import time
import pickle
import ncudp

def main():
    args = ncudp.arguments()
    c = ncudp.Client(args)
    c.connection()
    data_out = bytearray()

    print("Awaiting connection...")

    while True:
        type, addr = c.receive()
        if type == 1:
            c.transmit(c.create_packet(1), addr)
            print("Connected to server...")
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
                if c.decoder.is_complete():
                    #c.save_file()
                    data_out.extend(c.data)
                    c.next_gen()
                    break

    while True:
        type, addr = c.receive()
        if type == 6:
            c.save_file(data_out)
            break

    delta = time.time() - start
    print(f"Throughput: {c.total_bytes / delta} Bytes/s")
    print(f"Total erasure: {((c.erased)/(c.total_rx)) * 100}%")
    c.sock.close()
    print("Processing finished.")

if __name__ == '__main__':
    main()