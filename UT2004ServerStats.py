############################################################################
#               UT2004 Server Stats Monitor           by Snoop, 2019       # 
############################################################################

import socket, os, select
from threading import Thread, Event
from prettytable import PrettyTable
import string

#===========================================================================
server_address = ('80.4.151.145', 7777 + 1) #MIASMA.ROCK (vCTF)
#server_address = ('109.230.224.189', 6969 + 1) #TUS (TAM)
#server_address = ('52.57.28.68', 7767 + 1) #ZORDON (AS)
#server_address = ('81.30.148.30', 32800 + 1) #Fair games (DM)
#===========================================================================

def parseString(pos, data):
    i = pos + 1
    res = ""
    while True:
        if (data[i] == 0): #end of the string
            break;
        if (data[i] == 0x1b): #byte color flag then escape RGB triplet
            i+=4;
        res += chr(data[i])
        i+=1
    return res, i+1

def parseInt(pos, data):
    return int(data[pos]), pos + 4;

def regestUT2004ServerData(server_address):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(0)
    
    data = type('', (), {})()
    data.players = data.server = b''
    data.empty = False
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
                data.empty = True
                #print("server request timeout...");
                break; 
            #print(tmp,'\n====')
            if (len(tmp)<5): #empty section
                continue;
            elif (tmp[4] == 0x02): #players info section 
                data.players += tmp[5:]
            elif (tmp[4] == 0x01): #mutators and server setting section
                continue;
            elif (tmp[4] == 0x00): #server info section 
                data.server += tmp[5:]
                break;
    finally:
        sock.close()
    return data

def parseUT2004PlayersInfo(data):
    result = []
    pos = 4; i = 0
    if (pos >= len(data)):
        return result; #empty data        
    while(True): 
        obj = type('', (), {})()
        obj.team = obj.id = '-'
        obj.name, pos = parseString(pos, data);
        obj.ping, pos = parseInt(pos, data);
        obj.score, pos = parseInt(pos, data);

        team, pos = parseInt(pos+3, data);
        pos -=3;

        teams = {0x00 : "-",
                 0x20 : "red",
                 0x40 : "blue"}

        obj.team = teams[team]

        result.append(obj)

        if pos+4 < len(data):
            obj.id, pos = parseInt(pos, data);
        else:
            break
    return result

def parseUT2004BasicServerInfo(data):
    obj = type('', (), {})()
    obj.name = b'' 
    obj.name = obj.map = obj.type = obj.players = "none"
    #server name
    pos = 13
    obj.name, pos = parseString(pos,data)
    #map name
    obj.map, pos = parseString(pos,data)
    #game type
    obj.game_type, pos = parseString(pos,data)
    #max/cur players
    obj.cur_players, pos = parseInt(pos, data)
    obj.max_players, pos = parseInt(pos, data)
    return obj

class MyThread(Thread):
    def __init__(self, event, server_address):
        Thread.__init__(self)
        self.stopped = event
        self.address = server_address

    def tick(self):
        raw_data = regestUT2004ServerData(server_address)
        if (raw_data.empty == True):
            return
        players_info = parseUT2004PlayersInfo(raw_data.players);
        basic_server_info = parseUT2004BasicServerInfo(raw_data.server)
        os.system('cls')
        new_width = len(players_info)+7
        if (new_width != self.last_width):
            os.system("mode 60,"+str(new_width))
            self.last_width = new_width
        print("SERVER: ", basic_server_info.name)
        print("MAP: ", basic_server_info.map, " Players:" , basic_server_info.cur_players, "/", basic_server_info.max_players)
        t = PrettyTable(['Player Name', 'Score', 'Ping', 'Team', 'Id'])
        for row in players_info:
            t.add_row([row.name, row.score, row.ping, row.team, row.id])
        print(t)
        #print(t.get_string(sortby="Score",reversesort=True))

    def run(self):
        self.tick()
        while not self.stopped.wait(5):
            self.tick()
    last_width = 0;

#===========================================================================

stop_thread = Event()
thread = MyThread(stop_thread, server_address)
thread.start()
