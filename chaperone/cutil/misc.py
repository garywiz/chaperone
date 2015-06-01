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

def lookup_user(uid, gid = None):
    """
    Looks up a user using either a name or integer user value.  If a group is specified,
    Then set the group explicitly in the returned pwrec
    """
    intuid = None

    try:
        intuid = int(uid)
    except ValueError:
        pass
    
    if intuid is not None:
        pwrec = pwd.getpwuid(intuid)
    else:
        pwrec = pwd.getpwnam(uid)

    if gid is None:
        return pwrec

    return type(pwrec)(
        (pwrec.pw_name,
         pwrec.pw_passwd,
         pwrec.pw_uid,
         lookup_gid(gid),
         pwrec.pw_gecos,
         pwrec.pw_dir,
         pwrec.pw_shell)
    )

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

    pwrec = grp.getgrnam(gid)

    return pwrec.gr_gid

