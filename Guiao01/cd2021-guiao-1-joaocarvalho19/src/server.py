"""CD Chat server program."""
import logging
import socket
import json
import selectors
from src.protocol import CDProto

logging.basicConfig(filename="server.log", level=logging.DEBUG)

class Server:
    """Chat Server process."""
    def __init__(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sel = selectors.DefaultSelector()

        self.clientList = {}        #dict {socket: username}
        self.channels = {}          #dict {socket: [channel_1, channel_2, ...]}

        self.s.bind(('localhost', 1234))
        self.s.listen(5)
        self.sel.register(self.s, selectors.EVENT_READ, self.accept)
        
    def loop(self):
        """Loop indefinetely."""
        while not self.done:
            events = self.sel.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)

    def accept(self, sock, mask):
        conn, addr = self.s.accept()  # Should be ready
        logging.info("Accepted %s from %s",conn, addr)
        self.sel.register(conn, selectors.EVENT_READ, self.read)

    def read(self, conn, mask):
        recv_data = CDProto.recv_msg( conn )
        if recv_data:
            data = json.loads(str(recv_data))
            logging.debug("Received: %s", data)
            if data["command"] == "register":
                self.clientList[conn] = data["user"]

            elif data["command"] == "message":
                if conn in self.channels.keys():
                    channel = self.channels[conn][-1]
                    for connection, chann_list in self.channels.items():
                        if channel in chann_list:                            
                            logging.debug('echoing %s to %s', repr(data["message"]), self.clientList[connection])
                            CDProto.send_msg( connection, CDProto.message(data["message"]))
                else:
                    for connection in self.clientList.keys():
                        logging.debug('echoing %s to %s', repr(data["message"]), self.clientList[connection])
                        CDProto.send_msg( connection, CDProto.message(data["message"]))
                    
            elif data["command"] == "join":
                if conn not in self.channels.keys():
                    self.channels[conn] = [data["channel"]]
                else:
                    value = self.channels[conn]
                    if data["channel"] in value:
                        value.remove(data["channel"])
                    self.channels[conn] = value + [data["channel"]]
                
        else:
            del self.clientList[conn]
            if conn in self.channels.keys():
                del self.channels[conn]
            logging.info('Closing %s',conn)
            self.sel.unregister(conn)
            conn.close()