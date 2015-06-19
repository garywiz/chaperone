import re
import os
from fnmatch import fnmatch

from chaperone.cutil.misc import lookup_user, lazydict

##
## ALL chaperone configuration variables defined here for easy reference

ENV_CONFIG_DIR       = '_CHAP_CONFIG_DIR'          # directory which CONTAINS the config file *or* directory
ENV_INTERACTIVE      = '_CHAP_INTERACTIVE'         # if this session is interactive (has a ptty attached)
ENV_SERVICE          = '_CHAP_SERVICE'             # name of the current service
ENV_TASK_MODE        = '_CHAP_TASK_MODE'           # if we are running in --task mode

ENV_CHAP_OPTIONS     = '_CHAP_OPTIONS'             # Preset before chaperone runs to set default options

# Technically IEEE 1003.1-2001 states env vars can contain anything except '=' and NUL but we need to
# obviously exclude the terminator!
# 
# Minimal support is included for nested parenthesis when operators are used, as in:
#      $(VAR:-$(VAL))
# However, more levels of nesting are not supported and will cause substitutions to be unrecognised.

_RE_ENVVAR = re.compile(r'\$(?:\([^=\(\)]+(?::(?:[^=\(\)]|\([^=\)]+\))+)?\)|{[^={}]+(?::(?:[^={}]|{[^=}]+})+)?})')

# Parsing for operators within expansions
_RE_OPERS = re.compile(r'^([^:]+):([-+])(.*)$')

_DICT_CONST = dict()            # a dict we must never change, just an optimisation

class Environment(lazydict):

    uid = None
    gid = None

    # This is a cached version of this environment, expanded
    _expanded = None

    # The _shadow Environment contains a pointer to the environment which contained
    # the LAST active value for each env_set item so that we can deal with self-referential
    # cases like:
    #    'PATH': '/usr/local:$(PATH)'
    _shadow = None

    def __init__(self, from_env = os.environ, config = None, uid = None, gid = None):
        """
        Create a new environment.  An environment may have a user associated with it.  If so,
        then it will be pre-populated with the user's HOME, USER and LOGNAME so that expansions
        can reference these.
        """
        super().__init__()

        #print("\n--ENV INIT", config, uid, from_env, from_env and getattr(from_env, 'uid', None))

        userenv = dict()

        # Inherit user from passed-in environment
        self._shadow = getattr(from_env, '_shadow', None)
        shadow = None           # we don't bother to recreate this in any complex fashion unless we need to

        if uid is None:
            self.uid = getattr(from_env, 'uid', self.uid)
            self.gid = getattr(from_env, 'gid', self.gid)
        else:
            pwrec = lookup_user(uid, gid)
            self.uid = pwrec.pw_uid
            self.gid = pwrec.pw_gid
            userenv['HOME'] = pwrec.pw_dir
            userenv['USER'] = userenv['LOGNAME'] = pwrec.pw_name

        if not config:
            if from_env:
                self.update(from_env)
            self.update(userenv)
        else:
            inherit = config.get('env_inherit') or ['*']
            if inherit and from_env:
                self.update({k:v for k,v in from_env.items() if any([fnmatch(k,pat) for pat in inherit])})
            self.update(userenv)

            add = config.get('env_set')
            unset = config.get('env_unset')

            if add or unset:
                self._shadow = shadow = (getattr(self, '_shadow') or _DICT_CONST).copy()

            if add:
                for k,v in add.items():
                    if from_env and k in from_env:
                        shadow[k] = from_env # we keep track of the environment where the predecessor originated
                    self[k] = v
            if unset:
                patmatch = lambda p: any([fnmatch(p,pat) for pat in unset])
                for delkey in [k for k in self.keys() if patmatch(k)]:
                    del self[delkey]
                for delkey in [k for k in shadow.keys() if patmatch(k)]:
                    del shadow[delkey]

        #print('   DONE (.uid={0}): {1}\n'.format(self.uid, self))

    def _get_shadow_environment(self, var):
        """
        Returns the environment where var  existed before the specified variable was set, even
        that occurred long ago.  Delays expansion of the parent environment until this point,
        since it is only rarely that self-referential environment variables need to consult the shadow.
        """
        try:
            shadow = self._shadow[var]
        except (TypeError, KeyError):
            return None

        try:
            return shadow.expanded()
        except AttributeError:
            pass

        # Note shadow may be None at this point, or a dict()
        self._shadow[var] = shadow = Environment(shadow)

        return shadow.expanded()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._expanded = None

    def __delitem__(self, key):
        super().__delitem__(key)
        self._expanded = None

    def clear(self):
        super().clear()
        self._expanded = None

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

        If a list is provided instead of a string, a list will be returned with each item
        separately expanded.
        """
        if isinstance(instr, list):
            return [self.expand(item) for item in instr]
        if not isinstance(instr, str):
            return instr
        return _RE_ENVVAR.sub(lambda m: self._expand_into(m.group(0)[2:-1], self, m.group(0)), instr)

    def expand_attributes(self, obj, *args):
        """
        Given an object and a set of attributes, expands each and replaces the originals with
        expanded versions.   Implicitly expands the environment to assure all variable substitutions
        occur correctly.
        """
        explist = (k for k in args if hasattr(obj, k))
        if not explist:
            return

        env = self.expanded()
        for attr in explist:
            setattr(obj, attr, env.expand(getattr(obj, attr)))
            
    def expanded(self):
        """
        Does a recursive expansion on all variables until there are no matches.  Circular recursion
        is halted rather than reported as an error.  Returns a version of this environment
        which has been expanded.  Asking an expanded() copy for another expanded() copy returns self
        unless the expanded copy has been modified.
        """
        if self._expanded is not None:
            return self._expanded

        result = Environment(None) 
        for k in sorted(self.keys()): # sorted so outcome is deterministic
            self._expand_into(k, result)

        # Copy uid after we expand, since any user information is already present in our
        # own environment.
        result.uid = self.uid
        result.gid = self.gid
        result._shadow = self._shadow

        # Cache a copy, but also tell the cached copy that it's expanded cached copy is itself.
        result._expanded = result
        self._expanded = result

        return result

    def _expand_into(self, k, result, default = None, parent = None):
        match = _RE_OPERS.match(k)
        use_repl = None
        val = None

        # We are the primary source of values unless we discover a self-referential
        # variable later.
        primary = self    

        if not match:
            if parent == k:     # self-referential
                primary = self._get_shadow_environment(k)
                val = (primary and primary.get(k, '')) or '' # special case where we return nothing
            else:
                if k in result:
                    return result[k]
                if k not in primary:
                    return default
                val = primary[k]
        else:
            (k, oper, repl) = match.groups()
            if parent == k:     # self-referential
                primary = self._get_shadow_environment(k) or _DICT_CONST
            # Handle both :- and :+
            if (oper == '-' and k not in primary) or (oper == '+' and k in primary):
                use_repl = repl
                k = None        # this is not a self-referential forward reference
            elif k not in primary:
                return ''
            elif k in result:
                return result[k]
            else:
                val = primary[k]

        recurse = lambda m: self._expand_into(m.group(0)[2:-1], result, m.group(0), k)

        if use_repl is not None:
            val = _RE_ENVVAR.sub(recurse, use_repl)
        elif result is self:
            val = _RE_ENVVAR.sub(recurse, val)
        else:
            # Looks odd, but needed to seed the result to assure we ignore recursion later
            result[k] = val
            val = result[k] = _RE_ENVVAR.sub(recurse, val)

        return val
    
    def get_public_environment(self):
        """
        Public variables are those which are exported to the application and do NOT start with an
        underscore.  All underscore names will be kept private.
        """
        newenv = self.expanded().copy()
    
        # collect private or blanks, then delete them
        delkeys = [k for k in newenv.keys() if k.startswith('_') or newenv[k] in (None, '')]
        if delkeys:
            for k in delkeys:
                del newenv[k]

        return newenv

