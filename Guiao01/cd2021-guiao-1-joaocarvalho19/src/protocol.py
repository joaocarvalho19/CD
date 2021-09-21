"""Protocol for chat server - Computação Distribuida Assignment 1."""
import json
from datetime import datetime
from socket import socket


class Message:
    """Message Type."""
    def __init__(self, message):
        self.message = message

    def __repr__(self):
        return json.dumps(self.message)

    
class JoinMessage(Message):
    """Message to join a chat channel."""
    def __init__(self, channel):
        self.message = {"command": "join", "channel": channel}

    def __repr__(self):
        return json.dumps(self.message) 


class RegisterMessage(Message):
    """Message to register username in the server."""
    def __init__(self, username):
        self.message = {"command": "register", "user": username}
    
    def __repr__(self):
        return json.dumps(self.message)
        
    
class TextMessage(Message):
    """Message to chat with other clients."""
    def __init__(self, msg, channel = None):
        now = datetime.now()
        timestamp = datetime.timestamp(now)
        if not channel:
            self.message = {"command": "message", "message": msg, "ts": int(round(timestamp))}
        else:
            self.message = {"command": "message", "message": msg, "ts": int(round(timestamp)), "channel": channel}
    
    def __repr__(self):
        return json.dumps(self.message)


class CDProto:
    """Computação Distribuida Protocol."""

    @classmethod
    def register(cls, username: str) -> RegisterMessage:
        """Creates a RegisterMessage object."""
        return RegisterMessage(username)

    @classmethod
    def join(cls, channel: str) -> JoinMessage:
        """Creates a JoinMessage object."""
        return JoinMessage(channel)

    @classmethod
    def message(cls, message: str, channel: str = None) -> TextMessage:
        """Creates a TextMessage object."""
        
        return TextMessage(message, channel)

    @classmethod
    def send_msg(cls, connection: socket, msg: Message):
        """Sends through a connection a Message object."""
        connection.sendall(len(str(msg)).to_bytes(2, "big"))
        connection.sendall(bytes(str(msg),encoding="utf-8"))

    @classmethod
    def recv_msg(cls, connection: socket) -> Message:
        """Receives through a connection a Message object."""
        message={}
        cab_len = int.from_bytes(connection.recv(2), "big")
        msg_recv = connection.recv(cab_len)
        if msg_recv and cab_len:
            try:
                msg = json.loads(msg_recv.decode("utf-8"))
            except ValueError:
                #not json
                raise CDProtoBadFormat(msg_recv)
            else:
                #json
                if msg["command"] == "register":
                    message = RegisterMessage(msg["user"])
                elif msg["command"] == "join":
                    message = JoinMessage(msg["channel"])
                elif msg["command"] == "message":
                    message = TextMessage(msg["message"])
                
                return message
        else:
            return None


class CDProtoBadFormat(Exception):
    """Exception when source message is not CDProto."""
    def __init__(self, original_msg: bytes=None) :
        """Store original message that triggered exception."""
        self._original = original_msg

    @property
    def original_msg(self) -> str:
        """Retrieve original message as a string."""
        return self._original.decode("utf-8")