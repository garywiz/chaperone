import os
from chaperone.cutil.misc import get_signal_name

class ProcStatus(int):

    _other_error = None

    def __new__(cls, val):
        try:
            intval = int(val)
        except ValueError:
            rval = int.__new__(cls, 0)
            rval._other_error = str(val)
            return rval

        return int.__new__(cls, intval)

    @property
    def exited(self):
        return os.WIFEXITED(self)

    @property
    def signaled(self):
        return os.WIFSIGNALED(self)

    @property
    def stopped(self):
        return os.WIFSTOPPED(self)

    @property
    def continued(self):
        return os.WIFCONTINUED(self)

    @property
    def exit_status(self):
        return (os.WIFEXITED(self) or None) and os.WEXITSTATUS(self)

    @property
    def normal_exit(self):
        return self.exit_status == 0 and not (self.signaled or self.stopped) and not self._other_error

    @property
    def exit_message(self):
        es = self.exit_status
        if es is not None:
            return os.strerror(es)
        return None
        
    @property
    def signal(self):
        if os.WIFSTOPPED(self):
            return os.WSTOPSIG(self)
        if os.WIFSIGNALED(self):
            return os.WTERMSIG(self)
        return None

    @property
    def briefly(self):
        if self.signaled or self.stopped:
            return get_signal_name(self.signal)
        if self.exited:
            return "exit({0})".format(self.exit_status)
        return '?'

    def __format__(self, spec):
        if spec:
            return int.__format__(self, spec)
        msg = "<ProcStatus"
        if self.exited:
            msg += " exit_status={0}".format(self.exit_status)
        if self.signaled:
            msg += " signal=%d" % self.signal
        if self.stopped:
            msg += " stoppped=%d" % self.signal
        return msg + ">"
