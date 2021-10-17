import argparse
import os
import socket
import sys
import struct
import random
import select
import hashlib

MCAST_GRP = "224.1.1.1"
MCAST_PORT = 5007


class SmartUDP:

    def __init__(self, args):
        self.args = args
        self.mcast_grp = args.ip
        self.mcast_port = args.port
        self.data = {}
        self.gen_number = 0
        self.packet_bytes = 1400
        self.seq = 0
        self.gen_size = self.args.gen_size

    def __str__(self):
        return f'Created'

    def progressBar (self, iteration, total, prefix = '', suffix = '', decimals = 1, length = 50, fill = '█', printEnd = "\r"):
        """
        Call in a loop to create terminal progress bar
        @params:
            iteration   - Required  : current iteration (Int)
            total       - Required  : total iterations (Int)
            prefix      - Optional  : prefix string (Str)
            decimals    - Optional  : positive number of decimals in percent complete (Int)
            length      - Optional  : character length of bar (Int)
            fill        - Optional  : bar fill character (Str)
            printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
        """
        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        filledLength = int(length * iteration // total)
        bar = fill * filledLength + '-' * (length - filledLength)
        print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
        # Print New Line on Complete
        if iteration == total: 
            print()


class Server(SmartUDP):

    def __init__(self, args):
        SmartUDP.__init__(self, args)
        self.clients = {}
        self.address = (self.mcast_grp, self.mcast_port)
        file_stats = os.stat(self.args.file_path)
        self.total_bytes = file_stats.st_size
        self.packet_bytes = self.args.packet_size
        self.total_packets = self.total_bytes // self.packet_bytes + 1
        if self.total_packets < self.gen_size:
            self.gen_size = self.total_packets
        self.num_gens = (-(-self.total_packets // self.gen_size))
        self.tx = 0

    def connection(self):
        self.sock = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_DGRAM, proto=socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        self.sock.setblocking(0)
        return True

    def open_file(self):
        if not os.path.isfile(self.args.file_path):
            print(f"{self.args.file_path} is not a valid file.")
            sys.exit(1)
        else:
            self.f = open(os.path.expanduser(self.args.file_path), 'rb')
            enc_file = os.path.expanduser(self.args.file_path).encode()
            hash_obj = hashlib.sha1(enc_file)
            self.hex_val = hash_obj.hexdigest()
            return True

    def get_data(self, seq):
        self.data[seq] = self.f.read(self.packet_bytes)
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
        packet = header + payload
        return packet

    def transmit(self, packet):
        ready = select.select([], [self.sock], [], 1)
        if ready[1]:
            self.sock.sendto(packet, self.address)
        return True

    def receive(self):
        while True:
            ready = select.select([self.sock], [], [], 1)
            if ready[0]:
                packet = self.sock.recv(self.packet_bytes)
                symbol = bytearray(packet[6:])
                packet_type, hostname = struct.unpack_from('<HI', packet)
                # Engineering type packet
                if packet_type == 1:
                    break
                # Request for re-send
                elif packet_type == 3:
                    break
                elif packet_type == 4:
                    break
            else:
                return 0, 0, 0
        return packet_type, symbol, hostname


class Client(SmartUDP):

    def __init__(self, args):
        SmartUDP.__init__(self, args)
        self.hostname = args.hostname
        self.total_rx = 0
        self.erased = 0
        self.missing = []
        self.erasure = random.uniform(args.erasurelow, args.erasurehigh)
        self.gen_size = args.gen_size
        self.num_gens = 0

    def connection(self):
        self.sock = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_DGRAM, proto=socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', self.mcast_port))
        self.mreq = struct.pack('4sl', socket.inet_aton(
            self.mcast_grp), socket.INADDR_ANY)
        self.sock.setsockopt(
            socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, self.mreq)
        self.sock.setblocking(0)
        return True

    def create_packet(self, packet_type, payload=b''):
        header = bytearray(6)
        struct.pack_into(
            '<HI',
            header,
            0,
            packet_type,
            self.hostname
        )
        padding = bytearray(self.packet_bytes - (len(header) + len(payload)))
        packet = header + payload

        return packet

    def set_generation(self):
        self.missing = list(range(self.gen_number*self.gen_size,
                            self.gen_number*self.gen_size+self.gen_size))
        return True

    def save_file(self):
        f = open(self.args.output_file, "wb")
        for k in range(len(self.data)):
            f.write(self.data[k])
        f.close()
        enc_file = self.args.output_file.encode()
        hash_obj = hashlib.sha1(enc_file)
        self.hex_val = hash_obj.hexdigest()
        return True

    def transmit(self, packet, address):
        while True:
            ready = select.select([], [self.sock], [], 1)
            if ready[1]:
                self.sock.sendto(packet, address)
                break
        return True

    def receive(self):
        while True:
            ready = select.select([self.sock], [], [], 1)
            if ready[0]:
                packet, addr = self.sock.recvfrom(self.packet_bytes + 18)
                symbol = bytearray(packet[18:])
                packet_type, self.total_bytes, self.packet_bytes, self.total_packets, seq = struct.unpack_from(
                    '<HIIII', packet)
                # Engineering packet
                if packet_type == 1:
                    self.num_gens = (-(-self.total_packets // self.gen_size))
                    if self.total_packets < self.gen_size:
                        self.gen_size = self.total_packets
                    return packet_type, addr
                # Data received
                elif packet_type == 2:
                    self.total_rx += 1
                    if random.uniform(0, 100) > self.erasure:
                        if seq in self.missing:
                            self.data[seq] = symbol
                            self.missing.remove(seq)
                    else:
                        self.erased += 1

            # Initial send complete, request re-send
                elif packet_type == 3:
                    break
                # Ack gen complete
                elif packet_type == 4:
                    break
                # File complete
                elif packet_type == 5:
                    break
                elif packet_type == 6:
                    break
            else:
                return 0, 0
        return packet_type, addr


def arguments():
    parser = argparse.ArgumentParser()
    ip = socket.gethostbyname(socket.gethostname())

    """The parser takes a path to a file as input."""
    parser.add_argument(
        "--file-path",
        type=str,
        help="Path to the file which should be sent.",
        default=os.path.realpath(__file__),
    )

    parser.add_argument(
        "--output-file",
        type=str,
        help="Path to the file which should be received.",
        default="output_file",
    )

    """The parser takes the target IP-address as input."""
    parser.add_argument(
        "--ip", type=str, help="The IP address to send to.", default=MCAST_GRP
    )

    """The parser takes the target port as input."""
    parser.add_argument(
        "--port", type=int, help="The port to send to.", default=MCAST_PORT
    )

    """The parser takes the packet size in bytes."""
    parser.add_argument(
        "--packet-size", type=int, help="Packet size in bytes.", default=1400
    )

    """The parser takes the generation size"""
    parser.add_argument(
        "--gen-size", type=int, help="Number of packets per generation.", default=20
    )

    """The parser takes the client number"""
    parser.add_argument(
        "--hostname", type=int, help="Client Number", default=0
    )

    """The parser takes the erasure probability"""
    parser.add_argument(
        "--erasurelow", type=int, help="Erasure low percentage", default=0
    )

    """The parser takes the erasure probability"""
    parser.add_argument(
        "--erasurehigh", type=int, help="Erasure high percentage", default=0
    )
    args = parser.parse_args()
    return args
