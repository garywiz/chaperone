import asyncio
from aiocron import crontab
from chaperone.cutil.logging import error, warn, debug, info
from chaperone.cproc.subproc import SubProcess

class CronProcess(SubProcess):

    _cron = None
    _force_enable = False
    _fut_monitor = None

    def __init__(self, service, family=None):
        super().__init__(service, family)
        if not self.interval:
            raise Exception("interval= property missing, required for cron service '{0}'".format(self.name))

        self.note = self.interval
        self._cron = crontab(self.interval, func=self._cron_hit, start=False)

    def default_status(self):
        if self._cron.handle:
            return 'waiting'
        return None

    @asyncio.coroutine
    def start(self, enable = True):
        """
        Takes over startup and sets up our cron loop to handle starts instead.
        """
        self._force_enable = enable
        if not (self.enabled or enable):
            return

        self.enabled = True

        # Start up cron
        self._cron.start()

    @asyncio.coroutine
    def _cron_hit(self):
        if self.enabled:
            if self.running:
                warn("cron service {0} is still running when next interval expired, will not run again", self.name)
            else:
                info("cron service {0} starting", self.name)
                yield from super().start(self._force_enable)

    @asyncio.coroutine
    def stop(self):
        self._cron.stop()
        yield from super().stop()

    @asyncio.coroutine
    def process_started_co(self):
        if self._fut_monitor and not self._fut_monitor.cancelled():
            self._fut_monitor.cancel()
            self._fut_monitor = None

        # We have a successful start.  Monitor this service.

        self._fut_monitor = asyncio.async(self._monitor_service())
        self.add_pending(self._fut_monitor)

    @asyncio.coroutine
    def _monitor_service(self):
        result = yield from self.wait()
        if isinstance(result, int) and result > 0:
            yield from self._abnormal_exit(result)
        else:
            yield from self.reset()
