import asyncio
from chaperone.cproc.subproc import SubProcess

class SimpleProcess(SubProcess):

    _fut_monitor = None

    @asyncio.coroutine
    def process_started_co(self):
        if self._fut_monitor:
            self._fut_monitor.cancel()
            self._fut_monitor = None
        self._fut_monitor = asyncio.async(self._monitor_service())
        self.add_pending(self._fut_monitor)

    @asyncio.coroutine
    def _monitor_service(self):
        result = yield from self.wait()
        if isinstance(result, int) and result > 0:
            yield from self._abnormal_exit(result)
