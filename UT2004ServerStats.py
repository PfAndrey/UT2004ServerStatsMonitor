############################################################################
#               UT2004 Sever Stats Monitor            by Snoop, 2019       # 
############################################################################

import socket, os
from threading import Thread, Event
from prettytable import PrettyTable
import string

#===========================================================================
#server_address = ('52.57.28.68', 7767 + 1) #ZORDON AS
server_address = ('116.203.71.213',51337 + 1) #TR TAM
#server_address = ('208.79.234.80',9000 + 1) #Omnip ONS
#server_address = ('81.30.148.30', 32800 + 1) #FAIR-games DM
#===========================================================================

def extractString(pos, data, skip_first=0):
    if (pos>=len(data)):
        return "", pos
    ln = int(data[pos])
    from_p = pos+1+skip_first;
    to_p = pos+ln+1     
    str = data[from_p:to_p].decode("ansi") 
    #printable = set(string.printable)
    #filter(lambda x: x in printable, str)
    return str, pos+ln + 1

def escapeUTColorCharasters(str):
    res = ''; i=0
    while(i < len(str)):
        if (ord(str[i]) == 0x1b): #if byte color flag then escape RGB triplet
            i+=4;
        if (i >= len(str)):
            break;
        res += str[i]
        i+=1
    #print("result:",res)
    return res;

def regestUT2004ServerData(server_address):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    data = type('', (), {})()
    data.players = b''
    data.server = b''
    try:
        #send server info request
        sent = sock.sendto(b'\x80\x00\x00\x00\x03', server_address)
        sent = sock.sendto(b'\x80\x00\x00\x00\x00', server_address)
        #receive server info response
        while(True):
            tmp, server = sock.recvfrom(4096)
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
    print(data)
    return data

def parseUT2004PlayersInfo(data):
    result = []
    pos = 4; i = 0
    if (pos >= len(data)):
        return result; #empty data        
    while(True): 
        obj = type('', (), {})()
        obj.team = obj.id = '-'
        str, pos = extractString(pos,data);
        obj.name = escapeUTColorCharasters(str)
        obj.ping = int(data[pos])
        obj.score = int(data[pos+4])     
        if (pos+12<len(data)):
            obj.id = data[pos+12]
            team = data[pos+11];
            if (team == 0x40): obj.team = 'blue'
            if (team == 0x20): obj.team = 'red'
            if (team == 0x00): obj.team = '-'
        result.append(obj)
        pos += 16
        if (pos + 1 >= len(data)):
            break
    return result

def parseUT2004BasicServerInfo(data):
    obj = type('', (), {})()
    obj.name = b'' 
    obj.name = obj.map = obj.type = obj.players = "none"

    #server name
    pos = 13
    str,pos = extractString(pos,data,1)
    obj.name = escapeUTColorCharasters(str)
 
    pos+=1      
    str,pos= extractString(pos,data)
    obj.map = escapeUTColorCharasters(str)
    
    obj.game_type, pos = extractString(pos,data)
    obj.cur_players = int(data[pos])
    obj.max_players = int(data[pos+4])
    return obj

class MyThread(Thread):
    def __init__(self, event, server_address):
        Thread.__init__(self)
        self.stopped = event
        self.address = server_address

    def tick(self):
        raw_data = regestUT2004ServerData(server_address)
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
