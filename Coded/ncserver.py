import argparse
import kodo
import os
import socket
import struct
import sys
import time
import random
import pickle
import ncudp

def main():
    args = ncudp.arguments()
    s = ncudp.Server(args)
    s.connection()
    s.open_file()
    missing = 0
    gen = 0

    for _ in range(1):
        s.transmit(s.create_packet(1))
    print("Sent eng packet...")

    timeout = time.time() + 0.1
    while True:
        type, symbol, hostname = s.receive()
        if type == 1:
            s.clients[hostname] = 1
            print("Added client")
            print(s.clients)
        else:
            if time.time() > timeout:
                break
    
    for x in range(s.num_gens):
        # Read in block worth of data
        s.create_gen()
        # Load block into encoder buffer
        for _ in range(s.gen_size):
            s.transmit(s.create_packet(2))
            #print("Packet sent")
        for _ in range(1):
            s.transmit(s.create_packet(3))
            #print("finished gen")

        while True:
            type, symbol, hostname = s.receive()
            if type == 3:
                s.clients[hostname] = 3
                res = pickle.loads(symbol)
                if res > missing:
                    missing = res            
            elif type == 4:
                s.clients[hostname] = 4
            
            if all(v != 1 for v in s.clients.values()):
                if any(v == 3 for v in s.clients.values()):
                    for pkt in range(missing):
                        #print(f"Sending packet: {pkt}")
                        s.transmit(s.create_packet(2))
                    #print("--------------------------------")
                    s.transmit(s.create_packet(3))
                    missing = 0
                elif all(v == 4 for v in s.clients.values()):
                    s.transmit(s.create_packet(5))
                    gen += 1
                    break
        
        for client in s.clients:
            s.clients[client] = 1
    
    for _ in range(1):
        s.transmit(s.create_packet(6))

    print('File transfer complete.')
    s.sock.close()
    s.f.close()

if __name__ == '__main__':
    main()