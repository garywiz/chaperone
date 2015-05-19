import asyncio
import socket
import os
import re
import sys

from functools import partial

from cutil.logging import info, warn, debug
from logging.handlers import SysLogHandler

_FACILITY = ('kern', 'user', 'mail', 'daemon', 'auth', 'syslog', 'lpr', 'news', 'uucp', 'clock', 'authpriv',
             'ftp', 'ntp', 'audit', 'alert', 'cron', 'local0', 'local1', 'local2', 'local3', 'local4',
             'local5', 'local6', 'local7')
_FACILITY_DICT = {_FACILITY[i]:i for i in range(len(_FACILITY))}

_PRIORITY = ('emerg', 'alert', 'crit', 'err', 'warn', 'notice', 'info', 'debug')
_PRIORITY_DICT = {_PRIORITY[i]:i for i in range(len(_PRIORITY))}

_PRIORITY_DICT['warning'] = _PRIORITY_DICT['warn']
_PRIORITY_DICT['error'] = _PRIORITY_DICT['err']

_RE_SPEC = re.compile(r'^(?P<fpfx>!?)(?:/(?P<regex>.+)/|\[(?P<prog>.+)\]|(?P<fac>[*a-zA-Z]+))\.(?P<pfx>!?=?)(?P<pri>[*a-zA-Z]+)$')
_RE_SPECSEP = re.compile(r' *; *')

_RE_SYSLOG = re.compile(r'^<(?P<pri>\d+)>(?P<date>\w{3} [ 0-9][0-9] \d\d:\d\d:\d\d) (?P<prog>[^ \[]+)(?P<rest>\[\d+\]: .+)$')

class _syslog_spec_matcher:
    """
    This class supports matching a classic syslog.conf spec:
       <facilty>.<priority>
    where:
        facility is a list of comma-separated faclities, or '*'
        priority is a priority (meaning >=priority) or =priority (meaning exactly that priority)
    either may be preceded by '!' to invert the match.

    And the extensions:
       /regex/.<priority>
       where regex will match the entire message

       [prog].<priority>
       where prog will match the program specifier, if any

    One or more of the above can be combined, separated by semicolons.
    """

    __slots__ = ('_regexes', '_matchlist', 'debuglist')

    def __init__(self, speclist):
        self._regexes = []
        self._matchlist = []
        self.debuglist = []

        pieces = _RE_SPECSEP.split(speclist)
        for p in pieces:
            self._init_spec(p)

    def _init_spec(self, spec):
        match = _RE_SPEC.match(spec)

        if not match:
            raise Exception("Invalid log spec syntax: " + spec)

        # Compile an expression to match

        gdict = match.groupdict()

        if gdict['regex'] is not None:
            self._regexes.append(re.compile(gdict['regex'], re.IGNORECASE))
            s = '(bool(buf.search(s._regexes[%d])))' % (len(self._regexes) - 1)
        elif gdict['prog'] is not None:
            s = '(g and "%s" == g.lower())' % gdict['prog'].lower()
        elif gdict['fac'] != '*':
            fac = _FACILITY_DICT.get(gdict.get('fac'))
            if fac == None:
                raise Exception("Invalid logging facility code, %s: %s" % (gdict['fac'], spec))
            s = '(f==%d)' % fac
        else:
            s = None

        if gdict['fpfx']:
            e = ['(False)' if s is None else 'not ' + s]
        elif s is not None:
            e = [s]
        else:
            e = []              # all inclusive, no expr required

        pri = gdict['pri']
        pfx = gdict.get('pfx', '')

        if pri == '*':
            if '!' in pfx:
                e.append('(False)') # silly, but it's a valid syntax
        else:
            prival = _PRIORITY_DICT.get(pri)
            if prival == None:
                raise Exception("Invalid logging priority, %s: %s" % (pri, spec))
            s = "not " if '!' in pfx else ""

            if '=' in pfx:
                s += "(p==%d)" % prival
            else:
                s += "(p<=%d)" % prival
            e.append(s)

        self.debuglist.append(e) # keep these so we can examine the logic if we need to

        if e:
            expr = "lambda s,p,f,g,buf: " + " and ".join(e)
            self._matchlist.append(eval(expr))

    def match(self, msg, prog = None, priority = SysLogHandler.LOG_ERR, facility = SysLogHandler.LOG_SYSLOG):
        for m in self._matchlist():
            if not m(self, priority, facility, prog, msg):
                return False
        return True             # empty list is true as well
        
def create_unix_datagram_server(proto, path):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(path)
    return loop.create_unix_server(SyslogServerProtocol, sock=sock)

class SyslogServerProtocol(asyncio.Protocol):

    def __init__(self, parent):
        self.parent = parent
        super().__init__()

    def _output(self, msg, priority = SysLogHandler.LOG_ERR, facility = SysLogHandler.LOG_SYSLOG):
        print(msg)

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
            sys.stdout.flush()
            return

        messages = message.split("\0")
        for m in messages:
            if m:
                self._parse_to_output(m)
        sys.stdout.flush()

class SyslogServer:

    def run1(self):  # alternative additional datagram endpoint (experimental, probably not needed)
        loop = asyncio.get_event_loop()
        listen = loop.create_datagram_endpoint(SyslogServerProtocol, local_addr = ('127.0.0.1', SYSLOG_PORT))
        return asyncio.async(listen)

    def run(self):
        loop = asyncio.get_event_loop()
        listen = loop.create_unix_server(partial(SyslogServerProtocol, self), path="/dev/log")
        future = asyncio.async(listen)
        future.add_done_callback(lambda f: os.chmod("/dev/log", 0o777))
        return future
