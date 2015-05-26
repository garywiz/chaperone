"""
Interactive command tool for chaperone

Usage:
    telchap <command> [<args> ...]
"""

import sys
import os
import asyncio
import shlex
from docopt import docopt

from chaperone.cproc.client import CommandClient

def main_entry():
    options = docopt(__doc__, options_first=True)
    try:
        result = CommandClient.sendCommand(options['<command>'] + " " + " ".join([shlex.quote(a) for a in options['<args>']]))
    except (ConnectionRefusedError, FileNotFoundError) as ex:
        result = "chaperone does not seem to be listening, is it running?\n(Error is: {0})".format(ex)

    print(result)

