import logging
from logging.handlers import SysLogHandler

# Copy all syslog levels
for k,v in SysLogHandler.__dict__.items():
    if k.startswith('LOG_'):
        globals()[k] = v
    
FACILITY = ('kern', 'user', 'mail', 'daemon', 'auth', 'syslog', 'lpr', 'news', 'uucp', 'cron', 'authpriv',
             'ftp', 'ntp', 'audit', 'alert', 'altcron', 'local0', 'local1', 'local2', 'local3', 'local4',
             'local5', 'local6', 'local7')
FACILITY_DICT = {FACILITY[i]:i for i in range(len(FACILITY))}

PRIORITY = ('emerg', 'alert', 'crit', 'err', 'warn', 'notice', 'info', 'debug')
PRIORITY_DICT = {PRIORITY[i]:i for i in range(len(PRIORITY))}

PRIORITY_DICT['warning'] = PRIORITY_DICT['warn']
PRIORITY_DICT['error'] = PRIORITY_DICT['err']

# Python equivalent for PRIORITY settings
PRIORITY_PYTHON = (logging.CRITICAL, logging.CRITICAL, logging.CRITICAL, logging.ERROR,
                   logging.WARNING, logging.INFO, logging.INFO, logging.DEBUG)

def get_syslog_info(facility, priority):
    try:
        f = FACILITY[facility]
    except IndexError:
        f = '?'
    try:
        return f + '.' + PRIORITY[priority]
    except IndexError:
        return f + '.?'

    
def syslog_to_python_lev(lev):
    if lev < 0 or lev > len(PRIORITY):
        return logging.DEBUG
    return PRIORITY_PYTHON[lev]
