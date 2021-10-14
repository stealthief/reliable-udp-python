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
    print("\nSent engineering packet, awaiting response...")

    timeout = time.time() + 0.1
    while True:
        type, symbol, hostname = s.receive()
        if type == 1:
            s.clients[hostname] = 1
            #print("Added client")
        else:
            if time.time() > timeout:
                break
    print(f"> Connected to {len(s.clients)} client(s)\n-------------------------------------")
    
    for x in range(s.num_gens):
        # Read in block worth of data
        s.current_gen = x
        s.create_gen()
        # Load block into encoder buffer
        for _ in range(s.gen_size):
            s.transmit(s.create_packet(2))
            s.tx += 1
        for _ in range(1):
            s.transmit(s.create_packet(3))

        count = 0
        while True:
            type, symbol, hostname = s.receive()
            if type == 3:
                s.clients[hostname] = 3
                res = pickle.loads(symbol)
                if res > missing:
                    missing = res            
            elif type == 4:
                s.clients[hostname] = 4
            else:
                if count == 3:
                    s.transmit(s.create_packet(3))
                else:
                    count += 1
            
            if all(v != 1 for v in s.clients.values()):
                if missing != 0:
                    for pkt in range(missing):
                        s.transmit(s.create_packet(2))
                        s.tx += 1
                    for y in s.clients:
                        if s.clients[y] == 3:
                            s.clients[y] = 1
                    s.transmit(s.create_packet(3))
                    missing = 0
                elif all(v == 4 for v in s.clients.values()):
                    s.transmit(s.create_packet(5))
                    gen += 1
                    break

        s.progressBar(x+1, s.num_gens, 'Tx')
        for client in s.clients:
            s.clients[client] = 1
    for _ in range(1):
        s.transmit(s.create_packet(6))

    print('\nFile transfer complete!\n-------------------------------------')
    print(f'Re-transmit rate: {round(((s.tx / s.total_packets) -1)*100, 1)} %\n')
    print('File transfer complete.')
    s.sock.close()
    s.f.close()

if __name__ == '__main__':
    main()