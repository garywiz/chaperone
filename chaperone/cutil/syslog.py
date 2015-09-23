import asyncio
import socket
import os
import re
import sys
import logging

from time import strftime
from functools import partial

from chaperone.cutil.logging import info, warn, debug, set_custom_handler
from chaperone.cutil.misc import lazydict, maybe_remove, remove_for_recreate
from chaperone.cutil.servers import ServerProtocol, Server
from chaperone.cutil.syslog_handlers import LogOutput

import chaperone.cutil.syslog_info as syslog_info

_RE_SPEC = re.compile(r'^(?P<fpfx>!?)(?:/(?P<regex>.+)/|\[(?P<prog>.+)\]|(?P<fac>[,*0-9a-zA-Z]+))\.(?P<pfx>!?=?)(?P<pri>[*a-zA-Z]+)$')
_RE_SPECSEP = re.compile(r' *; *')

# The following is based on RFC3164 with some tweaks to deal with anomalies.
# One anomaly worth mentioning is that some log sources append newlines (or whitespace) to their messages,
# or include embedded newlines.  Here is a good JIRA discussion about how Apache dealt with this, including some background:
#   https://issues.apache.org/jira/browse/LOG4NET-370
# At present we merely DISCARD whitespace from the end of messages, but don't attempt to break multiple
# messages into separate lines so that UDP syslog destinations don't have to deal with packet reordering,
# which is a real pain for some people, with an example here:
#  https://redmine.pfsense.org/issues/1938

_RE_RFC3164 = re.compile(r'^<(?P<pri>\d+)>(?P<date>\w{3} [ 0-9][0-9] \d\d:\d\d:\d\d) (?:(?P<host>[^ :\[]+) )?(?P<tag>[^ :\[]+)(?P<rest>[:\[ ].+?)\s*$', re.DOTALL)


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
    3.  Somewhere out here, there is some nerdy OCD guy who will say "But wait, your selector format is so CLOSE
        to the syslog format that you MUST support it with the same semantics or you're going to alienate [me]."  
        Just nipping that in the bud.
    """

    __slots__ = ('_regexes', '_match', 'debugexpr', 'selector')

    def __init__(self, selector, minimum_priority = None):
        self.selector = selector
        self._compile(minimum_priority)

    def reset_minimum_priority(self, minimum_priority = None):
        """
        Recompile the spec using a new minimum priority.  minimum_priority may be None to eliminate
        any such minimum from having an effect and reverting to the exact selectors.
        """
        self._compile(minimum_priority)

    def  _compile(self, minimum_priority):
        self._regexes = []

        pieces = _RE_SPECSEP.split(self.selector)

        # Build the list of negations and positive expressions
        neg = list()
        pos = list()
        for p in pieces:
            self._init_spec(p, neg, pos, minimum_priority)

        if not pos:
            self._buildex("False")
        elif not neg:
            self._buildex(" or ".join(pos))
        else:
            self._buildex("(" + (" and ".join(neg)) + ") and (" + (" or ".join(pos)) + ")")

    def _buildex(self, expr):
        # Perform some quick peepole optimization, then compile
        nexpr = expr.replace("True and ", "").replace(" and True", "")
        nexpr = nexpr.replace("not True", "False").replace(" and ((True))", "")
        nexpr = nexpr.replace("False or ", "").replace(" or False", "")
        self.debugexpr = nexpr
        self._match = eval("lambda s,p,f,g,buf: " + nexpr)

    def _init_spec(self, spec, neg, pos, minpri):
        match = _RE_SPEC.match(spec)

        if not match:
            raise Exception("Invalid log spec syntax: " + spec)

        # Compile an expression to match

        gdict = match.groupdict()

        if gdict['regex'] is not None:
            self._regexes.append(re.compile(gdict['regex'], re.IGNORECASE))
            c1 = 'bool(s._regexes[%d].search(buf))' % (len(self._regexes) - 1)
        elif gdict['prog'] is not None:
            c1 = '(g and "%s" == g.lower())' % gdict['prog'].lower()
        elif gdict['fac'] != '*':
            faclist = [syslog_info.FACILITY_DICT.get(f) for f in gdict.get('fac', '').lower().split(',')]
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
            prival = syslog_info.PRIORITY_DICT.get(pri.lower())
            if prival == None:
                raise Exception("Invalid logging priority, %s: %s" % (pri, spec))
            if minpri is not None and minpri > prival:
                prival = minpri
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
            
    def match(self, msg, prog = None, priority = syslog_info.LOG_ERR, facility = syslog_info.LOG_SYSLOG):
        result = self._match(self, priority, facility, prog, msg)
        #print('MATCH', prog, result, self.debugexpr)
        return result

        
class SyslogServerProtocol(ServerProtocol):

    def datagram_received(self, data, addr):
        self.data_received(data)

    def data_received(self, data):
        try:
            message = data.decode('ascii', 'ignore')
        except Exception as ex:
            self._output("Could not decode SYSLOG record data")
            sys.stdout.flush()
            return

        messages = message.split("\0")

        for m in messages:
            if m:
                self.owner.parse_to_output(m)
        sys.stdout.flush()

class SyslogServer(Server):

    _loglist = list()
    _server = None
    _log_socket = None

    _capture_handler = None     # our capture handler to redirect python logs

    def __init__(self, logsock = "/dev/log", datagram = True, **kwargs):
        super().__init__(**kwargs)

        self._datagram = datagram
        self._log_socket = logsock

        try:
            os.remove(logsock)
        except Exception:
            pass

    def _create_server(self):
        if not self._datagram:
            return self.loop.create_unix_server(
                SyslogServerProtocol.buildProtocol(self), path=self._log_socket)

        # Assure we will be able to bind later
        remove_for_recreate(self._log_socket)

        return self.loop.create_datagram_endpoint(
            SyslogServerProtocol.buildProtocol(self), family=socket.AF_UNIX)

    @asyncio.coroutine
    def server_running(self):
        # Bind the socket if it's a datagram
        if self._datagram:
            transport = self.server[0]
            transport._sock.bind(self._log_socket)
        os.chmod(self._log_socket, 0o777)

    def close(self):
        self.capture_python_logging(False)
        for logitem in self._loglist:
            for m in logitem[1]:
                m.close()
        super().close()
        maybe_remove(self._log_socket)

    def configure(self, config, minimum_priority = None):
        loglist = self._loglist = list()
        lc = config.get_logconfigs()
        for k,v in lc.items():
            matcher = _syslog_spec_matcher(v.selector or '*.*', minimum_priority)
            loglist.append( (matcher, LogOutput.getOutputHandlers(v)) )

    def reset_minimum_priority(self, minimum_priority = None):
        """
        Specifies a new minimum priority for logging.  Recompiles all selectors, so it's best
        to provide this when the configure is done, if possible.
        """
        for m in self._loglist:
            m[0].reset_minimum_priority(minimum_priority)

    def capture_python_logging(self, enable = True):
        if enable:
            if not self._capture_handler:
                self._capture_handler = CustomSysLog(self)
                set_custom_handler(self._capture_handler)
        elif self._capture_handler:
            set_custom_handler(self._capture_handler, False)
            self._capture_handler = None

    def parse_to_output(self, msg):
        # For a description of what a valid syslog line can look like, see:
        # http://www.rsyslog.com/doc/syslog_parsing.html

        match = _RE_RFC3164.match(msg)
        if not match:
            pri = syslog_info.LOG_SYSLOG * 8 + syslog_info.LOG_ERR
            logattrs = { 'tag': '?', 'format_error': True, 'host' : None }
        else:
            logattrs = match.groupdict()
            pri = int(logattrs['pri'])
            logattrs['tag'] = os.path.basename(logattrs['tag'])

        logattrs['raw'] = msg

        self.writeLog(logattrs, priority = pri & 7, facility = pri // 8)

    def writeLog(self, logattrs, priority, facility):
        #print("\nWRITELOG", priority, facility, logattrs)
        for m in self._loglist:
            if m[0].match(logattrs['raw'], logattrs['tag'], priority, facility):
                for logger in m[1]:
                    logger.writeLog(logattrs, priority, facility)

    
class SysLogFormatter(logging.Formatter):
    """
    Handles formatting Python output in the same format as normal syslog daemons.
    """

    def __init__(self, program, pid):

        self.default_program = program
        self.default_pid = pid

        super().__init__('{asctime} {program_name}[{program_pid}]: {message}', style='{')

    def format(self, record):
        if not hasattr(record, 'program_name'):
            setattr(record, 'program_name', self.default_program)
        if not hasattr(record, 'program_pid'):
            setattr(record, 'program_pid', self.default_pid)
        return super().format(record)

    def formatTime(self, record, datefmt=None):
        timestr = strftime('%b %d %H:%M:%S', self.converter(record.created))
        # this may be picky, but people parse syslogs, let's not annoy them
        if timestr[3:5] == ' 0':
            return timestr.replace(' 0', '  ', 1)
        return timestr

        
class CustomSysLog(logging.Handler):
    """
    A custom Python logging class that makes it easy to redirect Python output to our
    internal syslog capture handler.
    """

    PRIORITY_NAMES = {
        "ALERT":    syslog_info.LOG_ALERT,
        "CRIT":     syslog_info.LOG_CRIT,
        "CRITICAL": syslog_info.LOG_CRIT,
        "DEBUG":    syslog_info.LOG_DEBUG,
        "EMERG":    syslog_info.LOG_EMERG,
        "ERR":      syslog_info.LOG_ERR,
        "ERROR":    syslog_info.LOG_ERR,        #  DEPRECATED
        "INFO":     syslog_info.LOG_INFO,
        "NOTICE":   syslog_info.LOG_NOTICE,
        "PANIC":    syslog_info.LOG_EMERG,      #  DEPRECATED
        "WARN":     syslog_info.LOG_WARNING,    #  DEPRECATED
        "WARNING":  syslog_info.LOG_WARNING,
        }

    def __init__(self, owner):
        super().__init__(logging.DEBUG) # enable all levels since we manage filtering ourselves
        self._owner = owner
        self.setFormatter(SysLogFormatter(sys.argv[0] or '-', os.getpid()))

    def emit(self, record):
        facility = getattr(record, '_facility', syslog_info.LOG_LOCAL5)
        priority = self.PRIORITY_NAMES.get(record.levelname, syslog_info.LOG_ERR)

        self._owner.parse_to_output("<{0}>".format(facility << 3 | priority) + self.format(record))
