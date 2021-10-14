import time
import pickle
import smartudp as sudp

def main():
    args = sudp.arguments()# Get arguments passed in
    c = sudp.Client(args) # Initialise client
    c.connection() # Create client socket
    erased = 0

    print("\nClient initialised, awaiting connection...")
    # Receive engineering packet
    while True:
        type, addr = c.receive()
        if type == 1:
            c.transmit(c.create_packet(1), addr)
            c.set_generation()
            print(f"> Connected to server: {addr[0]}:{addr[1]}\n-------------------------------------")
            break

    # Start receiving file     
    start = time.time() + 0.1 
    for x in range(c.num_gens):

        # Receive and request missing
        while c.missing:
            type, addr = c.receive()
            if type == 3:
                erased += len(c.missing)
                res = pickle.dumps(c.missing)
                c.transmit(c.create_packet(3, res), addr)
        c.transmit(c.create_packet(4), addr)   

        # Wait for all clients to finish receiving generation    
        while True:
            type, addr = c.receive()
            if type == 5: # Generation received
                c.progressBar(x+1, c.num_gens, 'Rx')
                c.gen_number += 1
                c.set_generation()
                break
    
    # Confirm file complete and save
    while True:
        type, addr = c.receive()
        if type == 6:
            c.save_file()
            break
    print("\nFile transfer complete!\n-------------------------------------")
    delta = time.time() - start # Calculate time taken
    # Print out thrroughput and erasure
    print(f"Decode Rate: {round((c.total_bytes / delta)/1e6, 2)} MB/s")
    print(f"Erasure Rate: {round(((c.erased)/(c.total_rx)) * 100, 1)}%\n")
    c.sock.close()
if __name__ == '__main__':
    main()