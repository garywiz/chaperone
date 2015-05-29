import os
import pwd
import shlex
from copy import deepcopy

import yaml
import voluptuous as V

from chaperone.cutil.logging import info, warn, debug
from chaperone.cutil.misc import lazydict, Environment, lookup_user

@V.message('not an executable file', cls=V.FileInvalid)
@V.truth
def IsExecutable(v):
    return os.path.isfile(v) and os.access(v, os.X_OK)
    
@V.message('all-uppercase service_groups and service names are reserved for the system')
@V.truth
def ValidServiceName(v):
    return str(v).upper() != str(v)

_config_service = { V.Required('bin'): str }

_config_schema = V.Any(
    { V.Match('^.+\.service$'): {
        'after': str,
        'args': str,
        'before': str,
        'bin': str,
        'command': str,
        'debug': bool,
        'enabled': bool,
        'env_inherit': [ str ],
        'env_set': { str: str },
        'env_unset': [ str ],
        'exit_kills': bool,
        'gid': V.Any(str, int),
        'ignore_failures': bool,
        'optional': bool,
        'process_timeout': V.Any(float, int),
        'restart': bool,
        'service_group': str,
        'stderr': V.Any('log', 'inherit'),
        'stdout': V.Any('log', 'inherit'),
        'type': V.Any('oneshot', 'simple', 'forking'),
        'uid': V.Any(str, int),
      },
      V.Match('^settings$'): {
        'debug': bool,
        'env_inherit': [ str ],
        'env_set': { str: str },
        'env_unset': [ str ],
        'gid': V.Any(str, int),
        'idle_delay': V.Any(float, int),
        'process_timeout': V.Any(float, int),
        'uid': V.Any(str, int),
      },
      V.Match('^.+\.logging'): {
        'enabled': bool,
        'extended': bool,
        'file': str,
        'filter': str,
        'stderr': bool,
        'stdout': bool,
     },
   }
)
    
validator = V.Schema(_config_schema)

class _BaseConfig(object):

    name = None
    environment = None
    env_set = None
    env_unset = None
    env_inherit = ['*']

    _repr_pat = None
    _expand_these = {}
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

    def __init__(self, initdict, name = "MAIN", env = None, settings = None):
        self.name = name

        #print("_BaseConfig init env user", env and env.user)

        if settings:
            for sd in self._settings_defaults:
                if sd not in initdict:
                    val = settings.get(sd)
                    if val is not None:
                        setattr(self, sd, val)

        if env:
            env = self.environment = Environment(env, 
                                                 config = self, 
                                                 uid = initdict.get('uid'),
                                                 gid = initdict.get('gid')).expanded()
            expand = env.expand
        else:
            expand = lambda x: x

        for k,v in initdict.items():
            if k in self._expand_these:
                setattr(self, k, env.expand(v))
            else:
                setattr(self, k, v)

        self.post_init()

    def post_init(self):
        pass

    def get(self, attr, default = None):
        return getattr(self, attr, default)
        
    def __repr__(self):
        if self._repr_pat:
            return self._repr_pat.format(self)
        return super().__repr__()


class ServiceConfig(_BaseConfig):

    after = None
    args = None
    before = None
    bin = None
    command = None
    debug = None
    enabled = True
    exit_kills = False
    gid = None
    ignore_failures = False
    optional = False
    process_timeout = 10.0      # time to elapse before we decide a process has misbehaved
    restart = True
    service_group = "default"
    stderr = "log"
    stdout = "log"
    type = 'simple'
    uid = None

    exec_args = None            # derived from bin/command/args, but may be preset using createConfig
    idle_delay = 1.0            # present, but mirrored from settings, not settable per-service
                                # since it is only triggered once when the first IDLE group item executes

    prerequisites = None        # a list of service names which are prerequisites to this one

    _repr_pat = "Service:{0.name}(service_group={0.service_group}, after={0.after}, before={0.before})"
    _expand_these = {'command', 'args', 'stdout', 'stderr', 'bin'}
    _settings_defaults = {'debug', 'idle_delay', 'process_timeout'}

    def post_init(self):
        # Assure that exec_args is set to the actual arguments used for execution
        if self.command:
            if self.bin or self.args:
                raise Exception("bin/args and command config are mutually-exclusive")
            self.exec_args = shlex.split(self.command)
        elif self.bin:
            self.exec_args = [self.bin] + shlex.split(self.args or '')

        # Expand before and after into sets
        self.before = set(self.before.split()) if self.before is not None else set()
        self.after = set(self.after.split()) if self.after is not None else set()

        
class LogConfig(_BaseConfig):

    filter = '*.*'
    file = None
    stderr = False
    stdout = False
    enabled = True
    extended = False            # include facility/priority information

    _expand_these = {'filter', 'file'}


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
            groups.setdefault(v.service_group, lambda: lazydict())[k] = v

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

        # The "IDLE" group is special.  Revamp things so that any services in the "IDLE" group
        # have an implicit "after: 'all-others'" where all-others is an explicit list of all
        # services NOT in the idle group

        if 'IDLE' in groups:
            nonidle = set(k for k,v in services.items() if v.service_group != "IDLE")
            for s in groups['IDLE'].values():
                s.after.update(nonidle)

        # Before is now gone, make sure that all "after... groups" are translated into "after.... service"

        for group in groups.values():
            #print(*[iter(item.after) for item in group.values()])
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

        afters = set(services.keys())
        for v in services.values():
            v.refs = tuple(map(lambda n: services[n], v.after.intersection(afters)))

        svlist = list()         # this will be our final list, containing original items
        svseen = set()

        def add_nodes(items):
            for item in items:
                if hasattr(item, 'active'):
                    raise Exception("Circular dependency in service declaration")
                item.active = True
                add_nodes(item.refs)
                del item.active
                if item.name not in svseen:
                    svseen.add(item.name)
                    svlist.append(self[item.name])
                    # set startup prerequisite dependencies
                    svlist[-1].prerequisites = tuple(r.name for r in item.refs)

        add_nodes(services.values())

        self._ordered_startup = svlist

        return svlist
            
class Configuration(object):

    uid = None                  # specifies if a system-wide user was provided
    gid = None
    _conf = None
    _env = None                 # calculated environment

    @classmethod
    def configFromCommandSpec(cls, spec, user = None, default = None):
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

        if os.path.exists(trypath):
            os.environ['_CHAPERONE_CONFIG_DIR'] = os.path.dirname(trypath)

        if os.path.isdir(trypath):
            return cls(*[os.path.join(trypath, f) for f in sorted(os.listdir(trypath))
                         if f.endswith('.yaml') or f.endswith('.conf')],
                       default = default, uid = user)


        return cls(trypath, default = default, uid = user)
        
    def __init__(self, *args, default = None, uid = None):
        """
        Given one or more files, load our configuration.  If no configuration is provided,
        then use the configuration specified by the default.
        """
        debug("CONFIG INPUT (uid={1}): '{0}'".format(args, uid))

        self.uid = uid
        self._conf = dict()

        for fn in args:
            if os.path.exists(fn):
                self._merge(yaml.load(open(fn, 'r').read().expandtabs()))
        
        if not self._conf and default:
            self._conf = yaml.load(default)

        validator(self._conf)

        s = self.get_settings()
        self.uid = s.get('uid', self.uid)
        self.gid = s.get('gid', self.gid)

    def _merge(self, items):
        if type(items) == list:
            items = {k:dict() for k in items}
        conf = self._conf
        for k,v in items.items():
            if k in conf and not k.endswith('.service'):
                conf[k].update(v)
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
        return self._conf.get('settings')

    def get_environment(self):
        if not self._env:
            self._env = Environment(config=self.get_settings(), uid=self.uid, gid=self.gid)
        return self._env

    def dump(self):
        debug('FULL CONFIGURATION: {0}'.format(self._conf))
