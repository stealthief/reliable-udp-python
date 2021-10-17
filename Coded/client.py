import time
import pickle
import ncudp

def main():
    """
    Main flow control logic for the network coded client.
    """
    args = ncudp.arguments() # Get arguments at execution
    c = ncudp.Client(args) # Instantiate ncUDP client object
    c.connection() # Initialise network socket
    data_out = bytearray() # Initialise array for received data

    print("\nClient initialised, awaiting connection...")

    # Engineering phase: Client listens and responds to server advertisement
    while True:
        type, addr = c.receive()
        if type == 1:
            c.transmit(c.create_packet(1), addr)
            print(f"> Connected to server: {addr[0]}:{addr[1]}\n-------------------------------------")
            break

    start = time.time() + 0.1 # Start timer for measuring decode time

    # Loop for each generation in the file to be received
    for x in range(c.num_gens):
        # Receive data packets and respond with any missing
        while True:
            type, addr = c.receive()
            if type == 3: # Received end generation control packet
                if c.decoder.is_complete(): # If all packets received, respond complete
                    c.transmit(c.create_packet(4), addr)
                    break
                else: # Otherwise return number of missing packets
                    res = pickle.dumps(c.missing)
                    c.transmit(c.create_packet(3, res), addr)
        # When generation complete, wait for all other clients to complete before moving to next generation.        
        while True:
            type, addr = c.receive()  
            if type == 5: # Server signals all clients complete
                c.progressBar(x+1, c.num_gens, 'Rx') # Increment receive progress
                data_out.extend(c.data) # Append data to data array
                c.next_gen() # Set the next generation for receiving
                break
    # When last generation complete, wait for file transfer complete confirmation from server        
    while True:
        type, addr = c.receive()
        if type == 6: # All clients finished receiving file
            c.save_file(data_out) # Save data to file
            break

    delta = time.time() - start # Calculate total decode time

    # Print statistics to terminal
    print("\nFile transfer complete!\n-------------------------------------")
    print(f"Decode Rate: {round((c.total_bytes / delta)/1e6, 2)} MBytes/s")
    print(f"Erasure Rate: {round(((c.erased)/(c.total_rx)) * 100, 1)}%\n")
    print(f"Run-time: {delta}")
    c.sock.close() # Close the socket

if __name__ == '__main__':
    main()