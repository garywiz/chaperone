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
# 
# Minimal support is included for nested parenthesis when operators are used, as in:
#      $(VAR:-$(VAL))
# However, more levels of nesting are not supported and will cause substitutions to be unrecognised.

_RE_ENVVAR = re.compile(r'\$(?:\([^=\(]+(?::(?:[^=\(\)]|\([^=\)]+\))+)?\)|{[^={]+(?::(?:[^={}]|{[^=}]+})+)?})')

# Parsing for operators within expansions
_RE_OPERS = re.compile(r'^([^:]+):([-+])(.*)$')

class Environment(lazydict):

    def __init__(self, from_env = os.environ, config = None):
        super().__init__()
        if not config:
            if from_env:
                self.update(from_env)
        else:
            inherit = config.get('env_inherit')
            if inherit and from_env:
                self.update({k:v for k,v in from_env.items() if any([fnmatch(k,pat) for pat in inherit])})
            add = config.get('env_set')
            if add:
                self.update(add)
            unset = config.get('env_unset')
            if unset:
                for s in unset:
                    self.pop(s, None)

    def _elookup(self, match):
        whole = match.group(0)
        return self.get(whole[2:-1], whole)

    def expand(self, instr):
        """
        Expands an input string by replacing environment variables of the form ${ENV} or $(ENV).
        If an expansion is not found, the substituion is ignored and the original reference remains.

        Two bash features are employed to allow tests:
            $(VAR:-sub)    Expands to sub if VAR not defined
            $(VAR:+sub)    Expands to sub if VAR IS defined
        """
        if not isinstance(instr, str):
            return instr
        return _RE_ENVVAR.sub(self._elookup, instr)

    def expanded(self):
        """
        Does a recursive expansion on all variables until there are no matches.  Circular recursion
        is halted rather than reported as an error.
        """
        result = Environment(None) 
        for k in sorted(self.keys()): # sorted so outcome is deterministic
            self._expand_into(k, result)
        return result

    def _expand_into(self, k, result, default = None):
        match = _RE_OPERS.match(k)
        use_repl = None
        val = None

        if not match:
            if k in result:
                return result[k]
            if k not in self:
                return default
            val = self[k]
        else:
            (k, oper, repl) = match.groups()
            # Handle both :- and :+
            if (oper == '-' and k not in self) or (oper == '+' and k in self):
                use_repl = repl
            elif k not in self:
                return ''
            elif k in result:
                return result[k]
            else:
                val = self[k]

        if use_repl is not None:
            val = _RE_ENVVAR.sub(lambda m: self._expand_into(m.group(0)[2:-1], result, m.group(0)), use_repl)
        else:
            # Looks odd, but needed to seed the result to assure we ignore recursion later
            result[k] = val
            val = result[k] = _RE_ENVVAR.sub(lambda m: self._expand_into(m.group(0)[2:-1], result, m.group(0)), val)

        return val
        

def maybe_remove(fn):
    """
    Tries to remove a file but ignores a FileNotFoundError.
    """
    try:
        os.remove(fn)
    except FileNotFoundError:
        pass

