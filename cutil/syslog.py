from cutil.logging import info, warn, debug
from logging.handlers import SysLogHandler
import asyncio
import socket
import os
import re

_RE_SYSLOG = re.compile(r'^<(?P<pri>\d+)>(?P<date>\w{3} [ 0-9][0-9] \d\d:\d\d:\d\d) (?P<prog>[^ \[]+)(?P<rest>\[\d+\]: .+)$')

def create_unix_datagram_server(proto, path):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(path)
    return loop.create_unix_server(SyslogServerProtocol, sock=sock)

class SyslogServerProtocol(asyncio.Protocol):

    def _output(self, msg, priority = SysLogHandler.LOG_ERR, facility = SysLogHandler.LOG_SYSLOG):
        print ("<{0}>{1}".format(facility * 8 + priority, msg))

    def _parse_to_output(self, msg):
        match = _RE_SYSLOG.match(msg)
        if not match:
            self._output(msg)
            return
        pri = int(match.group('pri'))
        self._output(match.group('date') + ' ' + os.path.basename(match.group('prog')) + ' ' + match.group('rest'),
                     priority = pri & 7, facility = pri // 8)

    def data_received(self, data):
        try:
            message = data.decode()
        except Exception as ex:
            self._output("Could not decode SYSLOG record data")
            return

        messages = message.split("\0")
        for m in messages:
            if m:
                self._parse_to_output(m)

class SyslogServer:

    def run1(self):
        loop = asyncio.get_event_loop()
        listen = loop.create_datagram_endpoint(SyslogServerProtocol, local_addr = ('127.0.0.1', SYSLOG_PORT))
        return asyncio.async(listen)

    def run(self):
        loop = asyncio.get_event_loop()
        listen = loop.create_unix_server(SyslogServerProtocol, path="/dev/log")
        future = asyncio.async(listen)
        future.add_done_callback(lambda f: os.chmod("/dev/log", 0o777))
        return future

