"""
Systemd notify tool (compatible with systemd-notify)

Usage:
    sdnotify [options] [VARIABLE=VALUE ...]

Options:
    --pid PID        Inform chaperone/systemd of MAINPID
                     (must say --pid=self if you want the programs PID)
    --status=STATUS  Inform chaperone/systemd of status information
    --ready          Send the ready signal (READY=1)
    --booted         Indicate whether we were booted with systemd.
                     (Note: Always indicates 'no', exit status 1.)
    --ignore         Silently ignore inability to send notifications.
                     (Always ignored if NOTIFY_SOCKET is not set.)

All of the above specified will be sent in the order given above, then
any VARIABLE=VALUE pairs will be sent.

This is provided by Chaperone as an alternative to systemd-notify for distros
which may not have one.
"""

# perform any patches first
import chaperone.cutil.patches

# regular code begins
import sys
import os
import socket
from docopt import docopt

from chaperone.cproc.version import VERSION_MESSAGE

def _mkabstract(socket_name):
    if socket_name.startswith('@'):
        socket_name = '\0%s' % socket_name[1:]
    return socket_name


def do_notify(msg):
    notify_socket = os.getenv('NOTIFY_SOCKET')
    if notify_socket:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            sock.connect(_mkabstract(notify_socket))
            sock.sendall(msg.encode())
        except EnvironmentError as ex:
            raise Exception("Systemd notification failed: " + str(ex))
        finally:
            sock.close()

def main_entry():
    options = docopt(__doc__, version=VERSION_MESSAGE)

    mlist = list()

    if options['--pid']:
        pid = options['--pid']
        if pid == 'self':
            mlist.append("MAINPID="+str(os.getpid()))
        else:
            try:
                pidval = int(pid)
            except ValueError:
                print("error: not a valid PID '{0}'".format(pid))
                exit(1)
            mlist.append("MAINPID="+str(pid))
    
    if options['--status']:
        mlist.append("STATUS=" + options['--status'])

    if options['--ready']:
        mlist.append("READY=1")

    for vv in options['VARIABLE=VALUE']:
        vvs = vv.split('=')
        if len(vvs) != 2:
            print("error: not a valid format for VARIABLE=VALUE, '{0}'".format(vv))
            exit(1)
        mlist.append("{0}={1}".format(vvs[0].upper(), vvs[1]))

    for msg in mlist:
        try:
            do_notify(msg)
        except Exception as ex:
            if not options['--ignore']:
                print("error: could not send sd_notify message, " + str(ex))
                exit(1)
    
    if options['--booted']:
        exit(1)
