"""CD Chat client program"""
import logging
import sys
import selectors
import fcntl
import os

from .protocol import CDProto, CDProtoBadFormat
import socket
import json
from datetime import datetime

logging.basicConfig(filename=f"{sys.argv[0]}.log", level=logging.DEBUG)

class Client:
    """Chat Client process."""

    def __init__(self, name: str = "Foo"):
        """Initializes chat client."""
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.name = name
        self._host = "localhost"
        self.selector = selectors.DefaultSelector()
        self.cicle = True        #loop variable

    def connect(self):
        """Connect to chat server and setup stdin flags."""
        orig_fl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fl | os.O_NONBLOCK)

        self.selector.register(self.s, selectors.EVENT_READ, self.read)
        self.selector.register(sys.stdin, selectors.EVENT_READ, self.write)

        self.s.connect((self._host, 1234))
        #Register User  
        CDProto.send_msg( self.s, CDProto.register(self.name))

    def write(self, stdin, mask):
        line = stdin.read()
        if line.replace(" ","") == 'exit\n':
            self.selector.unregister(stdin)
            self.selector.unregister(self.s)
            #  close 
            self.s.close()
            self.cicle = False
            
        if "/join" in line:
            line = line.rstrip('\n')
            channel = line.replace("/join ","")
            CDProto.send_msg( self.s, CDProto.join(channel.replace(" ","")))
            
        if line.replace(" ","") != 'exit\n' and "/join" not in line and line != '':
            CDProto.send_msg( self.s, CDProto.message(line.rstrip('\n')))

    def read(self, conn, mask):
        recv_data = CDProto.recv_msg( self.s )
        data = json.loads(str(recv_data))
        res = data["message"].rstrip('\n')
        logging.debug("Received: %s", str(data))
        print('Keyboard input: {}'.format(res))
        return res

    def loop(self):
        """Loop indefinetely."""
        while self.cicle:
            #Msg cicle
            sys.stdout.write('Message: ')
            sys.stdout.flush()
            for key, mask in self.selector.select():
                callback = key.data
                callback(key.fileobj, mask)