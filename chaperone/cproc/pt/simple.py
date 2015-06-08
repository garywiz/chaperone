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
            if result is not None and result > 0:
                raise Exception("{0} failed on start-up during {1}sec grace period".format(self.name, self.startup_pause))
                yield from self._abnormal_exit(result)

        # We have a successful start.  Monitor this service.

        self._fut_monitor = asyncio.async(self._monitor_service())
        self.add_pending(self._fut_monitor)

    @asyncio.coroutine
    def _monitor_service(self):
        result = yield from self.wait()
        if isinstance(result, int) and result > 0:
            yield from self._abnormal_exit(result)
