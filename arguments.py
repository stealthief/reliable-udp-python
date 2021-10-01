import argparse
import os

MCAST_GRP = "224.1.1.1"
MCAST_PORT = 5007

def arguments():
        parser = argparse.ArgumentParser()

        """The parser takes a path to a file as input."""
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
        
        """The parser takes the target IP-address as input."""
        parser.add_argument(
            "--ip", type=str, help="The IP address to send to.", default=MCAST_GRP
        )

        """The parser takes the target port as input."""
        parser.add_argument(
            "--port", type=int, help="The port to send to.", default=MCAST_PORT
        )

        """The parser takes the packet size in bytes."""
        parser.add_argument(
            "--packet-size", type=int, help="Packet size in bytes.", default=1400
        )

        """The parser takes the generation size"""
        parser.add_argument(
            "--gen-size", type=int, help="Number of packets per generation.", default=20
        )
        args = parser.parse_args()
        return args