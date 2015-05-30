import asyncio
from chaperone.cproc.subproc import SubProcess

class SimpleProcess(SubProcess):

    _fut_monitor = None

    @asyncio.coroutine
    def process_started_co(self):
        self._fut_monitor = asyncio.async(self._monitor_service())

    @asyncio.coroutine
    def _monitor_service(self):
        result = yield from self.wait()
        if isinstance(result, int) and result > 0:
            yield from self._abnormal_exit(result)

