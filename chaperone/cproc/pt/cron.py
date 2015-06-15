import asyncio
from aiocron import crontab
from chaperone.cutil.logging import error, warn, debug, info
from chaperone.cutil.syslog_info import LOG_CRON
from chaperone.cproc.subproc import SubProcess
from chaperone.cutil.errors import ChParameterError

_CRON_SPECIALS = {
    '@yearly':      '0 0 1 1 *',
    '@annually':    '0 0 1 1 *',
    '@monthly':     '0 0 1 * *',
    '@weekly':      '0 0 * * 0',
    '@daily':       '0 0 * * *',
    '@hourly':      '0 * * * *',
}

class CronProcess(SubProcess):

    syslog_facility = LOG_CRON

    _cron = None
    _fut_monitor = None

    def __init__(self, service, family=None):
        super().__init__(service, family)
        if not self.interval:
            raise Exception("interval= property missing, required for cron service '{0}'".format(self.name))

        # Support specials with or without the @
        real_interval = _CRON_SPECIALS.get(self.interval) or _CRON_SPECIALS.get('@'+self.interval) or self.interval

        # make a status note
        self.note = "{0} ({1})".format(self.interval, real_interval) if self.interval != real_interval else real_interval

        self._cron = crontab(real_interval, func=self._cron_hit, start=False)

    def default_status(self):
        if self._cron.handle:
            return 'waiting'
        return None

    @asyncio.coroutine
    def start(self):
        """
        Takes over startup and sets up our cron loop to handle starts instead.
        """
        if not self.enabled:
            return

        # Start up cron
        try:
            self._cron.start()
        except:
            raise ChParameterError("not a valid cron interval specification, '{0}'".format(self.interval))

    @asyncio.coroutine
    def _cron_hit(self):
        if self.enabled:
            if self.running:
                warn("cron service {0} is still running when next interval expired, will not run again", self.name)
            else:
                info("cron service {0} starting", self.name)
                yield from super().start()

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
