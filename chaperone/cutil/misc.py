import os
import pwd
import grp
import copy
import signal
import subprocess

from chaperone.cutil.errors import ChNotFoundError, ChParameterError, ChSystemError

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


        
def is_exe(p):
    return os.path.isfile(p) and os.access(p, os.X_OK)

def executable_path(fn, env = os.environ):
    """
    Returns the fully qualified pathname to an executable.  The PATH is searched, and
    any tilde expansions are performed.  Exceptions are raised as usual.
    """
    penv = env.get("PATH")
    newfn = os.path.expanduser(fn)
    path,prog = os.path.split(newfn)
    
    if not path and penv:
        for path in penv.split(os.pathsep):
            if is_exe(os.path.join(path, prog)):
                newfn = os.path.join(path, prog)
                break

    if not os.path.isfile(newfn):
        raise FileNotFoundError(fn)
    if not os.access(newfn, os.X_OK):
        raise PermissionError(fn)

    return newfn
                
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
        raise ChNotFoundError("specified user ('{0}') does not exist".format(uid))

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


def lookup_gid(gid, must_exist = False):
    """
    Looks up a user using either a name or integer user value.
    """
    intgid = None

    try:
        intgid = int(gid)
    except ValueError:
        pass
    
    if intgid is not None:
        if not must_exist:
            return intgid
        findit = grp.getgrgid
    else:
        findit = grp.getgrnam

    try:
        pwrec = findit(gid)
    except KeyError:
        raise ChNotFoundError("specified group ('{0}') does not exist".format(gid))

    return pwrec.gr_gid


def maybe_create_user(user, uid = None, gid = None):
    """
    If the user does not exist, then create one with the given name, and optionally
    the specified uid.  If a gid is specified, create a group with the same name as the 
    user, and the given gid.

    If the user does exist, then confirm that the uid and gid match, if either
    or both are specified.
    """

    if uid is not None:
        try:
            uid = int(uid)
        except ValueError:
            raise ChParameterError("Specified UID is not a number: {0}".format(uid))
        
    try:
        pwrec = lookup_user(user)
    except ChNotFoundError:
        pwrec = None

    # If the user exists, we do nothing, but we do validate that their UID and GID
    # exist.

    if pwrec:
        if uid is not None and uid != pwrec.pw_uid:
            raise ChParameterError("User {0} exists, but does not have expected UID={1}".format(user, uid))
        if gid is not None and lookup_gid(gid, True) != pwrec.pw_gid:
            raise ChParameterError("User {0} exists, but does not have expected GID={1}".format(user, gid))
        return

    # Now, we need to create the user, and optionally the group

    ucmd = ['useradd', '--no-create-home']
    if uid is not None:
        ucmd += ['-u', str(uid)]

    if gid is not None:

        create_group = False
        try:
            newgid = lookup_gid(gid, must_exist = True) # name or number
        except ChNotFoundError:
            create_group = True
            try:
                newgid = int(gid)   # must be a number at this point
            except ValueError:
                # We don't report the numeric error, because we *know* there is no such group
                # and we won't create a symbolic group with a randomly-created number.
                raise ChParameterError("Group does not exist: {0}".format(gid))

        if create_group:
            if subprocess.call(['groupadd', '-g', str(newgid), user]):
                raise ChSystemError("Unable to add a group with name={0} and GID={1}".format(user, newgid))
            newgid = lookup_gid(user, must_exist = True)
            
        ucmd += ['-g', str(newgid)]  # use this gid to create our user

    ucmd += [user]

    if subprocess.call(ucmd):
        raise ChSystemError("Error while trying to add user: {0}".format(' '.join(ucmd)))


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


SIGDICT = dict((v,k) for k,v in sorted(signal.__dict__.items())
               if k.startswith('SIG') and not k.startswith('SIG_'))

def get_signal_name(signum):
    return SIGDICT.get(signum, "SIG%d" % signum)

def get_signal_number(signame):
    sup = signame.upper()
    if sup.startswith('SIG') and not sup.startswith('SIG_'):
        num = getattr(signal, sup, None)
    else:
        try:
            num = int(signame)
        except ValueError:
            num = None
    
    if num is None:
        raise ChParameterError("Invalid signal specifier: " + str(signame))

    return num
