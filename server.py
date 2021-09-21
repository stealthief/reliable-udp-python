import argparse
import os
import socket
import sys
import struct
import time
import random
import select
import pickle

MCAST_GRP = "224.1.1.1"
MCAST_PORT = 5007

class Server:
    
    def __init__(self, args):
        self.mcast_grp = MCAST_GRP
        self.mcast_port = MCAST_PORT
        self.clients = []
        self.data = {}
        self.address = (self.mcast_grp, self.mcast_port)
        self.args = args
        file_stats = os.stat(self.args.file_path)
        self.total_bytes = file_stats.st_size
        self.packet_bytes = 1400
        self.total_packets = self.total_bytes // self.packet_bytes + 1
        self.gen_size = 20

    def connection(self):
        self.sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM, proto=socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        self.sock.setblocking(0)
        return True

    def open_file(self):
        if not os.path.isfile(self.args.file_path):
            print(f"{self.args.file_path} is not a valid file.")
            sys.exit(1)
        else:
            self.f = open(os.path.expanduser(self.args.file_path), 'rb')
            return True

    def get_data(self, seq):
        self.data[seq] = self.f.read(self.packet_bytes-18)
        return self.data[seq]

    def create_packet(self, packet_type, seq=0, payload=b''):

        header = bytearray(18)
        struct.pack_into(
            '<HIIII',
            header,
            0,
            packet_type,
            self.total_bytes,
            self.packet_bytes,
            self.total_packets,
            seq
        )
        padding = bytearray(self.packet_bytes - (len(header) + len(payload)))
        packet = header + payload + padding

        return packet

    def transmit(self, packet):
        while True:
            ready = select.select([], [self.sock], [], 1)
            if ready[1]:
                self.sock.sendto(packet, self.address)
                break
        return True

    def receive(self):
        packet_type = None
        missing = []

        while True:
            ready = select.select([self.sock], [], [], 1)
            if ready[0]:
                packet = self.sock.recv(1400)
                symbol = bytearray(packet[2:])
                packet_type, = struct.unpack_from('<H', packet)
                if packet_type == 1:
                    if symbol not in self.clients:
                        self.clients.append(symbol)
                    break
                elif packet_type == 3:
                    res = pickle.loads(symbol)
                    for i in res:
                        self.transmit(self.create_packet(2, i, self.data[i]))
                    for i in range(3):
                        self.transmit(self.create_packet(3))      
                elif packet_type == 4:
                    break
        return True

def arguments():
        parser = argparse.ArgumentParser(description=main.__doc__)

        """The parser takes a path to a file as input."""
        parser.add_argument(
            "--file-path",
            type=str,
            help="Path to the file which should be sent.",
            default=os.path.realpath(__file__),
        )

        """The parser takes the target IP-address as input."""
        parser.add_argument(
            "--ip", type=str, help="The IP address to send to.", default=MCAST_GRP
        )

        """The parser takes the target port as input."""
        parser.add_argument(
            "--port", type=int, help="The port to send to.", default=MCAST_PORT
        )

        """One can tell the parser to run without using the network."""
        parser.add_argument(
            "--dry-run", action="store_true", help="Run without network use."
        )
        args = parser.parse_args()
        return args

def main():
    args = arguments()
    s = Server(args)
    s.connection()
    f = s.open_file()
    seq = 0
    eng = False
    complete = False
    # Send eng packets

    try:
        eng = s.create_packet(1)
        for i in range(1):
            s.transmit(eng)
        print("Engineering packet sent")

        # Will this keep trying to receive response??
        while not eng:
            if s.receive():
                eng = True
        #print(f"Number of clients is: {s.clients}")

        print(f"Total packets: {s.total_packets}\nNumber of gens: {s.total_packets / s.gen_size}")
        num_gens = s.total_packets // s.gen_size + 10
        print(f"Number of gens calced: {num_gens}")
        # Initial transmission
        for i in range(num_gens):
            print(i)
            packets = {}
            gen_complete = False
            for j in range(s.gen_size):
                data = s.get_data(seq)
                packet = s.create_packet(2, seq, data)
                s.transmit(packet)
                seq += 1
            for k in range(3):
                s.transmit(s.create_packet(3))
            while not gen_complete:
                if s.receive():
                    gen_complete = True
        
            for l in range(3):
                s.transmit(s.create_packet(4))
            
            print(f"Gen {i} complete")

        print("File transfer complete.")
    except KeyboardInterrupt:
        sys.exit(1)

if __name__ == '__main__':
    main()

