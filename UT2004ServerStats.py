#!/usr/bin/env python3

############################################################################
#               UT2004 Server Stats Monitor          by Snoop, 2019 - 2024 #
############################################################################

import socket, os, select
from threading import Thread, Event
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict
from typing import Optional

#===========================================================================
TARGET_SERVER_ADDRESS = ('109.230.224.189', 6969) # TUS (TAM)
#TARGET_SERVER_ADDRESS = ('81.30.148.30', 32800) # Fair games (DM)
#TARGET_SERVER_ADDRESS = ('194.26.183.119', 7788) # CEONSS (ONS)
#TARGET_SERVER_ADDRESS = ('80.4.151.145', 7777) # MIASMA (VCTF)
#===========================================================================

class PlayerTeam(Enum):
    SPEC = "spec"
    RED  = "red"
    BLUE = "blue"
    UNKNOWN = "-"

@dataclass
class PlayerInfo:
    name : str  = ""
    score : int = -1
    ping : int  = -1
    team : PlayerTeam  = PlayerTeam.UNKNOWN
    id : int    = -1

    def get_country_code(self) -> Optional[str]:
        if len(self.name) > 4 and self.name[-4] == "(" and self.name[-1] == ")":
            return self.name[-3:-1]
        return ""

@dataclass
class ServerInfo:
    name : str = ""
    map : str = ""
    game_type : str = ""
    cur_players : int = 0
    max_players : int = 0
    settings: Dict[str, str] = field(default_factory=dict)

class UT2004RawData:

    """ Helper class to parse data from raw UT2004 server response """

    def __init__(self, bytes):
        self.bytes = bytes
        self.length = len(bytes)
        self.pos = 0

    def read_string(self) -> str:
        i = self.pos + 1
        if i >= self.length:
            return ""
        res = ""
        while self.bytes[i] != 0:
            if self.bytes[i] == 0x1b: #byte color flag then escape RGB triplet
                i += 4
            res += chr(self.bytes[i])
            i += 1
        self.pos = i + 1
        return res

    def read_int32(self) -> int:
        i = self.pos
        self.pos += 4

        if (i >= self.length):
            return -1
        return int.from_bytes(self.bytes[i:i+4], byteorder='little', signed=True)

    def read_int8(self, align = 4) -> int:
        i = self.pos + align - 1
        self.pos += align

        if i >= self.length:
            return 0
        return self.bytes[i]

    def seek(self, delta):
        self.pos += delta

    def is_eof(self) -> bool:
        return self.pos >= self.length

class UT2004Server:

    """ UT2004 server info provider """

    def __init__(self, server_ip : str, server_port : int):
        self.server_address = (server_ip, server_port + 1)
        self.ip = server_ip
        self.port = server_port

    def getInfo(self) -> tuple[ServerInfo, list[PlayerInfo]]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(1)

        players_data = b''
        server_basic_data = b''
        server_settings_data = b''

        try:
            #send server info request
            sock.sendto(b'\x80\x00\x00\x00\x03', self.server_address)
            sock.sendto(b'\x80\x00\x00\x00\x00', self.server_address)
            #receive server info response
            while(True):
                ready = select.select([sock], [], [], 3)
                if (ready[0]):
                    tmp, server = sock.recvfrom(4096)
                else:
                    break

                if len(tmp) < 5: #empty section
                    continue

                packet_type = tmp[4]
                packet_payload = tmp[5:]

                if (packet_type == 0x01): #mutators and server setting section
                    server_settings_data += packet_payload
                if (packet_type == 0x02): #players info section
                    players_data += packet_payload
                if (packet_type == 0x00): #server info section
                    server_basic_data += packet_payload
                    break
        finally:
            sock.close()

        server_info = self._parseUT2004BasicServerInfo(server_basic_data, server_settings_data)
        players_info = self._parseUT2004PlayersInfo(players_data)

        return server_info, players_info

    def _parseUT2004PlayersInfo(self, data) -> list[PlayerInfo]:
        raw_data = UT2004RawData(data)
        raw_data.seek(4) # offset
        result = []

        while not raw_data.is_eof():
            player = PlayerInfo()
            player.name = raw_data.read_string()
            player.ping = raw_data.read_int32()
            player.score = raw_data.read_int32()
            team = raw_data.read_int8()
            player.id = raw_data.read_int32()

            teams = {0x00 : PlayerTeam.SPEC,
                     0x20 : PlayerTeam.RED,
                     0x40 : PlayerTeam.BLUE}

            player.team = teams.get(team, PlayerTeam.UNKNOWN)
            result.append(player)
        return result

    def _parseUT2004BasicServerInfo(self, basic_data, settings_data) -> ServerInfo:
        server_info = ServerInfo()

        # parse basic server info
        raw_data = UT2004RawData(basic_data)
        raw_data.seek(13) # offset
        server_info.name = raw_data.read_string()
        server_info.map = raw_data.read_string()
        server_info.game_type = raw_data.read_string()
        server_info.cur_players = raw_data.read_int32()
        server_info.max_players = raw_data.read_int32()

        # parse server settings
        raw_data = UT2004RawData(settings_data)
        while not raw_data.is_eof():
            key = raw_data.read_string()
            value = raw_data.read_string()
            server_info.settings[key] = value

        return server_info

class FormattedTable:

    """ Class to print formatted tables """

    def __init__(self, headers : list[str]):
        self.headers = headers
        self.rows = []

    def add_row(self, row : list[str]):
        self.rows.append(row)

    def print(self):
        max_widths = [len(header) for header in self.headers]
        for row in self.rows:
            for i, cell in enumerate(row):
                max_widths[i] = max(max_widths[i], len(cell))

        header = " | ".join([header.ljust(max_widths[i]) for i, header in enumerate(self.headers)])
        print(header)
        print("-" * len(header))
        for row in self.rows:
            row_str = " | ".join([cell.ljust(max_widths[i]) for i, cell in enumerate(row)])
            print(row_str)

    def clear_rows(self):
        self.rows = []

class MyThread(Thread):

    """ Thread class to monitor UT2004 server stats"""

    def __init__(self, event):
        Thread.__init__(self)
        self.stopped = event
        self.table = FormattedTable(["Name", "Score", "Ping", "Team", "ID"])
        self.ut_server  = UT2004Server(TARGET_SERVER_ADDRESS[0], TARGET_SERVER_ADDRESS[1])

    def clean(self):
        if os.name == 'nt':
            os.system('cls')
        else:
            os.system('clear')

    def tick(self):
        basic_server_info, players_info = self.ut_server.getInfo()

        self.clean()
        print(f"SERVER: {basic_server_info.name} GAME TYPE: {basic_server_info.game_type}")
        print(f"MAP: {basic_server_info.map} Players: {basic_server_info.cur_players} / {basic_server_info.max_players}")
        self.table.clear_rows()
        for player in players_info:
            self.table.add_row([player.name, str(player.score), str(player.ping), str(player.team.value), str(player.id)])
        self.table.print()

        # print("Server settings:")
        # for key, value in basic_server_info.settings.items():
        #    print(f"{key}: {value}")

    def run(self):
        self.tick()
        while not self.stopped.wait(5):
            self.tick()
    last_width = 0

#===========================================================================

def main():
    stop_thread = Event()
    thread = MyThread(stop_thread)
    thread.start()

if __name__ == "__main__":
    main()