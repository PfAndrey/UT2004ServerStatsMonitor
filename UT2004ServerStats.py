#!/usr/bin/env python3

############################################################################
#               UT2004 Server Stats Monitor          by Snoop, 2019 - 2024 #
############################################################################

import socket, os, select
from threading import Thread, Event
from dataclasses import dataclass, field
from typing import Dict
from enum import Enum

#===========================================================================
server_address = ('80.4.151.145', 7777 + 1) #MIASMA.ROCK (vCTF)
#server_address = ('109.230.224.189', 6969 + 1) #TUS (TAM)
#server_address = ('52.57.28.68', 7767 + 1) #ZORDON (AS)
#server_address = ('81.30.148.30', 32800 + 1) #Fair games (DM)
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

@dataclass
class ServerInfo:
    name : str = ""
    map : str = ""
    game_type : str = ""
    cur_players : int = 0
    max_players : int = 0
    settings: Dict[str, str] = field(default_factory=dict)

class FormattedTable:
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

class UT2004RawData:

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

def regestUT2004ServerData(server_address) -> tuple[ServerInfo, list[PlayerInfo]]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(0)

    players_data = b''
    server_basic_data = b''
    server_settings_data = b''

    try:
        #send server info request
        sent = sock.sendto(b'\x80\x00\x00\x00\x03', server_address)
        sent = sock.sendto(b'\x80\x00\x00\x00\x00', server_address)
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

    server_info = parseUT2004BasicServerInfo(server_basic_data, server_settings_data)
    players_info = parseUT2004PlayersInfo(players_data)

    return server_info, players_info

def parseUT2004PlayersInfo(data) -> list[PlayerInfo]:
    rawData = UT2004RawData(data)
    rawData.seek(4) # offset
    result = []

    while not rawData.is_eof():
        player = PlayerInfo()
        player.name = rawData.read_string()
        player.ping = rawData.read_int32()
        player.score = rawData.read_int32()
        team = rawData.read_int8()
        player.id = rawData.read_int32()

        teams = {0x00 : PlayerTeam.SPEC,
                 0x20 : PlayerTeam.RED,
                 0x40 : PlayerTeam.BLUE}

        player.team = teams.get(team, PlayerTeam.UNKNOWN)
        result.append(player)
    return result

def parseUT2004BasicServerInfo(basic_data, settings_data) -> ServerInfo:
    server_info = ServerInfo()

    # parse basic server info
    rawData = UT2004RawData(basic_data)
    rawData.seek(13) # offset
    server_info.name = rawData.read_string()
    server_info.map = rawData.read_string()
    server_info.game_type = rawData.read_string()
    server_info.cur_players = rawData.read_int32()
    server_info.max_players = rawData.read_int32()

    # parse server settings
    rawData = UT2004RawData(settings_data)
    while not rawData.is_eof():
        key = rawData.read_string()
        value = rawData.read_string()
        server_info.settings[key] = value

    return server_info

class MyThread(Thread):
    def __init__(self, event, server_address):
        Thread.__init__(self)
        self.stopped = event
        self.address = server_address
        self.table = FormattedTable(["Name", "Score", "Ping", "Team", "ID"])

    def clean(self):
        if os.name == 'nt':
            os.system('cls')
        else:
            os.system('clear')

    def tick(self):
        basic_server_info, players_info = regestUT2004ServerData(server_address)

        self.clean()
        print(f"SERVER: {basic_server_info.name}")
        print(f"MAP: {basic_server_info.map} Players: {basic_server_info.cur_players} / {basic_server_info.max_players}")
        self.table.clear_rows()
        for row in players_info:
            self.table.add_row([row.name, str(row.score), str(row.ping), str(row.team.value), str(row.id)])
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
    thread = MyThread(stop_thread, server_address)
    thread.start()

if __name__ == "__main__":
    main()