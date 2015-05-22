import re
import os
import copy
from fnmatch import fnmatch

class lazydict(dict):

    __slots__ = ()              # create no __dict__ overhead for a pure dict subclass

    def __init__(self, *args):
        """
        Allow a series of iterables as an initializer.
        """
        super().__init__()
        for a in args:
            self.update(a)

    def get(self, key, default = None):
        """
        A very of get() that accepts lazy defaults.  You can provide a callable which will be invoked only
        if necessary.
        """
        if key in self:
            return self[key]

        return default() if callable(default) else default
    
    def setdefault(self, key, default = None):
        """
        A version of setdefault that works the way it should, by having a lambda that is executed
        only in the case where the item does not exist.
        """
        if key in self:
            return self[key]
        self[key] = value = default() if callable(default) else default

        return value

    def deepcopy(self):
        return copy.deepcopy(self)


# Technically IEEE 1003.1-2001 states env vars can contain anything except '=' and NUL but we need to
# obviously exclude the terminator!
_RE_ENVVAR = re.compile(r'\$(?:\([^\)=]+\)|{[^\)=]+})')

class Environment(lazydict):

    def __init__(self, config, from_env = os.environ):
        super().__init__()
        if not config:
            self.update(from_env)
        else:
            inherit = config.get('env_inherit')
            if inherit:
                self.update({k:v for k,v in from_env.items() if any([fnmatch(k,pat) for pat in inherit])})
            add = config.get('env_add')
            if add:
                self.update(add)

    def _elookup(self, match):
        whole = match.group(0)
        return self.get(whole[2:-1], whole)

    def expand(self, instr):
        """
        Expands an input string by replacing environment variables of the form ${ENV} or $(ENV).
        If an expansion is not found, the substituion is ignored and the original reference remains.
        """
        if not isinstance(instr, str):
            return instr
        return _RE_ENVVAR.sub(self._elookup, instr)
