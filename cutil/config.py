import yaml
import os
import pwd

class Configuration(object):

    _conf = None

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

        print("TRYPATH: {0}".format(trypath))

        if not os.path.exists(trypath):
            return cls(default = default)

        if os.path.isdir(trypath):
            return cls(*[os.path.join(trypath, f) for f in os.listdir(trypath) 
                         if f.endswith('.yaml') or f.endswith('.conf')],
                       default = default)

        return cls(trypath, default = default)
        
    def __init__(self, *args, default = None):
        """
        Given one or more files, load our configuration.  If no configuration is provided,
        then use the configuration specified by the default.
        """
        print("ATTEMPTING CONFIG: '{0}'".format(args))

        self._conf = dict()

        for fn in args:
            if os.path.exists(fn):
                self._merge(yaml.load(open(fn, 'r')))
        
        if not self._conf and default:
            self._conf = yaml.load(default)

    def _merge(self, items):
        if type(items) == list:
            items = {k:dict() for k in items}
        print("ITEMS: {0}".format(items))
        conf = self._conf
        for k,v in items.items():
            if k in conf and not k.startswith('service.'):
                conf[k].update(v)
            else:
                conf[k] = v

    def services(self):
        return {k:v for k,v in self._conf if k.endswith('.service')}

    def dump(self):
        return 'configuration: {0}'.format(self._conf)
