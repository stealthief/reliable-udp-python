import argparse
import kodo
import os
from os import path
import socket
import struct
import select
import sys
import time
import random

import atexit

MCAST_GRP = "224.1.1.1"
MCAST_PORT = 5007


class ncUDP:

    def __init__(self, args):
        self.args = args
        self.mcast_grp = args.ip
        self.mcast_port = args.port
        self.field = kodo.FiniteField.binary16
        self.gen_size = self.args.gen_size


class Server(ncUDP):

    def __init__(self, args):
        ncUDP.__init__(self, args)
        self.clients = {}
        self.address = (self.mcast_grp, self.mcast_port)
        file_stats = os.stat(self.args.file_path)
        self.total_bytes = file_stats.st_size
        self.packet_bytes = self.args.packet_size
        self.total_packets = self.total_bytes // self.packet_bytes + 1
        if self.total_packets < self.gen_size:
            self.gen_size = self.total_packets
        self.num_gens = (-(-self.total_packets // self.gen_size))
        self.encoder = kodo.block.Encoder(self.field)
        self.generator = kodo.block.generator.RandomUniform(self.field)
        self.set_encoder()

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
            return True

    def set_encoder(self):
        self.encoder.configure(self.gen_size, self.packet_bytes)
        self.symbol = bytearray(self.encoder.symbol_bytes)
        self.generator.configure(self.encoder.symbols)
        self.coefficients = bytearray(self.generator.max_coefficients_bytes)

    def create_gen(self):
        self.data = bytearray(self.f.read(
            self.encoder.block_bytes).ljust(self.encoder.block_bytes))
        #data = bytearray(os.urandom(self.encoder.block_bytes))
        # print((-(-len(data)//self.packet_bytes)))
        self.gen_size = (-(-len(self.data)//self.packet_bytes))
        self.set_encoder()
        self.encoder.set_symbols_storage(self.data)

    def create_packet(self, packet_type):
        header_data = bytearray(29)
        if packet_type == 2:
            seed = random.randint(0, 2 ** 64-1)
            self.generator.set_seed(seed)
            self.generator.generate(self.coefficients)
            self.encoder.encode_symbol(self.symbol, self.coefficients)
        else:
            seed = 0

        struct.pack_into(
            '<HQQBIIH',
            header_data,
            0,
            packet_type,
            seed,
            self.field.value,
            self.field.value,
            self.total_bytes,
            self.packet_bytes,
            self.gen_size
        )
        if packet_type == 2:
            packet = header_data + self.symbol
        else:
            packet = header_data
        return packet

    def transmit(self, packet):
        while True:
            ready = select.select([], [self.sock], [], 1)
            if ready[1]:
                self.sock.sendto(packet, self.address)
                break
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


class Client(ncUDP):

    def __init__(self, args):
        ncUDP.__init__(self, args)
        self.decoder = kodo.block.Decoder(self.field)
        self.generator = kodo.block.generator.RandomUniform(self.field)
        self.missing = 0
        self.hostname = args.hostname
        self.erased = 0
        self.total_rx = 0
        self.erasure = args.erasure
        if os.path.exists('output_file'):
            os.remove('output_file')

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

    def next_gen(self):

        self.decoder.configure(self.gen_size, self.packet_bytes)
        self.generator.configure(self.decoder.symbols)
        self.symbol = bytearray(self.decoder.symbol_bytes)
        self.coefficients = bytearray(self.generator.max_coefficients_bytes)
        self.data.clear()
        self.data = bytearray(self.decoder.block_bytes)
        self.decoder.set_symbols_storage(self.data)
        self.missing = self.gen_size

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

    def save_file(self, data):
        self.f = open(self.args.output_file, "wb")
        self.f.write(data)
        self.f.close()
        print("Gen received")
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
                packet, addr = self.sock.recvfrom(1429)
                symbol = bytearray(packet[29:])
                packet_type, seed, self.offset, field_byte, self.total_bytes, self.packet_bytes, self.gen_size = struct.unpack_from(
                    '<HQQBIIH', packet)
                self.total_packets = self.total_bytes // self.packet_bytes + 1
                # Engineering packet
                if packet_type == 1:
                    self.num_gens = (-(-self.total_packets // self.gen_size))
                    self.decoder.configure(self.gen_size, self.packet_bytes)
                    self.generator.configure(self.decoder.symbols)
                    self.symbol = bytearray(self.decoder.symbol_bytes)
                    self.coefficients = bytearray(
                        self.generator.max_coefficients_bytes)
                    self.data = bytearray(self.decoder.block_bytes)
                    self.decoder.set_symbols_storage(self.data)
                    self.missing = self.gen_size
                    self.full_gen = self.gen_size
                    break

                # Data received
                elif packet_type == 2:
                    self.total_rx += 1
                    if random.uniform(0, 100) > self.erasure:
                        if self.gen_size != self.full_gen:
                            self.next_gen()
                        self.generator.set_seed(seed)
                        self.generator.generate(self.coefficients)
                        self.decoder.decode_symbol(symbol, self.coefficients)
                        self.missing -= 1
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
        "--erasure", type=int, help="Erasure percentage", default=0
    )
    args = parser.parse_args()
    return args
