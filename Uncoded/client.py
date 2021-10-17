import time
import pickle
import smartudp as sudp

def main():
    """
    Main flow control logic for the un-coded client.
    """
    args = sudp.arguments()# Get arguments at execution
    c = sudp.Client(args) # Initialise smartUDP client
    c.connection() # Initialise network socket

    print("\nClient initialised, awaiting connection...")

    # Engineering phase: Client listens and responds to server advertisement
    while True:
        type, addr = c.receive()
        if type == 1:
            c.transmit(c.create_packet(1), addr)
            c.set_generation()
            print(f"> Connected to server: {addr[0]}:{addr[1]}\n-------------------------------------")
            break
    
    start = time.time() + 0.1 # Start timer for measuring decode time

    # Loop for each generation in the file to be received
    for x in range(c.num_gens):
        # Receive data packets and respond until no missing packets
        while c.missing:
            type, addr = c.receive()
            if type == 3: # Received end generation control packet
                res = pickle.dumps(c.missing)
                c.transmit(c.create_packet(3, res), addr) # Transmit missing list
        c.transmit(c.create_packet(4), addr)   # Transmit generation complete

        # When generation complete, wait for all other clients to complete before moving to next generation.    
        while True:
            type, addr = c.receive()
            if type == 5: # Server signals all clients complete
                c.progressBar(x+1, c.num_gens, 'Rx') # Increment receive progress
                c.gen_number += 1 # Increment current generation number
                c.set_generation() # Set the next generation for receiving
                break
    # When last generation complete, wait for file transfer complete confirmation from server   
    while True:
        type, addr = c.receive()
        if type == 6: # All clients finished receiving file
            c.save_file() # Save data to file
            break
    
    delta = time.time() - start # Calculate total decode time

    # Print statistics to terminal
    print("\nFile transfer complete!\n-------------------------------------")
    print(f"Decode Rate: {round((c.total_bytes / delta)/1e6, 2)} MB/s")
    print(f"Erasure Rate: {round(((c.erased)/(c.total_rx)) * 100, 1)}%\n")
    print(f"Run-time: {delta}")
    c.sock.close() # Close the socket

if __name__ == '__main__':
    main()