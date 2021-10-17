import time
import pickle
import ncudp

def main():
    """
    Main flow control logic for the network coded server.
    """
    args = ncudp.arguments() # Get arguments at execution
    s = ncudp.Server(args) # Instantiate ncUDP server object
    s.connection() # Initialise network socket
    s.open_file() # Open the target file
    missing = 0 # Initialise empty missing packet number to 0

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
        s.current_gen = x # Set generation number
        s.create_gen() # Initialise encoder and create generation of coded packets
        # Initial transmission of generation packets
        for _ in range(s.gen_size):
            s.transmit(s.create_packet(2))
            s.tx += 1 # Track number of data packets sent for calculating re-transmission rate
        for _ in range(1):
            s.transmit(s.create_packet(3)) # Transmit end generation control packet

        count = 0
        while True:
            type, symbol, hostname = s.receive()
            if type == 3: # If missing, add to list and client state to 3
                s.clients[hostname] = 3
                res = pickle.loads(symbol)
                if res > missing:
                    missing = res            
            elif type == 4: # If not missing, set client state to 4
                s.clients[hostname] = 4
            else: # Re-transmit end generation control packet for clients that missed it
                if count == 3: 
                    s.transmit(s.create_packet(3))
                    count = 0
                else:
                    count += 1
            # If all clients have reported status, re-transmit new coded packets == to missing
            if all(v != 1 for v in s.clients.values()):
                if missing != 0:
                    for _ in range(missing):
                        s.transmit(s.create_packet(2))
                        s.tx += 1 # Track number of data packets sent for calculating re-transmission rate
                    for y in s.clients: # Reset clients state that were missing back to 1
                        if s.clients[y] == 3:
                            s.clients[y] = 1
                    s.transmit(s.create_packet(3))
                    missing = 0 # Set missing to 0 after re-transmissions complete
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
    print('File transfer complete.')
    s.sock.close() # Close the socket
    s.f.close() # Close the target file

if __name__ == '__main__':
    main()