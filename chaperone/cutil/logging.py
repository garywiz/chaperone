import logging
import os
import sys
import traceback
from time import strftime

from logging.handlers import SysLogHandler
from functools import partial

import chaperone.cutil.syslog_info as syslog_info

logger = logging.getLogger(__name__)

_root_logger = logging.getLogger(None)
_stderr_handler = logging.StreamHandler()
_cur_level = logging.NOTSET

_format = logging.Formatter()
_stderr_handler.setFormatter(_format)

_root_logger.addHandler(_stderr_handler)


def set_log_level(lev):
    global _cur_level

    _cur_level = syslog_info.syslog_to_python_lev(lev)
    logger.setLevel(_cur_level)


def set_custom_handler(handler, enable = True):
    if enable:
        _root_logger.addHandler(handler)
        _root_logger.removeHandler(_stderr_handler)
        logger.setLevel(logging.DEBUG)
    else:
        _root_logger.removeHandler(handler)
        _root_logger.addHandler(_stderr_handler)
        logger.setLevel(_cur_level)


def _versatile_logprint(delegate, fmt, *args, 
                        facility=None, exceptions=False, 
                        program=None, pid=None, **kwargs):
    """
    In addition to standard log formatting, the following two special cases are
    covered:
    1.  If there are no formatting characters (%), then simply concatenate repr() of *args
    2.  If there are '{' formatting arguments, then apply new-style .format using arguments
        provided.

    Additionally, you can pass an exception as the first argument:
    1.  If no other arguments are provided, then the exception message will be the
        log item.
    2.  A traceback will be printed in the case where the logger priority level is set to debug.
    """

    if isinstance(fmt, Exception):
        ex = fmt
        args = list(args)
        if len(args) == 0:
            fmt = [str(ex)]
        else:
            fmt = args.pop(0)
    else:
        ex = None

    if facility is not None or program or pid:
        extra = kwargs['extra'] = {}
        if facility:
            extra['_facility'] = facility
        if program:
            extra['program_name'] = str(program)
        if pid:
            extra['program_pid'] = str(pid)

    
    if ex and (exceptions or logger.level == logging.DEBUG): # use python level here
        trace = "\n" + traceback.format_exc()
    else:
        trace = ""

    if not len(args):
        delegate(fmt, **kwargs)
    elif '%' not in fmt:
        if '{' in fmt:
            delegate('%s', fmt.format(*args) + trace, **kwargs)
        else:
            delegate('%s', " ".join([repr(a) for a in args]) + trace, **kwargs)
    else:
        delegate(fmt, *args, **kwargs)

warn = partial(_versatile_logprint, logger.warning)
info = partial(_versatile_logprint, logger.info)
debug = partial(_versatile_logprint, logger.debug, exceptions=True)
error = partial(_versatile_logprint, logger.error)
