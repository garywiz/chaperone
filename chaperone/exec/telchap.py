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
    result = CommandClient.sendCommand(options['<command>'] + " " + " ".join([shlex.quote(a) for a in options['<args>']]))
