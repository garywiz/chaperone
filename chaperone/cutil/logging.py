import logging
import os
import sys

from logging.handlers import SysLogHandler
from functools import partial

logger = logging.getLogger(__name__)

_root_logger = logging.getLogger(None)
_stderr_handler = logging.StreamHandler()
_syslog_handler = None

_format = logging.Formatter()
_stderr_handler.setFormatter(_format)

_root_logger.addHandler(_stderr_handler)

def set_python_log_level(lev):
    logger.setLevel(lev)

def enable_syslog_handler():
    global _syslog_handler
    _syslog_handler = SysLogHandler('/dev/log')
    sf = logging.Formatter('{asctime} %s[%d]: {message}' % (sys.argv[0] or '-', os.getpid()), 
                           datefmt="%b %d %H:%M:%S", style='{')
    _syslog_handler.setFormatter(sf)
    _root_logger.addHandler(_syslog_handler)
    _root_logger.removeHandler(_stderr_handler)

def _versatile_logprint(delegate, fmt, *args, **kwargs):
    """
    In addition to standard log formatting, the following two special cases are
    covered:
    1.  If there are no formatting characters (%), then simply concatenate repr() of *args
    2.  If there are '{' formatting arguments, then apply new-style .format using arguments
        provided.
    """
    if not len(args):
        delegate(fmt, **kwargs)
    elif '%' not in fmt:
        if '{' in fmt:
            delegate('%s', fmt.format(*args))
        else:
            delegate('%s', " ".join([repr(a) for a in args]))
    else:
        delegate(fmt, *args, **kwargs)

warn = partial(_versatile_logprint, logger.warning)
info = partial(_versatile_logprint, logger.info)
debug = partial(_versatile_logprint, logger.debug)
error = partial(_versatile_logprint, logger.error)
