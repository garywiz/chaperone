import os
import re
import pwd
import shlex
from operator import attrgetter
from copy import deepcopy
from itertools import chain

import yaml
import voluptuous as V

from chaperone.cutil.env import Environment, ENV_CONFIG_DIR, ENV_SERVICE
from chaperone.cutil.errors import ChParameterError
from chaperone.cutil.logging import info, warn, debug
from chaperone.cutil.misc import lazydict, lookup_user, get_signal_number

@V.message('not an executable file', cls=V.FileInvalid)
@V.truth
def IsExecutable(v):
    return os.path.isfile(v) and os.access(v, os.X_OK)
    
_config_schema = V.Any(
    { V.Match('^.+\.service$'): {
        'after': str,
        'before': str,
        V.Required('command'): str,
        'directory': str,
        'debug': bool,
        'enabled': V.Any(bool, str),
        'env_inherit': [ str ],
        'env_set': { str: str },
        'env_unset': [ str ],
        'exit_kills': bool,
        'gid': V.Any(str, int),
        'ignore_failures': bool,
        'interval': str,
        'kill_signal': str,
        'optional': bool,
        'port': V.Any(str, int),
        'pidfile': str,
        'process_timeout': V.Any(float, int),
        'startup_pause': V.Any(float, int),
        'restart': bool,
        'restart_limit': int,
        'restart_delay': int,
        'service_groups': str,
        'setpgrp': bool,
        'stderr': V.Any('log', 'inherit'),
        'stdout': V.Any('log', 'inherit'),
        'type': V.Any('oneshot', 'simple', 'forking', 'notify', 'cron', 'inetd'),
        'uid': V.Any(str, int),
      },
      V.Match('^settings$'): {
        'debug': bool,
        'detect_exit': bool,
        'env_inherit': [ str ],
        'env_set': { str: str },
        'env_unset': [ str ],
        'gid': V.Any(str, int),
        'idle_delay': V.Any(float, int),
        'ignore_failures': bool,
        'process_timeout': V.Any(float, int),
        'startup_pause': V.Any(float, int),
        'shutdown_timeout': V.Any(float, int),
        'uid': V.Any(str, int),
        'logrec_hostname': str,
        'enable_syslog': bool,
        'status_interval': V.Any(float, int),
      },
      V.Match('^.+\.logging'): {
        'enabled': V.Any(bool, str),
        'extended': bool,
        'file': str,
        'syslog_host': str,
        'selector': str,
        'stderr': bool,
        'stdout': bool,
        'overwrite': bool,
        'uid': V.Any(str, int),
        'gid': V.Any(str, int),
        'logrec_hostname': str,
     },
   }
)
    
validator = V.Schema(_config_schema)

_RE_LISTSEP = re.compile(r'\s*,\s*')

def print_services(label, svlist):
    # Useful for debugging startup order
    print(label)
    for s in svlist:
        print(s)
        p = getattr(s, 'prerequisites', None)
        if p:
            print('  prereq:', p)

# Note that we extend YAML by allowing an empty string to mean "false".  This makes some macro
# expansions work better, such as ... enabled:"$(MYSQL_ENABLED:+true)"

_RE_YAML_BOOL = re.compile(r'^\s*(?:(?P<true>y|true|yes|on)|(n|false|no|off|))\s*$', re.IGNORECASE)

class _BaseConfig(object):

    name = None
    environment = None
    env_set = None
    env_unset = None
    env_inherit = ['*']

    _repr_pat = None
    _expand_these = {}
    _typecheck = {}
    _settings_defaults = {}
    
    @classmethod
    def createConfig(cls, config=None, **kwargs):
        """
        Creates a new configuration given a system configuration object.  Initializes the
        environment as triggers any per-configuration attribute initialization.
        """
        return cls(kwargs, 
                   env=config.get_environment(),
                   settings=config.get_settings())

    def _typecheck_assure_bool(self, attr):
        "Assures that the specified attribute is a legal boolean."
        val = getattr(self, attr)
        if val is None or isinstance(val, bool):
            return
        # First, try both 'true' and 'false' according to YAML conventions
        match = _RE_YAML_BOOL.match(str(val))
        if not match:
            raise ChParameterError("invalid boolean parameter for '{0}': '{1}'".format(attr, val))
        setattr(self, attr, bool(match.group('true')))

    def _typecheck_assure_int(self, attr):
        "Assures that the specified attribute is a legal integer."
        val = getattr(self, attr)
        if val is None or isinstance(val, int):
            return
        try:
            setattr(self, attr, int(val))
        except ValueError:
            raise ChParameterError("invalid integer parameter for '{0}': '{1}'".format(attr, val))

    def __init__(self, initdict, name = "MAIN", env = None, settings = None):
        self.name = name

        if settings:
            for sd in self._settings_defaults:
                if sd not in initdict:
                    val = settings.get(sd)
                    if val is not None:
                        setattr(self, sd, val)

        for k,v in initdict.items():
            setattr(self, k, v)

        # User names always have .xxx qualifier because of schema restrictions.  Otherwise, it's a user
        # defined name subject to restrictions.

        splitname = self.name.rsplit('.', 1)
        if len(splitname) == 2 and splitname[0] == splitname[0].upper():
            raise ChParameterError("all-uppercase names such as '{0}' are reserved for the system.".format(self.name))

        # UID and GID are expanded according to the incoming environment,
        # since the new environment depends upon these.
        if env:
            env.expand_attributes(self, 'uid', 'gid')

        uid = self.get('uid')
        gid = self.get('gid')

        if gid is not None and uid is None:
            raise Exception("cannot specify 'gid' without 'uid'")

        # We can now use 'self' as our config, with all defaults. 

        env = self.environment = Environment(env, uid=uid, gid=gid, config=self, 
                                             resolve_xid = not self.get('optional', False))
        self.augment_environment(env)

        if self._expand_these:
            env.expand_attributes(self, *self._expand_these)

        for attr,func in self._typecheck.items():
            getattr(self, '_typecheck_'+func)(attr)

        self.post_init()

    def shortname(self):
        return self.name

    def post_init(self):
        pass

    def augment_environment(self, env):
        pass

    def get(self, attr, default = None):
        return getattr(self, attr, default)
        
    def __repr__(self):
        if self._repr_pat:
            return self._repr_pat.format(self)
        return super().__repr__()


class ServiceConfig(_BaseConfig):

    after = None
    before = None
    command = None
    debug = None
    directory = None
    enabled = True
    exit_kills = False
    gid = None
    interval = None
    ignore_failures = False
    kill_signal = None
    optional = False
    pidfile = None              # the pidfile to monitor
    port = None                 # used for inetd processes
    process_timeout = None      # time to elapse before we decide a process has misbehaved
    startup_pause = 0.5         # time to wait momentarily to see if a service starts (if needed)
    restart = False
    restart_limit = 5           # number of times to invoke a restart before giving up
    restart_delay = 3           # number of seconds to delay between restarts
    setpgrp = True              # if this process should run in its own process group
    service_groups = "default"  # will be transformed into a tuple() upon construction
    stderr = "log"
    stdout = "log"
    type = 'simple'
    uid = None

    exec_args = None            # derived from bin/command/args, but may be preset using createConfig
    idle_delay = 1.0            # present, but mirrored from settings, not settable per-service
                                # since it is only triggered once when the first IDLE group item executes

    prerequisites = None        # a list of service names which are prerequisites to this one

    _repr_pat = "Service:{0.name}(service_groups={0.service_groups}, after={0.after}, before={0.before})"
    _expand_these = {'command', 'stdout', 'stderr', 'interval', 'directory', 'exec_args', 'pidfile', 'enabled', 'port'}
    _typecheck = {'enabled': 'assure_bool', 'port': 'assure_int'}
    _assure_bool = {'enabled'}
    _settings_defaults = {'debug', 'idle_delay', 'process_timeout', 'startup_pause', 'ignore_failures'}

    system_group_names = ('IDLE', 'INIT')
    system_service_names = ('CONSOLE', 'MAIN')

    @property
    def shortname(self):
        return self.name.replace('.service', '')

    def augment_environment(self, env):
        if self.name:
            env[ENV_SERVICE] = self.name

    def post_init(self):
        # Assure that exec_args is set to the actual arguments used for execution
        if self.command:
            self.exec_args = shlex.split(self.command)

        # Lookup signal number
        if self.kill_signal is not None:
            self.kill_signal = get_signal_number(self.kill_signal)

        # Expand before, after and service_groups into sets/tuples
        self.before = set(_RE_LISTSEP.split(self.before)) if self.before is not None else set()
        self.after = set(_RE_LISTSEP.split(self.after)) if self.after is not None else set()
        self.service_groups = tuple(_RE_LISTSEP.split(self.service_groups)) if self.service_groups is not None else tuple()

        for sname in chain(self.before, self.after):
            if sname.upper() == sname and sname not in chain(self.system_group_names, self.system_service_names):
                raise ChParameterError("{0} dependency reference not valid; '{1}' is not a recognized system name"
                                       .format(self.name, sname))

        for sname in self.service_groups:
            if sname.upper() == sname and sname not in self.system_group_names:
                raise ChParameterError("{0} contains an unrecognized system group name '{1}'".format(self.name, sname))

        if 'IDLE' in self.after:
            raise Exception("{0} cannot specify services which start *after* service_group IDLE".format(self.name))
        if 'INIT' in self.before:
            raise Exception("{0} cannot specify services which start *before* service_group INIT".format(self.name))

        
class LogConfig(_BaseConfig):

    selector = '*.*'
    file = None
    stderr = False
    stdout = False
    enabled = True
    overwrite = False
    extended = False            # include facility/priority information
    uid = None                  # used to control permissions on logfile creation
    gid = None
    logrec_hostname = None      # hostname used to override hostname in syslog record
    syslog_host = None          # remote IP of syslog handler

    _expand_these = {'selector', 'file', 'enabled', 'logrec_hostname', 'syslog_host'}
    _typecheck = {'enabled': 'assure_bool'}
    _settings_defaults = {'logrec_hostname'}

    @property
    def shortname(self):
        return self.name.replace('.logging', '')


class ServiceDict(lazydict):

    _ordered_startup = None

    def __init__(self, servdict, env = None, settings = None):
        """
        Accepts a dictionary of values to be turned into services.
        """
        super().__init__(
            ((k,ServiceConfig(v,k,env,settings)) for (k,v) in servdict)
        )

    def add(self, service):
        self[service.name] = service

    def clear(self):
        super().clear()
        self._ordered_startup = None

    def get_dependency_graph(self):
        """
        Returns a set of dependency groups.  Each group represents a set of dependencies starting at the
        root of the dependency tree.  This is valuable for debugging dependencies.   The output graph
        is ascii-art which shows the earliest start times and latest stop times for each service,
        roughly in order of start-up.
        """

        sep = ' | '
        sulist = self.get_startup_list()
        
        curcol = 0
        maxwidth = 0
        for s in sulist:
            ourlen = len(s.shortname)
            s._column = curcol + ourlen - 1
            curcol += ourlen + len(sep)
            maxwidth = max(maxwidth, ourlen)

        def histogram(serv):
            # find the earliest prerequsite, or 0 if there is none
            pcols = tuple(s._column for s in sulist if s.name in serv.prerequisites)
            start = (pcols and max(pcols) + 1) or 0
            return (' ' * start) + ('=' * (serv._column - start + 1))

        lines = list()

        lines.append(' ' * (maxwidth + len(sep)) + sep.join(s.shortname for s in sulist))

        for s in sulist:
            lines.append(s.shortname.ljust(maxwidth) + sep + histogram(s))

        lines.append(('-' * (maxwidth)) + '-> depends on...')

        for s in sulist:
            lines.append(s.shortname.ljust(maxwidth) + sep + ', '.join(pr.replace('.service', '') for pr in s.prerequisites))

        return lines

    def get_startup_list(self):
        """
        Returns the list of start-up items in priority order by examining before: and after: 
        attributes.
        """
        if self._ordered_startup is not None:
            return self._ordered_startup

        services = self.deepcopy()
        groups = lazydict()
        for k,v in services.items():
            for g in v.service_groups:
                groups.setdefault(g, lambda: lazydict())[k] = v

        #print_services('initial', services.values())

        # The "IDLE" and "INIT" groups are special.  Revamp things so that any services in the "IDLE" group
        # have an implicit "after: 'all-others'" and any services in "INIT" have an implicit "before: 'all-others'
        # where all-others is an explicit list of all services NOT in the respective group

        if 'IDLE' in groups:
            nonidle = set(k for k,v in services.items() if "IDLE" not in v.service_groups)
            for s in groups['IDLE'].values():
                s.after.update(nonidle)
        if 'INIT' in groups:
            noninit = set(k for k,v in services.items() if "INIT" not in v.service_groups)
            for s in groups['INIT'].values():
                s.before.update(noninit)

        # We want to only look at the "after:" attribute, so we will eliminate the relevance
        # of befores...

        for k,v in services.items():
            for bef in v.before:
                if bef in groups:
                    for g in groups[bef].values():
                        g.after.add(v.name)
                elif bef in services:
                    services[bef].after.add(v.name)
            v.before = None

        # Before is now gone, make sure that all "after... groups" are translated into "after.... service"

        for group in groups.values():
            afters = set()
            for item in group.values():
                afters.update(item.after)
            for a in afters:
                if a in groups:
                    names = groups[a].keys()
                    for item in group.values():
                        item.after.update(names)
                
        # Now remove any undefined services or groups and turn the 'after' attribute into a definitive
        # graph.
        #
        # Note: sorted() occurs a couple times below.  The main reason is so that the results
        #       are deterministic in cases where exact order is not defined.

        afters = set(services.keys())
        for v in services.values():
            v.refs = sorted(map(lambda n: services[n], v.after.intersection(afters)), key=attrgetter('name'))

        #print_services('before add nodes', services.values())

        svlist = list()         # this will be our final list, containing original items
        svseen = set()

        def add_nodes(items):
            for item in items:
                if hasattr(item, 'active'):
                    raise Exception("circular dependency in service declaration")
                item.active = True
                add_nodes(item.refs)
                del item.active
                if item.name not in svseen:
                    svseen.add(item.name)
                    svlist.append(self[item.name])
                    # set startup prerequisite dependencies
                    svlist[-1].prerequisites = set(r.name for r in item.refs)
        add_nodes(sorted(services.values(), key=attrgetter('name')))

        #print_services('final service list', svlist)

        self._ordered_startup = svlist

        return svlist
            
class Configuration(object):

    uid = None                  # specifies if a system-wide user was provided
    gid = None
    _conf = None
    _env = None                 # calculated environment

    @classmethod
    def configFromCommandSpec(cls, spec, user = None, default = None, extra_settings = None, disable_console_log = False):
        """
        A command specification (typically specified with the --config=<file_or_dir> command
        line option) is used to create a configuration object.   The target may be either a file
        or a directory.  If it is a file, then the file itself will be the only configuration
        read.  If it is a directory, then a search is made for any top-level files which end in
        .conf or .yaml, and those will be combined according to lexicographic order.

        If the configuration path is a relative path, then it is relative to either the root
        directory, or the home directory of the given user.  This allows a user-specific
        configuration to automatically take effect if desired.
        """

        frombase = '/'

        if user:
            frombase = lookup_user(user).pw_dir

        trypath = os.path.join(frombase, spec)

        debug("TRY CONFIG PATH: {0}".format(trypath))

        if not os.path.exists(trypath):
            return cls(default = default)
        else:
            os.environ[ENV_CONFIG_DIR] = os.path.dirname(trypath)

        if os.path.isdir(trypath):
            return cls(*[os.path.join(trypath, f) for f in sorted(os.listdir(trypath))
                         if f.endswith('.yaml') or f.endswith('.conf')],
                       default = default, uid = user, extra_settings = extra_settings, disable_console_log = disable_console_log)


        return cls(trypath, default = default, uid = user, extra_settings = extra_settings, disable_console_log = disable_console_log)
        
    def __init__(self, *args, default = None, uid = None, extra_settings = None, disable_console_log = False):
        """
        Given one or more files, load our configuration.  If no configuration is provided,
        then use the configuration specified by the default.
        """
        debug("CONFIG INPUT (uid={1}): '{0}'".format(args, uid))

        self.uid = uid
        self._conf = lazydict()

        for fn in args:
            if os.path.exists(fn):
                self._merge(yaml.load(open(fn, 'r').read().expandtabs()))
        
        if not self._conf and default:
            self._conf = lazydict(yaml.load(default))

        validator(self._conf)

        if extra_settings:
            self.update_settings(extra_settings)

        s = self.get_settings()
        self.uid = s.get('uid', self.uid)
        self.gid = s.get('gid', self.gid)

        # Special case used by --no-console-log.  It really was just easiest to do it this way
        # rather than try to build some special notion of "console logging" into the log services
        # backends.

        if disable_console_log:
            for k,v in self._conf.items():
                if k.endswith('.logging'):
                    if 'stdout' in v:
                        del v['stdout']
                    if 'stderr' in v:
                        del v['stderr']

    def _merge(self, items):
        if type(items) == list:
            items = {k:dict() for k in items}
        conf = self._conf
        for k,v in items.items():
            if k in conf and not k.endswith('.service'):
                conf.smart_update(k,v)
            else:
                conf[k] = v

    def get_services(self):
        env = self.get_environment()
        return ServiceDict( 
            ((k,v) for k,v in self._conf.items() if k.endswith('.service')),
            env,
            self._conf.get('settings')
        )

    def get_logconfigs(self):
        env = self.get_environment()
        settings = self._conf.get('settings')
        return lazydict(
            ((k,LogConfig(v,k,env,settings)) for k,v in self._conf.items() if k.endswith('.logging'))
        )

    def get_settings(self):
        return self._conf.get('settings') or {}

    def update_settings(self, updates):
        curset = self.get_settings()
        curset.update(updates)
        self._conf['settings'] = curset

    def get_environment(self):
        if not self._env:
            self._env = Environment(config=self.get_settings(), uid=self.uid, gid=self.gid)
        return self._env

    def dump(self):
        debug('FULL CONFIGURATION: {0}'.format(self._conf))
