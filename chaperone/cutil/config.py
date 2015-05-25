import os
import pwd
from copy import deepcopy

import yaml
import voluptuous as V

from chaperone.cutil.logging import info, warn, debug
from chaperone.cutil.misc import lazydict, Environment

@V.message('not an executable file', cls=V.FileInvalid)
@V.truth
def IsExecutable(v):
    return os.path.isfile(v) and os.access(v, os.X_OK)
    
_config_service = { V.Required('bin'): str }

_config_schema = V.Any(
    { V.Match('^.+\.service$'): {
        'command': str,
        'bin': str,
        'args': str,
        'restart': bool,
        'before': str,
        'after': str,
        'optional': bool,
        'ignore_failures': bool,
        'enabled': bool,
        'env_inherit': [ str ],
        'env_add': { str: str },
        'stdout': V.Any(None, 'log', 'inherit'),
        'stderr': V.Any(None, 'log', 'inherit'),
      },
      V.Match('^settings$'): {
        'env_inherit': [ str ],
        'env_add': { str: str },
      },
      V.Match('^.+\.logging'): {
        'filter': str,
        'file': str,
        'stderr': bool,
        'stdout': bool,
        'enabled': bool,
        'extended': bool,
     },
   }
)
    
validator = V.Schema(_config_schema)

class _BaseConfig(object):

    name = None
    _repr_pat = None
    _expand_these = None

    def __init__(self, name, initdict, env = None):
        self.name = name
        if env and self._expand_these:
            expand = env.expand
        else:
            expand = lambda x: x
        for k,v in initdict.items():
            setattr(self, k, expand(v))

    def get(self, attr, default = None):
        return getattr(self, attr, default)
        
    def __repr__(self):
        if self._repr_pat:
            return self._repr_pat.format(self)
        return super().__repr__()


class ServiceConfig(_BaseConfig):

    group = "default"
    restart = True
    before = None
    after = None
    ignore_failures = False
    optional = False
    command = None
    args = None
    enabled = True
    env_add = None
    env_inherit = ['*']
    stdout = "log"
    stderr = "log"
    bin = None

    _repr_pat = "Service:{0.name}(group={0.group}, after={0.after}, before={0.before})"
    _expand_these = {'command', 'args', 'stdout', 'stderr', 'bin'}

    def __init__(self, name, initdict, env = None):
        super().__init__(name, initdict, env)
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

    def __init__(self, servdict, env = None):
        """
        Accepts a dictionary of values to be turned into services.
        """
        super().__init__(
            ((k,ServiceConfig(k,v,env)) for (k,v) in servdict)
        )

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
            groups.setdefault(v.group, lambda: lazydict())[k] = v

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

        add_nodes(services.values())

        self._ordered_startup = svlist

        return svlist
            
class Configuration(object):

    _conf = None
    _env = None                 # calculated environment

    @classmethod
    def configFromCommandSpec(cls, spec, user = None, default = None):
        """
        A command specification (typically specified with the --config=<file_or_dir> command
        line option) is used to create a configuration object.

        If no user is specified, then the spec is relative to the root of the file system and may
        or may not contain a path.

        If a user is specified, then the spec is relative to the user's home directory.  However, 
        if it is a full path, then the leading path is stripped off before it is used.

        Thus, for root:
            chaperone.d      ->   /chaperone.d
            /etc/chaperone.d ->   /etc/chaperone.d
            foo/chaperone.d  ->   /foo/chaperone.d

        for jbloggs:
            chaperone.d      ->   /home/jbloggs/chaperone.d
            /etc/chaperone.d ->   /home/jbloggs/chaperone.d
            foo/chaperone.d  ->   /home/jbloggs/foo/chaperone.d

        This allows you to easily specify a system default location has sensible per-user mappings.
        """

        frombase = '/'

        if user:
            pwrec = pwd.getpwnam(user)
            frombase = pwrec.pw_dir
            if os.path.isabs(spec):
                spec = os.path.basename(spec)

        trypath = os.path.join(frombase, spec)

        debug("TRY CONFIG PATH: {0}".format(trypath))

        if not os.path.exists(trypath):
            return cls(default = default)

        if os.path.isdir(trypath):
            return cls(*[os.path.join(trypath, f) for f in sorted(os.listdir(trypath))
                         if f.endswith('.yaml') or f.endswith('.conf')],
                       default = default)

        return cls(trypath, default = default)
        
    def __init__(self, *args, default = None):
        """
        Given one or more files, load our configuration.  If no configuration is provided,
        then use the configuration specified by the default.
        """
        debug("CONFIG INPUT: '{0}'".format(args))

        self._conf = dict()

        for fn in args:
            if os.path.exists(fn):
                self._merge(yaml.load(open(fn, 'r')))
        
        if not self._conf and default:
            self._conf = yaml.load(default)

        validator(self._conf)

    def _merge(self, items):
        if type(items) == list:
            items = {k:dict() for k in items}
        conf = self._conf
        for k,v in items.items():
            if k in conf and not k.startswith('service.'):
                conf[k].update(v)
            else:
                conf[k] = v

    def get_services(self):
        env = self.get_environment()
        return ServiceDict( 
            ((k,v) for k,v in self._conf.items() if k.endswith('.service')),
            env
        )

    def get_logconfigs(self):
        env = self.get_environment()
        return lazydict(
            ((k,LogConfig(k,v,env)) for k,v in self._conf.items() if k.endswith('.logging'))
        )

    def get_settings(self):
        return self._conf.get('settings')

    def get_environment(self):
        if not self._env:
            self._env = Environment(self.get_settings())
        return self._env

    def dump(self):
        debug('FULL CONFIGURATION: {0}'.format(self._conf))
