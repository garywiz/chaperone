import asyncio
import socket
import re
from functools import partial

from chaperone.cutil.errors import ChProcessError
from chaperone.cutil.proc import ProcStatus
from chaperone.cutil.notify import NotifyListener
from chaperone.cproc.subproc import SubProcess

class NotifyProcess(SubProcess):

    process_timeout = 300
    defer_exit_kills = True

    _fut_monitor = None
    _listener = None
    _ready_event = None
    
    def _close_listener(self):
        if self._listener:
            self._listener.close()
            self._listener = None

    @asyncio.coroutine
    def process_prepare_co(self, environ):
        if not self._listener:
            self._listener = NotifyListener('@/chaperone/' + self.service.name,
                                            onNotify = self._notify_received)
            yield from self._listener.run()

        environ['NOTIFY_SOCKET'] = self._listener.socket_name

        # Now, set up an event which is triggered upon ready
        self._ready_event = asyncio.Event()

    def _notify_timeout(self):
        service = self.service
        message = "notify service '{1}' did not receive ready notification after {2} second(s), {3}".format(
            service.type,
            service.name, self.process_timeout, 
            "proceeding due to 'ignore_failures=True'" if service.ignore_failures else
            "terminating due to 'ignore_failures=False'")
        if not service.ignore_failures:
            self.terminate()
        raise ChProcessError(message)

    @asyncio.coroutine
    def reset(self, dependents = False, enable = False, restarts_ok = False):
        yield from super().reset(dependents, enable, restarts_ok)
        self._close_listener()

    @asyncio.coroutine
    def final_stop(self):
        yield from super().final_stop()
        self._close_listener()

    @asyncio.coroutine
    def process_started_co(self):
        if self._fut_monitor and not self._fut_monitor.cancelled():
            self._fut_monitor.cancel()
            self._fut_monitor = None

        yield from self.do_startup_pause()

        self._fut_monitor = asyncio.async(self._monitor_service())
        self.add_pending(self._fut_monitor)

        if self._ready_event:
            try:
                if not self.process_timeout:
                    raise asyncio.TimeoutError()
                yield from asyncio.wait_for(self._ready_event.wait(), self.process_timeout)
            except asyncio.TimeoutError:
                self._ready_event = None
                self._notify_timeout()
            else:
                if self._ready_event:
                    self._ready_event = None
                    rc = self.returncode
                    if rc is not None and not rc.normal_exit:
                        if self.ignore_failures:
                            warn("{0} (ignored) failure on start-up with result '{1}'".format(self.name, rc))
                        else:
                            raise ChProcessError("{0} failed with reported error {1}".format(self.name, rc), resultcode = rc)

    @asyncio.coroutine
    def _monitor_service(self):
        """
        We only care about errors here.  The rest is dealt with by having notifications
        occur.
        """
        result = yield from self.wait()
        if isinstance(result, int) and result > 0:
            self._setready()    # simulate ready
            self._ready_event = None
            self._close_listener()
            yield from self._abnormal_exit(result)
            
    def _notify_received(self, which, var, value):
        callfunc = getattr(self, "notify_" + var.upper(), None)
        #print("NOTIFY RECEIVED", var, value)
        if callfunc:
            callfunc(value)

    def _setready(self):
        if self._ready_event:
            self._ready_event.set()
            return True
        return False

    def notify_MAINPID(self, value):
        try:
            pid = int(value)
        except ValueError:
            self.logdebug("{0} got MAINPID={1}, but not a valid pid#", self.name, value)
            return
        self.pid = pid

    def notify_BUSERROR(self, value):
        code = ProcStatus(value)
        if not self._setready():
            self.process_exit(code)
        else:
            self.returncode = code

    def notify_ERRNO(self, value):
        try:
            intval = int(value)
        except ValueError:
            self.logdebug("{0} got ERROR={1}, not a valid error code", self.name, value)
            return
        code = ProcStatus(intval << 8)
        if not self._setready():
            self.process_exit(code)
        else:
            self.returncode = code

    def notify_READY(self, value):
        if value == "1":
            self._setready()

    def notify_STATUS(self, value):
        self.note = value

    @property
    def status(self):
        if self._ready_event:
            return "activating"
        return super().status
