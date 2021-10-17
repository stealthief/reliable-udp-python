import time
import pickle
import ncudp

def main():
    args = ncudp.arguments()
    c = ncudp.Client(args)
    c.connection()
    data_out = bytearray()

    print("\nClient initialised, awaiting connection...")

    while True:
        type, addr = c.receive()
        if type == 1:
            c.transmit(c.create_packet(1), addr)
            print(f"> Connected to server: {addr[0]}:{addr[1]}\n-------------------------------------")
            break

    start = time.time() + 0.1
    for x in range(c.num_gens):
        while True:
            type, addr = c.receive()
            if type == 3:
                if c.decoder.is_complete():
                    c.transmit(c.create_packet(4), addr)
                    break
                else:
                    #print(f"missing: {c.missing}")
                    res = pickle.dumps(c.missing)
                    c.transmit(c.create_packet(3, res), addr)
                
        #print("Generation decoded")
        while True:
            type, addr = c.receive()
    
            if type == 5:
                #c.progressBar(x+1, c.num_gens, 'Rx')
                data_out.extend(c.data)
                c.next_gen()
                break
            
    
    while True:
        type, addr = c.receive()
        if type == 6:
            c.save_file(data_out)
            break
    print("\nFile transfer complete!\n-------------------------------------")
    delta = time.time() - start
    print(f"Decode Rate: {round((c.total_bytes / delta)/1e6, 2)} MBytes/s")
    print(f"Erasure Rate: {round(((c.erased)/(c.total_rx)) * 100, 1)}%\n")
    print(f"Run-time: {delta}")
    c.sock.close()

if __name__ == '__main__':
    main()