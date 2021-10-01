import os
import sys
import time
import pickle
import queue
import smartudp as sudp


def main():
    args = sudp.arguments()
    s = sudp.Server(args)
    s.connection()
    s.open_file()
    missing = []

    # Send eng packets
    for _ in range(3):
        s.transmit(s.create_packet(1))
    print("Sent eng packet...")

    # Wait and receive any responses from clients
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
        
    # Start sending generations
    for x in range(s.num_gens):
        s.gen_number = x
        # Initial gen send
        for y in range(s.gen_size):
            s.transmit(s.create_packet(2, s.seq, s.get_data(s.seq)))
            s.seq += 1
        for _ in range(1):
            s.transmit(s.create_packet(3))

        # Loop to receive missing packet lists from clients
        while True:
            type, symbol, hostname = s.receive()
            # If missing, add to list
            if type == 3:
                s.clients[hostname] = 3
                res = pickle.loads(symbol)
                for pkt in res:
                    missing.append(pkt)
            # If no missing, set client state to 4
            elif type == 4:
                s.clients[hostname] = 4
            # While clients are missing (state 3), send missing packets
            if all(v != 1 for v in s.clients.values()):
                if any(v == 3 for v in s.clients.values()):
                    for pkt in missing:
                        s.transmit(s.create_packet(2, pkt, s.data[pkt]))
                    s.transmit(s.create_packet(3))
                    missing.clear()
                # If all clients complete (state 4), send finished gen packet
                elif all(v == 4 for v in s.clients.values()):
                    s.transmit(s.create_packet(5))
                    break
        # Reset client states to 1
        for client in s.clients:
            s.clients[client] = 1
            
    # After all generations complete, send finish file packet
    for _ in range(1):
        s.transmit(s.create_packet(6))

    print('File transfer complete.')
    s.sock.close()
    s.f.close()


if __name__ == '__main__':
    main()