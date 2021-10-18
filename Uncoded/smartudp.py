import argparse
import os
import socket
import sys
import struct
import random
import select
import hashlib

MCAST_GRP = "224.1.1.1"
MCAST_PORT = 5007


class SmartUDP:
    """
    A class to enable the reliable transmission of data via multi-cast UDP sockets between a server and multiple clients.
    ...
    Attributes
    ----------
    args : Array
        an array of input arguments collected at runtime
    mcast_grp : str
        a string containing the multi-cast IP address
    mcast_port : int
        an integer representing the port used for multi-cast
    data : dict
        a dictionary to store sequence number keys with data packet values
    gen_number : int
        an integer to track the generation number
    packet_bytes : int
        an integer representing the number of bytes per packet
    seq : int
        an integer representing the current sequence number
    gen_size : int
        an integer representing the configured generation size

    Methods
    -------
    progressBar(self, iteration, total, prefix = '', suffix = '', decimals = 1, length = 50, fill = '█', printEnd = "\r")
        Prints a transmission progress bar to the terminal during transmission
    """

    def __init__(self, args):
        """
        Parameters
        ----------
        args : list
            Arguments parsed in at runtime, used to initialise variables.
        """
        
        self.args = args
        self.mcast_grp = args.ip
        self.mcast_port = args.port
        self.data = {}
        self.gen_number = 0
        self.packet_bytes = 1400
        self.seq = 0
        self.gen_size = self.args.gen_size

    def progressBar (self, iteration, total, prefix = '', suffix = '', decimals = 1, length = 50, fill = '█', printEnd = "\r"):
        """
        Call in a loop to create terminal progress bar.

        Parameters
        ----------
            iteration : current iteration (Int)
            total : total iterations (Int)
            prefix : prefix string (Str), optional
            decimals : positive number of decimals in percent complete (Int), optional
            length : character length of bar (Int), optional
            fill : bar fill character (Str), optional
            printEnd : end character (e.g. "\r", "\r\n") (Str), optional
        """

        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        filledLength = int(length * iteration // total)
        bar = fill * filledLength + '-' * (length - filledLength)
        print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
        # Print New Line on Complete
        if iteration == total: 
            print()


class Server(SmartUDP):
    """
    A class to enable a server to reliably transmitt data via multi-cast UDP socket to a client
    ...
    Attributes
    ----------
    clients : dict
        a dictionary storing client hostname keys with state values
    address : tuple
        a tuple containing the IP address and port information for the multi-cast group
    total_bytes : int
        an integer representing the total number of bytes of data in the target file
    packet_bytes : int
        an integer representing the number of bytes per packet
    total_packets : int
        an integer representing the total number of packets of data to be transmitted
    num_gens : int
        an integer representing the total number of generations required to transmit the target file
    tx : int
        an integer storing the total number of data packets transmitted

    Methods
    -------
    connection()
        Creates UDP network socket
    open_file()
        Opens target file for reading
    get_data(seq)
        Reads a packet size of data and stores in the data dictionary with correct sequence number
    create_packet(packet_type, seq=0, payload=b'')
        Creates a packet with header and data
    transmit(packet)
        Transmits packet via socket
    receive()
        Receives packets via socket
    """

    def __init__(self, args):
        SmartUDP.__init__(self, args)
        self.clients = {}
        self.address = (self.mcast_grp, self.mcast_port)
        file_stats = os.stat(self.args.file_path)
        self.total_bytes = file_stats.st_size
        self.packet_bytes = self.args.packet_size
        self.total_packets = self.total_bytes // self.packet_bytes + 1
        if self.total_packets < self.gen_size:
            self.gen_size = self.total_packets
        self.num_gens = (-(-self.total_packets // self.gen_size))
        self.tx = 0

    def connection(self):
        """
        Initialises a multi-cast UDP socket with the multi-cast IP and port provided
        """
        self.sock = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_DGRAM, proto=socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        self.sock.setblocking(0)
        return True

    def open_file(self):
        """
        Opens the target file to be read as bytes
        """
        if not os.path.isfile(self.args.file_path):
            print(f"{self.args.file_path} is not a valid file.")
            sys.exit(1)
        else:
            self.f = open(os.path.expanduser(self.args.file_path), 'rb')
            enc_file = os.path.expanduser(self.args.file_path).encode()
            hash_obj = hashlib.sha1(enc_file)
            self.hex_val = hash_obj.hexdigest()
            return True

    def get_data(self, seq):
        """
        Reads a packet size of data from the open target file

        Parameters
        ----------
        seq : int
            The current sequence number

        Returns
        -------
        The packet-length of data for the current sequence
        """

        self.data[seq] = self.f.read(self.packet_bytes)
        return self.data[seq]

    def create_packet(self, packet_type, seq=0, payload=b''):
        """
        Creates a packet header containing:
            packet_type
            total_bytes
            packet_bytes
            total_packets
            seq
        
        If a payload (data) is included, this is appended to the header.

        Parameters
        ----------
        packet_type : int
            An integer to represent the packet type:
                1: Engineering
                2: Data
                3: End generation
                5: Moving to next generation
                6: File transfer complete

        seq : int, default=0
            An integer to represent the sequence number of the data payload. Default is 0 if not a data packet

        payload : bytes, default=b''
            A byte stream of data representing a single packet of bytes. Default is empty if not a data packet

        Returns
        -------
        A packet containing header and payload
        """

        header = bytearray(18)
        struct.pack_into( # Struct used to create the fixed length header
            '<HIIII',
            header,
            0,
            packet_type,
            self.total_bytes,
            self.packet_bytes,
            self.total_packets,
            seq
        )
        packet = header + payload # Attaching payload to header is a simple concatenation
        return packet

    def transmit(self, packet):
        """
        Transmits a packet via the multi-cast socket

        Parameters
        ----------
        packet : bytes
            Bytes representing a single packet from the create_packet method
        """

        ready = select.select([], [self.sock], [], 1)
        if ready[1]:
            self.sock.sendto(packet, self.address)
        return True

    def receive(self):
        """
        Receives and processes packets from clients

        Returns
        -------
        packet_type : int
            The type of packet received:
                1: Engineering
                3: Missing packets
                4: Generation complete

        symbol : bytes
            The payload of the received packet

        hostname : str
            The hostname of the source client, for updating the client dictionary
        """

        while True:
            ready = select.select([self.sock], [], [], 1)
            if ready[0]:
                packet = self.sock.recv(self.packet_bytes)
                symbol = bytearray(packet[6:])
                packet_type, hostname = struct.unpack_from('<HI', packet) # Struct unpacks the header
                # Engineering packet
                if packet_type == 1:
                    break
                # Request for re-transmit
                elif packet_type == 3:
                    break
                # No missing packets
                elif packet_type == 4:
                    break
            else:
                return 0, 0, 0
        return packet_type, symbol, hostname


class Client(SmartUDP):
    """
    A class to enable a client to reliably receive data via multi-cast UDP sockets from a server.
    ...
    Attributes
    ----------
    hostname : str
        a string containing the client hostname
    total_rx : int
        an integer to store the total number of received packets
    erased : int
        an integer to store the number of missed packets
    missing : list
        a list to store the sequence numbers of missed packets
    erasure : float
        a float representing the chance of packet erasure as a percentage
    gen_size : int
        an integer representing the generation size
    num_gens : int
        an integer representing the number of generations to receive the file

    Methods
    -------
    connection()
        Creates UDP network socket
    create_packet(packet_type, seq=0, payload=b'')
        Creates a packet with header and data
    set_generation()
        Sets up the missing list for the next generation sequence numbers
    save_file()
        Opens the output file and writes all received data to it
    transmit(packet)
        Transmits packet via socket
    receive()
        Receives packets via socket
    """

    def __init__(self, args):
        SmartUDP.__init__(self, args)
        self.hostname = args.hostname
        self.total_rx = 0
        self.erased = 0
        self.missing = []
        self.erasure = random.uniform(args.erasurelow, args.erasurehigh)
        self.gen_size = args.gen_size
        self.num_gens = 0

    def connection(self):
        """
        Initialises a multi-cast UDP socket with the multi-cast IP and port provided
        """
        self.sock = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_DGRAM, proto=socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('', self.mcast_port))
        self.mreq = struct.pack('4sl', socket.inet_aton(
            self.mcast_grp), socket.INADDR_ANY)
        self.sock.setsockopt(
            socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, self.mreq)
        self.sock.setblocking(0)
        return True

    def create_packet(self, packet_type, payload=b''):
        """
        Creates a packet header containing:
            packet_type
            hostname
        
        If a payload (data) is included, this is appended to the header.

        Parameters
        ----------
        packet_type : int
            An integer to represent the packet type:
                1: Engineering ACK
                3: Missing packets
                4: Generation complete

        payload : bytes, default=b''
            A byte stream of data representing a serialised version of missing packets list. Default is empty if not a data packet

        Returns
        -------
        A packet containing header and payload
        """

        header = bytearray(6)
        struct.pack_into(
            '<HI',
            header,
            0,
            packet_type,
            self.hostname
        )
        packet = header + payload
        return packet

    def set_generation(self):
        """
        Configures the missing packet list with the sequence numbers of the next generation
        """
        self.missing = list(range(self.gen_number*self.gen_size,
                            self.gen_number*self.gen_size+self.gen_size))
        return True

    def save_file(self):
        """
        Opens the output file for writing bytes and writes all received data to the file before closing.
        """
        f = open(self.args.output_file, "wb")
        for k in range(len(self.data)):
            f.write(self.data[k])
        f.close()
        enc_file = self.args.output_file.encode()
        hash_obj = hashlib.sha1(enc_file)
        self.hex_val = hash_obj.hexdigest()
        return True

    def transmit(self, packet, address):
        """
        Transmits a packet via uni-cast to the server

        Parameters
        ----------
        packet : bytes
            Bytes representing a single packet from the create_packet method
        """
        while True:
            ready = select.select([], [self.sock], [], 1)
            if ready[1]:
                self.sock.sendto(packet, address)
                break
        return True

    def receive(self):
        """
        Receives and processes packets from the server

        Returns
        -------
        packet_type : int
            The type of packet received:
                1: Engineering
                2: Data
                3: End generation
                5: ACK Generation complete
                6: File complete

        addr : str
            The hostname of the server, for uni-cast responses
        """

        while True:
            ready = select.select([self.sock], [], [], 1)
            if ready[0]:
                packet, addr = self.sock.recvfrom(self.packet_bytes + 18)
                symbol = bytearray(packet[18:])
                packet_type, self.total_bytes, self.packet_bytes, self.total_packets, seq = struct.unpack_from(
                    '<HIIII', packet)
                # Engineering packet
                if packet_type == 1:
                    self.num_gens = (-(-self.total_packets // self.gen_size))
                    if self.total_packets < self.gen_size:
                        self.gen_size = self.total_packets
                    return packet_type, addr
                # Data received
                elif packet_type == 2:
                    self.total_rx += 1
                    if random.uniform(0, 100) > self.erasure:
                        if seq in self.missing:
                            self.data[seq] = symbol
                            self.missing.remove(seq)
                    else:
                        self.erased += 1

            # Initial send complete, request re-send
                elif packet_type == 3:
                    break
                # File complete
                elif packet_type == 5:
                    break
                elif packet_type == 6:
                    break
            else:
                return 0, 0
        return packet_type, addr


def arguments():
    """
    A helper method called prior to class object instantiation to collate all input arguments for use by the constructor methods in setting variables.

    Parameters
    ----------
    --file-path : str
        The path to the file which should be sent

    --output-file : str
        The path to where the received file should be saved

    --ip : str
        The multi-cast group IP address

    --port : int
        The multi-cast port

    --packet-size : int
        The desired packet size in bytes

    --gen-size : int
        The desired number of packets per generation

    --hostname : str
        The hostname of the client
        Default is the actual hostname, but in virtual environments a unique hostname must be assigned per client

    --erasurelow : int
        The lower bound on erasure probability setting (%)

    --erasurehigh : int
        The upper bound on erasure probability setting (%)

    Returns
    -------
    args : list
        list of all arguments parsed in at runtime
    
    """
    parser = argparse.ArgumentParser()
    ip = socket.gethostbyname(socket.gethostname())

    parser.add_argument(
        "--file-path",
        type=str,
        help="Path to the file which should be sent.",
        default=os.path.realpath(__file__),
    )
    parser.add_argument(
        "--output-file",
        type=str,
        help="Path to the file which should be received.",
        default="output_file",
    )
    parser.add_argument(
        "--ip", type=str, help="The IP address to send to.", default=MCAST_GRP
    )
    parser.add_argument(
        "--port", type=int, help="The port to send to.", default=MCAST_PORT
    )
    parser.add_argument(
        "--packet-size", type=int, help="Packet size in bytes.", default=1400
    )
    parser.add_argument(
        "--gen-size", type=int, help="Number of packets per generation.", default=20
    )
    parser.add_argument(
        "--hostname", type=int, help="Client hostname", default=ip
    )
    parser.add_argument(
        "--erasurelow", type=int, help="Erasure low percentage", default=0
    )
    parser.add_argument(
        "--erasurehigh", type=int, help="Erasure high percentage", default=0
    )
    args = parser.parse_args()
    return args
