import os
import pwd
import grp
import copy


class objectplus:
    """
    An object which provides some general-purpose useful patterns.
    """

    _cls_singleton = None

    @classmethod
    def sharedInstance(cls):
        "Return a singleton object for this class."
        if not cls._cls_singleton:
            cls._cls_singleton = cls()
        return cls._cls_singleton


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

    def smart_update(self, key, theirs):
        """
        Smart update replaces values in our dictionary with values from the other.  However,
        in the case where both dictionaries contain sub-dictionaries, the sub-dictionaries
        are updated rather than replaced.  (This makes things like env_set inheritance easier.)
        """
        ours = super().get(key)
        if ours is None:
            ours[key] = theirs
            return

        for k,v in theirs.items():
            oursub = ours.get(k)
            if isinstance(oursub, dict) and isinstance(v, dict):
                oursub.update(v)
            else:
                ours[k] = v

    def deepcopy(self):
        return copy.deepcopy(self)


def maybe_remove(fn):
    """
    Tries to remove a file but ignores a FileNotFoundError.
    """
    try:
        os.remove(fn)
    except FileNotFoundError:
        pass


_lookup_user_cache = {}

def lookup_user(uid, gid = None):
    """
    Looks up a user using either a name or integer user value.  If a group is specified,
    Then set the group explicitly in the returned pwrec
    """
    key = (uid, gid)
    retval = _lookup_user_cache.get(key)
    if retval:
        return retval

    # calculate the new entry

    intuid = None

    try:
        intuid = int(uid)
    except ValueError:
        pass
    
    try:
        if intuid is not None:
            pwrec = pwd.getpwuid(intuid)
        else:
            pwrec = pwd.getpwnam(uid)
    except KeyError:
        raise Exception("specified user ('{0}') does not exist".format(uid))

    if gid is None:
        return pwrec

    retval = _lookup_user_cache[key] = type(pwrec)(
        (pwrec.pw_name,
         pwrec.pw_passwd,
         pwrec.pw_uid,
         lookup_gid(gid),
         pwrec.pw_gecos,
         pwrec.pw_dir,
         pwrec.pw_shell)
    )

    return retval


def lookup_gid(gid):
    """
    Looks up a user using either a name or integer user value.
    """
    intgid = None

    try:
        intgid = int(gid)
    except ValueError:
        pass
    
    if intgid is not None:
        return intgid

    try:
        pwrec = grp.getgrnam(gid)
    except KeyError:
        raise Exception("specified group ('{0}') does not exist".format(gid))

    return pwrec.gr_gid


def _assure_dir_for(path, pwrec, gid):
    # gid is present so we know if we need to set group modes, but
    # we always use the one in pwrec

    if os.path.exists(path):
        return

    _assure_dir_for(os.path.dirname(path), pwrec, gid)

    os.mkdir(path, 0o755 if not gid else 0o775)
    if pwrec:
        os.chown(path, pwrec.pw_uid, pwrec.pw_gid if gid else -1)
    
def open_foruser(filename, mode = 'r', uid = None, gid = None, exists_ok = True):
    """
    Similar to open(), but assures all directories exist (similar to os.makedirs)
    and assures that all created objects are writable by the given user, and
    optionally by the given group (causing mode to be set accordingly).
    """
    if uid:
        pwrec = lookup_user(uid, gid)
    else:
        pwrec = None
        gid = None

    rp = os.path.realpath(filename)
    _assure_dir_for(os.path.dirname(rp), pwrec, gid)

    fobj = open(rp, mode)

    if pwrec:
        os.chown(rp, pwrec.pw_uid, pwrec.pw_gid if gid else -1)
        os.chmod(rp, 0o644 if not gid else 0o664)

    return fobj
