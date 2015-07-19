import asyncio
from chaperone.cproc.subproc import SubProcess

class SimpleProcess(SubProcess):

    _fut_monitor = None

    @asyncio.coroutine
    def process_started_co(self):
        if self._fut_monitor and not self._fut_monitor.cancelled():
            self._fut_monitor.cancel()
            self._fut_monitor = None

        # We wait a short time just to see if the process errors out immediately.  This avoids a retry loop
        # and catches any immediate failures now.

        if self.startup_pause:
            try:
                result = yield from self.timed_wait(self.startup_pause)
            except asyncio.TimeoutError:
                result = None
            if result is not None and not result.normal_exit:
                if self.ignore_failures:
                    warn("{0} (ignored) failure on start-up with result '{1}'".format(self.name, result))
                else:
                    raise Exception("{0} failed on start-up with result '{1}'".format(self.name, result))

        # If there is a pidfile, sit here and wait for a bit
        yield from self.wait_for_pidfile()

        # We have a successful start.  Monitor this service.

        self._fut_monitor = asyncio.async(self._monitor_service())
        self.add_pending(self._fut_monitor)

    @asyncio.coroutine
    def _monitor_service(self):
        result = yield from self.wait()
        if isinstance(result, int) and result > 0:
            yield from self._abnormal_exit(result)
