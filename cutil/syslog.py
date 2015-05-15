from cutil.logging import info, warn, debug
import asyncio
import socket
import os

def create_unix_datagram_server(proto, path):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(path)
    return loop.create_unix_server(SyslogServerProtocol, sock=sock)

class SyslogServerProtocol(asyncio.Protocol):
    def data_received(self, data):
        print("GOT DATA")
        message = data.decode()
        print('Receieved: ' + str(message))

class SyslogServer:

    def run1(self):
        loop = asyncio.get_event_loop()
        listen = loop.create_datagram_endpoint(SyslogServerProtocol, local_addr = ('127.0.0.1', SYSLOG_PORT))
        print("LISTEN", listen)
        return asyncio.async(listen)

    def run(self):
        loop = asyncio.get_event_loop()
        listen = loop.create_unix_server(SyslogServerProtocol, path="/dev/log")
        print("LISTEN", listen)
        future = asyncio.async(listen)
        future.add_done_callback(lambda f: os.chmod("/dev/log", 0o777))
        return future

