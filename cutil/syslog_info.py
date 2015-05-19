
FACILITY = ('kern', 'user', 'mail', 'daemon', 'auth', 'syslog', 'lpr', 'news', 'uucp', 'clock', 'authpriv',
             'ftp', 'ntp', 'audit', 'alert', 'cron', 'local0', 'local1', 'local2', 'local3', 'local4',
             'local5', 'local6', 'local7')
FACILITY_DICT = {FACILITY[i]:i for i in range(len(FACILITY))}

PRIORITY = ('emerg', 'alert', 'crit', 'err', 'warn', 'notice', 'info', 'debug')
PRIORITY_DICT = {PRIORITY[i]:i for i in range(len(PRIORITY))}

PRIORITY_DICT['warning'] = PRIORITY_DICT['warn']
PRIORITY_DICT['error'] = PRIORITY_DICT['err']

def get_syslog_info(facility, priority):
    try:
        f = FACILITY[facility]
    except IndexError:
        f = '?'
    try:
        return f + '.' + PRIORITY[priority]
    except IndexError:
        return f + '.?'

    
