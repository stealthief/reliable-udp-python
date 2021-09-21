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

class Client:
    
    def __init__(self, args):
        self.mcast_grp = MCAST_GRP
        self.mcast_port = MCAST_PORT
        self.data = {}
        self.args = args
        self.erased = 0
        self.missing = []
        self.gen_num = 0
        self.actual = []

    def connection(self):
        self.sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM, proto=socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', self.mcast_port))
        self.mreq = struct.pack('4sl', socket.inet_aton(self.mcast_grp), socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, self.mreq)
        self.sock.setblocking(0)
        return True

    def transmit(self, address, packet_type, payload=b''):
        header = bytearray(2)
        struct.pack_into(
            '<H',
            header,
            0,
            packet_type
        )
        padding = bytearray(self.packet_bytes - (len(header) + len(payload)))
        packet = header + payload

        self.sock.sendto(packet, address)
        return True

    def receive(self, missing=[]):

        while True:
            ready = select.select([self.sock], [], [], 1)
            if ready[0]:
                packet, addr = self.sock.recvfrom(1400)
                symbol = bytearray(packet[18:])
                packet_type, self.total_bytes, self.packet_bytes, self.total_packets, seq = struct.unpack_from('<HIIII', packet)
                # Engineering packet
                if packet_type == 1:
                    self.transmit(addr, 1, bytearray('Client1', 'utf-8'))
                    break
                # Data received
                elif packet_type == 2:
                    # if random.randint(0,10000) > 0:
                    self.data[seq] = symbol
                    #try:
                    self.missing.remove(seq)
                    # except:
                    #     pass           
                # Initial send complete, request re-send
                elif packet_type == 3:
                    if self.missing:
                        self.erased += len(self.missing)
                        res = pickle.dumps(self.missing)
                        for x in self.missing:
                            self.actual.append(x)
                        self.transmit(addr, 3, res)
                    else:
                        self.transmit(addr, 4)
                # Ack gen complete
                elif packet_type == 4:
                    self.gen_num += 1
                    self.missing = list(range(self.gen_num*20, self.gen_num*20+20))
                    break
        return True


def arguments():
        parser = argparse.ArgumentParser(description=main.__doc__)
        parser.add_argument(
            "--output-file",
            type=str,
            help="Path to the file which should be received.",
            default="output_file",
        )

        parser.add_argument(
            "--ip", type=str, help="The IP address to use.", default=MCAST_GRP
        )

        parser.add_argument("--port", type=int, help="The port to use.", default=MCAST_PORT)

        parser.add_argument(
            "--dry-run", action="store_true", help="Run without network use."
        )

        args = parser.parse_args()
        return args

def main():
    args = arguments()
    c = Client(args)
    c.connection()
    f = open(c.args.output_file, "ab+")

    start = time.time()
    print("Awaiting engineering packet...")
    eng_pkt = False
    complete = False
    try:
        # Receive eng packet and ack, then receive file
        while not eng_pkt:
            if c.receive():
                eng_pkt = True

        print("Attempting to receive data...")
        c.missing = list(range(c.gen_num*20, c.gen_num*20+20))
        num_gens = c.total_packets // 20 + 10
        print(num_gens)
        for i in range(num_gens-1):
            c.receive()
                
        print(c.actual)

        f = open(c.args.output_file, "wb")
        for k in range(len(c.data)):
            f.write(c.data[k])
        f.close()
        print("File received")
        delta = time.time() - start

        print(f"Throughput: {c.total_bytes / delta} Bytes/s")
        print(f"Total erasure: {(c.erased/(c.total_packets)) * 100}%")

    except KeyboardInterrupt:
        sys.exit(1)

if __name__ == '__main__':
    main()
    

