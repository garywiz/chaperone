import re
import os
import subprocess
from fnmatch import fnmatch

from chaperone.cutil.logging import error, debug, warn
from chaperone.cutil.misc import lookup_user, lazydict
from chaperone.cutil.errors import ChVariableError, ChParameterError

##
## ALL chaperone configuration variables defined here for easy reference

ENV_CONFIG_DIR       = '_CHAP_CONFIG_DIR'          # directory which CONTAINS the config file *or* directory
ENV_INTERACTIVE      = '_CHAP_INTERACTIVE'         # if this session is interactive (has a ptty attached)
ENV_SERVICE          = '_CHAP_SERVICE'             # name of the current service
ENV_SERIAL           = '_CHAP_SERVICE_SERIAL'      # Contains a monotonic unique serial number for each started service, starting with 1
ENV_SERVTIME         = '_CHAP_SERVICE_TIME'        # Timestamp when service started running
ENV_TASK_MODE        = '_CHAP_TASK_MODE'           # if we are running in --task mode

ENV_CHAP_OPTIONS     = '_CHAP_OPTIONS'             # Preset before chaperone runs to set default options

# Technically IEEE 1003.1-2001 states env vars can contain anything except '=' and NUL but we need to
# obviously exclude the terminator!
# 
# Minimal support is included for nested parenthesis when operators are used, as in:
#      $(VAR:-$(VAL))
# However, more levels of nesting are not supported and will cause substitutions to be unrecognised.

_RE_BACKTICK = re.compile(r'`([^`]+)`', re.DOTALL)

# Parsing for operators within expansions
_RE_OPERS = re.compile(r'^(?:([^:]+):([-|?+_/])(.*)|(`.+`))$', re.DOTALL)
_RE_SLASHOP = re.compile(r'^(.+)(?<!\\)/(.*)(?<!\\)/([i]*)$', re.DOTALL)
_RE_BAREBAR = re.compile(r'(?<!\\)\|')

_DICT_CONST = dict()            # a dict we must never change, just an optimisation


class EnvScanner:
    """
    A class which performs basic parsing of strings containing environment variables,
    with support for nested constructs.  No, you can't do this with regular expressions.
    """

    open_expansion = '({'
    quotes = "\"`";             # we assume that single quotes may not be paired.  This prevents contractions
                                # from inhibiting expansions
    escape = "\\"
    variable_id = '$'
    nestlist = ')]}([{'         # arranged so that ending delimiters are first and positions match

    def __init__(self, variable_id = None, open_expansion = None):
        if variable_id:
            self.variable_id = variable_id
        if open_expansion:
            self.open_expansion = open_expansion
        self._RE_START = re.compile('(' + re.escape(self.escape) + ')?' + re.escape(self.variable_id) + 
                                    '(' + ('|'.join([re.escape(d[0]) for d in self.open_expansion])) + ')')
        
    def parse(self, buf, func, *args):
        """
        Parses buffer and expands variables using func(exp_data, exp_whole, *args)
        where, given $(xxx):
           exp_data is the actual contents of the variable, so 'xxx'
           exp_whole is the entire expression, so '$(xxx)'
        """
        
        # Quickly return if we don't have any expansions

        st = self._RE_START
        match = st.search(buf)
        if not match:
            return buf

        # Now do the hard work

        results = []
        buflen = len(buf)
        startpos = 0

        nestlen = len(self.nestlist)
        halfnest = nestlen // 2 # delims < halfnest are paired closing delimiters
        lookfor = self.nestlist + self.quotes

        while match:

            pos = match.start()
            if pos != startpos:
                results.append(buf[startpos:pos])

            if match.group(1):
                # just escape the value
                results.append(self.variable_id)
                startpos = match.start(2)
                pos = buflen
                match = st.search(buf, startpos)
            else:
                pos = match.start(2)
                startpos = pos + 1

                # Init the stack.  We know a push will come first
                stack = []

                # find the very end of the area, counting nested items
                while True:
                    ci = lookfor.find(buf[pos])
                    #print(pos, buf[pos], ci, stack, results)
                    if ci >= 0:
                        s0 = (not stack and -1) or stack[-1]
                        if s0 == ci:
                            stack.pop()
                            # We are totally done if the stack is empty
                            if not stack:
                                results.append(func(buf[startpos:pos], buf[match.start():pos+1], *args))
                                startpos = pos + 1
                                pos = buflen
                                match = st.search(buf, startpos)
                                break
                        elif ci >= halfnest and s0 < nestlen: # don't match within quotes
                            # at matching end delimiter, which may be nesting, or not
                            stack.append(ci-halfnest if ci < nestlen else ci)
                    pos += 1
                    if pos >= buflen:
                        startpos = match.start(0)
                        match = None
                        break
        
        if pos != startpos:
            results.append(buf[startpos:pos])

        return ''.join(results)


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

    # A class variable to keep track of backtick expansions so we don't do them more than once
    _cls_btcache = dict()
    _cls_use_btcache = True     # if shell expansions should be cached once or re-executed
    _cls_backtick = True        # indicates backticks are enabled

    # Default scanner
    _cls_scan = EnvScanner()

    @classmethod
    def set_parse_parameters(cls, variable_id = None, open_expansion = None):
        cls._cls_scan = EnvScanner(variable_id, open_expansion)

    @classmethod
    def set_backtick_expansion(cls, enabled = True, cache = True):
        cls._cls_backtick = enabled
        cls._cls_use_btcache = cache

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
        return self._cls_scan.parse(instr, self._expand_into, self)

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
            self._expand_into(k, None, result, k)

        # Copy uid after we expand, since any user information is already present in our
        # own environment.
        result.uid = self.uid
        result.gid = self.gid
        result._shadow = self._shadow

        # Cache a copy, but also tell the cached copy that it's expanded cached copy is itself.
        result._expanded = result
        self._expanded = result

        return result

    def _expand_into(self, k, wholematch, result, parent = None):
        """
        Internal workhorse that expands the variable 'k' INTO the given result dictionary.
        The result dictionary will conatin the expanded values.   The result dictionary is
        also a cache for nested and recursive environment expansion.

        'wholematch' is None unless called from in an re.sub() (or similar context).
                 If set, it indicates the complete expansion expression, including adornments.
                 It is used as the default expansion when a variable is not defined.
        'parent' is the name of the variable which was being expanded in the last
                 recursion, to catch the special case of self-referential variables.
        """

        match = _RE_OPERS.match(k)

        if match:
            (k, oper, repl, backtick) = match.groups()


        # Phase 1: Base variable value.  Start by determining the value of variable
        #          'k' within the current context.  

        # 1A: We have a backtick shortcut, such as $(`date`)
        if match and backtick:
            return self._recurse(result, backtick, parent)

        # 1B: We have an embedded self reference such as "PATH": "/bin:$(PATH)".  We use
        #     the last defined value in a prior environment as the value.
        elif parent == k and wholematch is not None:
            val = (self._get_shadow_environment(k) or _DICT_CONST).get(k) or ''

        # 1C: We have already calculated a result and will use that instead, but only
        #     in a nested expansion.  We re-evaluate top-levels all the time.
        elif wholematch is not None and k in result:
            val = result[k]

        # 1D: We have a variable which is not part of our environment at all, and
        #     either treat it as empty, or as the wholematch value for further
        #     processing
        elif k not in self:
            val = "" if match else wholematch
        
        # 1E: Finally, we will store this value and expand further.
        else:
            result[k] = self[k] # assure that recursion attempts stop with this value
            val = result[k] = self._recurse(result, self[k], k)
            
        # We now have, in 'val', the fully expanded contents of the variable 'k'

        if not match:
            return val


        # Phase 2: Process any operators to return a possibily modified
        #          value as the result of the complete expression.

        if oper == '?':
            if not val:
                raise ChVariableError(self._recurse(result, repl))

        elif oper == '/':
            smatch = _RE_SLASHOP.match(repl)
            if not smatch:
                raise ChParameterError("invalid regex replacement syntax in '{0}'".format(match.group(0)))

            val = self._recurse(result, re.sub((smatch.group(3) and "(?" + smatch.group(3) + ")") + smatch.group(1),
                                               smatch.group(2).replace('\/', '/'),
                                               val))

        elif oper == '|':
            vts = _RE_BAREBAR.split(repl, 3)
            if len(vts) == 1: # same as +
                val = '' if not val else self._recurse(result, vts[0])
            elif len(vts) == 2:
                val = self._recurse(result, vts[0] if val else vts[1])
            elif len(vts) >= 3:
                editval = vts[1] if fnmatch(val.replace(r'\|', '|').lower(), vts[0].lower()) else vts[2]
                val = self._recurse(result, editval.replace(r'\|', '|'))

        elif oper == "+":
            val = '' if not val else self._recurse(result, repl)

        elif oper == "_":       # strict opposite of +
            val = '' if val else self._recurse(result, repl)

        elif oper == "-":       # bash :-
            if not val:
                val = self._recurse(result, repl)

        return val
    
    def _recurse(self, result, buf, parent_var = None):
        "Worker method to isolate recursive env variable expansion, with backtick support"
        return _RE_BACKTICK.sub(self._backtick_expand,
                                self._cls_scan.parse(buf, self._expand_into, result, parent_var))

    def _backtick_expand(self, cmd):
        """
        Performs rudimentary backtick expansion after all other environment variables have been
        expanded.   Because these are cached, the user should not expect results to differ
        for different environment contexts, nor should the environment itself be relied upon.
        """

        # Accepts either a string or match object
        if not isinstance(cmd, str):
            cmd = cmd.group(1)

        if not self._cls_backtick:
            return "`" + cmd + "`"

        key = '{0}:{1}:{2}'.format(self.uid, self.gid, cmd)

        result = self._cls_btcache.get(key)

        if result is None:
            if self.uid:
                pwrec = lookup_user(self.uid, self.gid)
            else:
                pwrec = None

            def _proc_setup():
                if pwrec:
                    os.setgid(pwrec.pw_gid)
                    os.setuid(pwrec.pw_uid)

            try:
                result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT,
                                                 preexec_fn=_proc_setup)
                result = result.decode()
            except Exception as ex:
                error(ex, "Backtick expansion returned error: " + str(ex))
                result = ""

            result = result.strip().replace("\n", " ")
            if self._cls_use_btcache:
                self._cls_btcache[key] = result

        return result

    def get_public_environment(self):
        """
        Public variables are those which are exported to the application and do NOT start with an
        underscore.  All underscore names will be kept private.
        """
        return {k:v for k,v in self.expanded().items() if not (k.startswith('_') or v in (None, ''))}
