import time
import pickle
import smartudp as sudp

def main():
    """
    Main flow control logic for the un-coded server.
    """
    args = sudp.arguments() # Get arguments at execution
    s = sudp.Server(args) # Instantiate smartUDP server object
    s.connection() # Initialise network socket
    s.open_file() # Open the target file
    missing = [] # Initialise empty missing packet list

    # Engineering phase: Server sends advertisement packets
    for _ in range(3):
        s.transmit(s.create_packet(1))
    print("\nSent engineering packet, awaiting response...")

    # Wait for clients to respond and add them to the 'client state matrix'
    timeout = time.time() + 0.1
    while True:
        type, symbol, hostname = s.receive()
        if type == 1:
            s.clients[hostname] = 1 # Adding client to state matrix by hostname and default state of 1
        else:
            if time.time() > timeout:
                break

    print(f"> Connected to {len(s.clients)} client(s)\n-------------------------------------")
        
    # Loop for each generation in the file to be transmitted
    for x in range(s.num_gens):
        s.gen_number = x # Set generation number
        # Initial transmission of generation packets
        for _ in range(s.gen_size):
            s.transmit(s.create_packet(2, s.seq, s.get_data(s.seq)))
            s.seq += 1 # Increment the sequence number
            s.tx += 1 # Track number of data packets sent for calculating re-transmission rate
        for _ in range(1):
            s.transmit(s.create_packet(3)) # Transmit end generation control packet

        # Loop to receive missing packet lists from clients
        while True:
            type, symbol, hostname = s.receive()
            if type == 3: # If missing, add to list and client state to 3
                s.clients[hostname] = 3
                res = pickle.loads(symbol)
                for pkt in res:
                    missing.append(pkt)
            elif type == 4: # If not missing, set client state to 4
                s.clients[hostname] = 4
            # If all clients have reported status, re-transmit any packets in the missing list
            if all(v != 1 for v in s.clients.values()):
                if any(v == 3 for v in s.clients.values()):
                    for pkt in missing:
                        s.transmit(s.create_packet(2, pkt, s.data[pkt]))
                        s.tx += 1 # Track number of data packets sent for calculating re-transmission rate
                    s.transmit(s.create_packet(3))
                    missing.clear() # Empty the missing list after re-transmissions complete
                # If all clients complete (state 4), send finished gen packet
                elif all(v == 4 for v in s.clients.values()):
                    s.transmit(s.create_packet(5))
                    break

        s.progressBar(x+1, s.num_gens, 'Tx') # Increment transmit progress
        for client in s.clients: # Reset client states to 1
            s.clients[client] = 1 
            
    # When last generation complete, transmit end file packet
    for _ in range(1):
        s.transmit(s.create_packet(6))

    # Print statistics to terminal
    print('\nFile transfer complete!\n-------------------------------------')
    print(f'Re-transmit rate: {round(((s.tx / s.total_packets) -1)*100, 1)} %\n')
    s.sock.close() # Close the socket
    s.f.close() # Close the target file

if __name__ == '__main__':
    main()