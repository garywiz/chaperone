import asyncio
from chaperone.cproc.subproc import SubProcess

class OneshotProcess(SubProcess):

    process_timeout = 60.0       # default for a oneshot is 90 seconds

    @asyncio.coroutine
    def process_started_co(self):
        yield from self.timed_wait(self.process_timeout, self._exit_timeout)
        
    def _exit_timeout(self):
        service = self.service
        message = "oneshot service '{1}' did not exit after {2} second(s), {3}".format(
            service.type,
            service.name, self.process_timeout, 
            "proceeding due to 'ignore_failures=True'" if service.ignore_failures else
            "terminating due to 'ignore_failures=False'")
        if not service.ignore_failures:
            self.terminate()
        raise Exception(message)
