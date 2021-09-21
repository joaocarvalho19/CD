"""Message Broker"""
import enum
from typing import Dict, List, Any, Tuple
import socket
import selectors
import json
import pickle
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element,tostring
import pickle

class Serializer(enum.Enum):
    """Possible message serializers."""

    JSON = 0
    XML = 1
    PICKLE = 2


class Broker:
    """Implementation of a PubSub Message Broker."""

    def __init__(self):
        """Initialize broker."""
        self.canceled = False
        self._host = "localhost"
        self._port = 5000
        
        self.topics = {}
        self.last_message = {}
        self.users = {}
        self.sock = socket.socket()
        self.sel = selectors.DefaultSelector() #create selector
        self.sock.bind((self._host, self._port))
        self.sock.listen(100)
        self.sel.register(self.sock, selectors.EVENT_READ, self.accept)
        

    def accept(self, sock, mask):
        conn, addr = self.sock.accept()  # Should be ready
        cab_len = int.from_bytes(conn.recv(2), "big")
        if cab_len:
            recv_data_mechanism = conn.recv(cab_len)
            if recv_data_mechanism:
                self.users[conn] = str(recv_data_mechanism.decode('utf-8'))  #save user mechanism (JSONQueue, XMLQueue, PickleQueue)
            
        else:                  
            self.sel.unregister(conn)
            conn.close()

        self.sel.register(conn, selectors.EVENT_READ, self.read)

    def read(self, conn, mask):
        cab_len = int.from_bytes(conn.recv(2), "big")
        if cab_len:
            recv_data = conn.recv(cab_len)
            #print("RECV: {}".format(recv_data))
            command, topic, data = "","",""
            if self.users[conn] == 'JSONQueue':
                command, topic, data = self.recv_json(recv_data)
            if self.users[conn] == 'XMLQueue':
                command, topic, data = self.recv_xml(recv_data)
            if self.users[conn] == 'PickleQueue':
                command, topic, data = self.recv_pickle(recv_data)

            if command == "SUBSCRIPTION":
                self.subscribe(data, conn)
                last_msg = self.get_topic(data)
                if last_msg:
                    if self.users[conn] == 'JSONQueue':
                        value, cab = self.encode_json(command, topic, last_msg)
                        self.send(conn, value, cab)
                    if self.users[conn] == 'XMLQueue':
                        value, cab = self.encode_xml(command, topic, last_msg)
                        self.send(conn, value, cab)
                    if self.users[conn] == 'PickleQueue':
                        value, cab = self.encode_pickle(command, topic, last_msg)
                        self.send(conn, value, cab)

            if command == "LIST_REQ":
                if self.users[connection] == 'JSONQueue':
                    value, cab = self.encode_json(command, top, self.list_topics())
                    self.send(connection, value, cab)
                if self.users[connection] == 'XMLQueue':
                    value, cab = self.encode_xml(command, top, self.list_topics())
                    self.send(connection, value, cab)
                if self.users[connection] == 'PickleQueue':
                    value, cab = self.encode_pickle(command, top, self.list_topics())
                    self.send(connection, value, cab)
            
            if command == "CANCEL_SUBS":
                if conn in self.users:
                    del self.users[conn]  
                for i in self.topics:
                    for addr,_format in self.topics[i]:
                        if addr == conn:
                            self.topics[i].remove((addr,_format))

            if command == "PUBLICATION":
                self.put_topic(topic, data)
                if conn in self.users:
                    for top in self.hierarchy_topics(topic):
                        if self.list_subscriptions(top):
                            for connection, _format in self.list_subscriptions(top):
                                if self.users[connection] == 'JSONQueue':
                                    value, cab = self.encode_json(command, top, data)
                                    self.send(connection, value, cab)
                                if self.users[connection] == 'XMLQueue':
                                    value, cab = self.encode_xml(command, top, data)
                                    self.send(connection, value, cab)
                                if self.users[connection] == 'PickleQueue':
                                    value, cab = self.encode_pickle(command, top, data)
                                    self.send(connection, value, cab)

        else:
            del self.users[conn]
            for i in self.topics:
                for addr,_format in self.topics[i]:
                    if addr == conn:
                        self.topics[i].remove((addr,_format))
            self.sel.unregister(conn)
            conn.close()

    def hierarchy_topics(self, topics):
        #'qwe/asd/zxc' -> ['/qwe', '/qwe/asd', 'qwe/asd/zxc']
        if "/" in topics:
            top_list = topics.rsplit('/', 1)
            if top_list[0] != "":
                return self.hierarchy_topics(top_list[0]) + [topics]
            else:
                return [topics]
        else:
            return [topics]

    def send(self, conn, data, cab):
        conn.send(cab)
        conn.send(data)
    
    def recv_json(self, recv_data):
        data = json.loads(recv_data.decode('utf-8'))
        return data["command"], data["topic"], data["data"]
    
    def recv_xml(self, msg):
        root = ET.fromstring(msg.decode("utf-8"))
        
        value=root.attrib
        command=value['command']
        topic=value['topic']
        data=value['msg']

        return command,topic,data
    
    def recv_pickle(self, recv_data):
        data = pickle.loads(recv_data)
        return data["command"], data["topic"], data["data"]

    def encode_json(self, command, topic, value):
        msg = json.dumps({"command": command, "topic": topic, "data": value})
        return bytes(msg,encoding="utf-8"), len(str(msg)).to_bytes(2, "big")
    
    def encode_xml(self, command, topic, value):
        xml = '<?xml version="1.0"?><data command="{}" topic="{}" msg="{}" ></data>'.format(command, topic, value)
        msg = xml.encode('utf-8')
        return msg, len(str(msg)).to_bytes(2, "big")

    def encode_pickle(self, command, topic, value):
        msg = pickle.dumps({"command": command, "topic": topic, "data": value})
        return msg, len(msg).to_bytes(2, "big")

    def list_topics(self) -> List[str]:
        """Returns a list of strings containing all topics."""
        return list(self.last_message.keys()) # return all keys from topics dict

    def get_topic(self, topic):
        """Returns the currently stored value in topic."""
        if topic in self.last_message.keys():
            return self.last_message[topic]
        else:
            return None

    def put_topic(self, topic, value):
        """Store in topic the value."""
        self.last_message[topic] = value

    def list_subscriptions(self, topic: str) -> List[socket.socket]:
        """Provide list of subscribers to a given topic."""
        if topic in self.topics:
            return self.topics[topic]
        else:
            return None
    
    def subscribe(self, topic: str, address: socket.socket, _format: Serializer = None):
        """Subscribe to topic by client in address."""
        if topic in self.topics.keys():
            self.topics[topic].append((address, _format))
        else:
            self.topics[topic] = [(address, _format)]
    
    def unsubscribe(self, topic, address):
        """Unsubscribe to topic by client in address."""
        if topic in self.topics.keys():
            for addr,_format in self.topics[topic]:
                if addr == address:
                    self.topics[topic].remove((addr,_format))

    def run(self):
        """Run until canceled."""
        while not self.canceled:
            events = self.sel.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)