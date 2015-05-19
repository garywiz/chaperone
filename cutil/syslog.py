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

_RE_SPEC = re.compile(r'^(?P<fpfx>!?)(?:/(?P<regex>.+)/|\[(?P<prog>.+)\]|(?P<fac>[,*a-zA-Z]+))\.(?P<pfx>!?=?)(?P<pri>[*a-zA-Z]+)$')
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

    Note that the syslogd semantics are hard to actually figure out, even if you scour the web.  So, here are
    some rules.

    The semicolon "joins" constraints by combining all negative constraints (those which omit facilities or priorities)
    and positive constraints separately.   The result will be logged ONLY if all the positive constraints are true
    and all of the negative constraints are false!

    So,
       *.!emerg               LOGS NOTHING (missing inclusions)
       *.*;*.!emerg           logs everything bug .emerg
       *.info;![cron].*       logs all info or higher, but omits everything from program "cron"
       *.*;![cron].!=info     Omits the info messages from any program BUT cron
       [cron].*;*.!info       includes all cron messages except those of info and above

    More specifically:
       *.info                 Includes info through emergency (6->0) but not Debug
       *.!info                Excludes info through emergency but does not exclude debug
       *.=info                Includes just info itself
       *.!=info               Excludes everything BUT info
       !f.!=info              Excludes everyting BUT info from everything BUT f

    Why all this bother?
    1.  Basic cases are pretty easy to read and understand.
    2.  Negations can be understood if documented, and are useful.
    3.  I don't want to introduce a completely new syntax.
    3.  Somewhere out here, there is some nerdy OCD guy who will say "But wait, your filter format is so CLOSE
        to the syslog format that you MUST support it with the same semantics or you're going to alienate [me]."  
        Just nipping that in the bud.
    """

    __slots__ = ('_regexes', '_match', 'debugexpr')

    def __init__(self, speclist):
        self._regexes = []

        pieces = _RE_SPECSEP.split(speclist)

        # Build the list of negations and positive expressions
        neg = list()
        pos = list()
        for p in pieces:
            self._init_spec(p, neg, pos)

        if not pos:
            self._buildex("False")
        elif not neg:
            self._buildex(" or ".join(pos))
        else:
            self._buildex("(" + (" or ".join(neg)) + ") and (" + (" or ".join(pos)) + ")")

    def _buildex(self, expr):
        # Perform some quick peepole optimization, then compile
        nexpr = expr.replace("True and ", "").replace(" and True", "")
        nexpr = nexpr.replace("not True", "False").replace("and ((True))", "")
        nexpr = nexpr.replace("False or ", "")
        self.debugexpr = nexpr
        self._match = eval("lambda s,p,f,g,buf: " + nexpr)

    def _init_spec(self, spec, neg, pos):
        match = _RE_SPEC.match(spec)

        if not match:
            raise Exception("Invalid log spec syntax: " + spec)

        # Compile an expression to match

        gdict = match.groupdict()

        if gdict['regex'] is not None:
            self._regexes.append(re.compile(gdict['regex'], re.IGNORECASE))
            c1 = 'bool(buf.search(s._regexes[%d]))' % (len(self._regexes) - 1)
        elif gdict['prog'] is not None:
            c1 = '(g and "%s" == g.lower())' % gdict['prog'].lower()
        elif gdict['fac'] != '*':
            faclist = [_FACILITY_DICT.get(f) for f in gdict.get('fac', '').split(',')]
            if None in faclist:
                raise Exception("Invalid logging facility code, %s: %s" % (gdict['fac'], spec))
            c1 = '(' + ' or '.join(['f==%d' % f for f in faclist]) + ')'
        else:
            c1 = 'True'

        pri = gdict['pri']
        pfx = gdict.get('pfx', '')

        if pri == '*':
            c2 = 'True'
        else:
            prival = _PRIORITY_DICT.get(pri)
            if prival == None:
                raise Exception("Invalid logging priority, %s: %s" % (pri, spec))
            if '=' in pfx:
                c2 = "p==%d" % prival
            else:
                c2 = "p<=%d" % prival

        fpfx = gdict.get('fpfx', '')

        # Assess negatives and positives.
        # neg will contain "EXCLUDE IF" and pos will contain "INCLUDE IF"

        if '!' in fpfx:
            # Double exclusion means to exclude everything except the given priority from
            # everything except the given facility
            if '!' in pfx:
                neg.append("(not %s and not %s)" % (c1, c2))
            else:
                neg.append("not (%s and %s)" % (c1, c2))
        elif '!' in pfx:
            neg.append("(not %s or not %s)" % (c1, c2))
        else:
            pos.append("(%s and %s)" % (c1, c2))
            
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
