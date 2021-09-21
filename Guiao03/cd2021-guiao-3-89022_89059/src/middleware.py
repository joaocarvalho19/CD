"""Middleware to communicate with PubSub Message Broker."""
from collections.abc import Callable
from enum import Enum
from queue import LifoQueue, Empty
from typing import Any
import socket
import sys
import fcntl
import os
import selectors
import json
import pickle
import xml.etree.ElementTree as ET

class MiddlewareType(Enum):
    """Middleware Type."""

    CONSUMER = 1
    PRODUCER = 2


class Queue:
    """Representation of Queue interface for both Consumers and Producers."""

    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        """Create Queue."""
        self.sock = socket.socket()
        self.host = 'localhost'
        self.port = 5000
        self.sel = selectors.DefaultSelector() #create selector
        self.sock.connect((self.host, self.port)) # connect to server (block until accepted)
        self.topic = topic
        self._type = _type
        self.sock.send(len(str(self.__class__.__name__)).to_bytes(2, "big"))
        self.sock.send(str(self.__class__.__name__).encode('utf-8'))
        if _type == MiddlewareType.CONSUMER:
            self.send("SUBSCRIPTION", topic)

    def push(self, value):  
        """Sends data to broker. """
        self.send("PUBLICATION", value)
        print(value)
        

    def send(self, command, value):
        data, cab = self.encode(command,self.topic,value)
        self.sock.send(cab)
        self.sock.send(data)

    def pull(self) -> (str, Any):
        """Waits for (topic, data) from broker.

        Should BLOCK the consumer!"""
        cab_len = int.from_bytes(self.sock.recv(2), "big")
        if cab_len:
            recv_data = self.sock.recv(cab_len)
            topic, value = self.decode(recv_data)
            return topic, value
        else:
            return None
        

    def list_topics(self, callback: Callable):
        """Lists all topics available in the broker."""
        self.send("LIST_REQ", "")

    def cancel(self):
        """Cancel subscription."""
        self.send('CANCEL_SUBS', "")

class JSONQueue(Queue):
    """Queue implementation with JSON based serialization."""
    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        super().__init__(topic, _type)
    
    def encode(self,command, topic, value):
        msg = json.dumps({"command": command, "topic": topic, "data": value})
        return bytes(msg,encoding="utf-8"), len(msg).to_bytes(2, "big")

    def decode(self, msg):
        msg = json.loads(msg.decode("utf-8"))
        return msg["topic"],msg["data"]

class XMLQueue(Queue):
    """Queue implementation with XML based serialization."""
    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        super().__init__(topic, _type)

    def encode(self,command, topic, value):
        xml = '<?xml version="1.0"?><data command="{}" topic="{}" msg="{}" ></data>'.format(command, topic, value)
        msg = xml.encode('utf-8')
        return msg, len(str(msg)).to_bytes(2, "big")

    def decode(self,msg):
        root = ET.fromstring(msg.decode("utf-8"))
            
        value=root.attrib
        command=value['command']
        topic=value['topic']
        data=value['msg']

        return topic,data

class PickleQueue(Queue):
    """Queue implementation with Pickle based serialization."""
    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        super().__init__(topic, _type)

    def encode(self,command, topic, value):
        msg = pickle.dumps({"command": command, "topic": topic, "data": value})
        return msg, len(str(msg)).to_bytes(2, "big")

    def decode(self, msg):
        msg = pickle.loads(msg)
        return msg["topic"],msg["data"]