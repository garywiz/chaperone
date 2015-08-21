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


def maybe_remove(fn, strict = False):
    """
    Tries to remove a file but ignores a FileNotFoundError or Permission error.  If an exception
    would have been raised, returns the exception, otherwise None.

    If "strict" then the file must either be missing, or successfully removed.  Other errors
    will still raise exceptions.
    """
    try:
        os.remove(fn)
    except (FileNotFoundError if strict else (FileNotFoundError, PermissionError)) as ex:
        return ex

    return None


        
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
         lookup_group(gid, True),
         pwrec.pw_gecos,
         pwrec.pw_dir,
         pwrec.pw_shell)
    )

    return retval


def lookup_group(gid, optional = False):
    """
    Looks up a user using either a name or integer user value.
    If 'optional' is true, then does not require that the group exist, and always
    returns the numeric value of 'gid', or the mapping from 'gid' if it is a name.
    Otherwise returns the group record.
    """
    intgid = None

    try:
        intgid = int(gid)
    except ValueError:
        pass
    
    if intgid is not None:
        if optional:
            return intgid
        findit = grp.getgrgid
    else:
        findit = grp.getgrnam

    try:
        grrec = findit(gid)
    except KeyError:
        raise ChNotFoundError("specified group ('{0}') does not exist".format(gid))

    return grrec.gr_gid if optional else grrec


def groupadd(name, gid):
    """
    Adds a group to the system with the specified name and GID.
    """
    # First, try the gnu tools way
    try:
        if subprocess.call(['groupadd', '-g', str(gid), name]) == 0:
            return
        raise ChSystemError("Unable to add a group with name={0} and GID={1}".format(name, gid))
    except FileNotFoundError:
        pass

    # Now, try using 'addgroup' with the busybox syntax
    if subprocess.call("addgroup -g {0} {1}".format(gid, name), shell=True) == 0:
        return

    raise ChSystemError("Unable to add a group with name={0} and GID={1}".format(name, gid))


def useradd(name, uid = None, gid = None, home = None):
    """
    Adds a user to the system given an optional UID and numeric GID.
    """

    ucmd = ['useradd', '--no-create-home']
    if uid is not None:
        ucmd += ['-u', str(uid)]
    if gid is not None:
        ucmd += ['-g', str(gid)]
    if home is not None:
        ucmd += ['--home-dir', home]
    
    ucmd += [name]

    tried = " ".join(ucmd)

    # try gnu tools first
    try:
        if subprocess.call(ucmd) == 0:
            return
        raise ChSystemError("Error while trying to add user: {0} ({1})".format(name, tried))
    except FileNotFoundError:
        pass

    ucmd = "adduser -D -H"
    if uid is not None:
        ucmd += " -u " + str(uid)
    if gid is not None:
        ucmd += " -G " + str(gid)
    if home is not None:
        ucmd += " -h '{0}'".format(home)

    ucmd += " " + name

    tried += "\n" + ucmd

    # try busybox-style adduser
    if subprocess.call(ucmd, shell=True) == 0:
        return

    raise ChSystemError("Error while trying to add user: {0}\ntried:\n{1}".format(name, tried))
    

def userdel(name):
    """
    Removes a user from the system.
    """
    del_ex = ChSystemError("Error while trying to remove user: {0}".format(name))

    # try gnu tools first
    try:
        if subprocess.call(['userdel', name]) == 0:
            return
        raise del_ex
    except FileNotFoundError:
        pass

    # try busybox-style adduser
    if subprocess.call("deluser " + name, shell=True) == 0:
        return

    raise del_ex
    
    
# User Directories Directory cache
_udd = None

def get_user_directories_directory():
    """
    Determines the directory where user directories are stored.  This is actually
    not that easy, and different systems have different ways of doing it.  So,
    we try adding a user called '_chaptest_' just to see where the directory goes,
    and use that.
    """
    global _udd

    if _udd is not None:
        return _udd

    try:
        testuser = "_chaptest_"
        useradd(testuser)
        userinfo = lookup_user(testuser)

        _udd = os.path.dirname(userinfo.pw_dir)

        userdel(testuser)
    except Exception:
        _udd = "/"              # default if any error occurs

    return _udd

def maybe_create_user(user, uid = None, gid = None, using_file = None, default_home = None):
    """
    If the user does not exist, then create one with the given name, and optionally
    the specified uid.  If a gid is specified, create a group with the same name as the 
    user, and the given gid.

    If the user does exist, then confirm that the uid and gid match, if either
    or both are specified.

    If 'using_file' is specified, then uid/gid are ignored and replaced with the uid/gid
    of the specified file.  The file must exist and be readable.
    """

    if using_file:
        stat = os.stat(using_file)
        if uid is None:
            uid = stat.st_uid
        if gid is None:
            gid = stat.st_gid

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
        if gid is not None and lookup_group(gid).gr_gid != pwrec.pw_gid:
            raise ChParameterError("User {0} exists, but does not have expected GID={1}".format(user, gid))
        return

    # Now, we need to create the user, and optionally the group.

    if gid is not None:

        create_group = False
        try:
            newgid = lookup_group(gid).gr_name # always use name
        except ChNotFoundError:
            create_group = True
            try:
                newgid = int(gid)   # must be a number at this point
            except ValueError:
                # We don't report the numeric error, because we *know* there is no such group
                # and we won't create a symbolic group with a randomly-created number.
                raise ChParameterError("Group does not exist: {0}".format(gid))

        if create_group:
            groupadd(user, newgid)
            newgid = lookup_group(user).gr_name
            
        gid = newgid              # always will be the group name

    # Test to see if the user directory itself already exists, which should be the case.
    # If it doesn't, then use the default, if provided.

    home = None

    if default_home:
        udd = get_user_directories_directory()
        if not os.path.exists(os.path.join(udd, user)):
            home = default_home

    useradd(user, uid, gid, home)


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

def remove_for_recreate(filename):
    """
    Indicates the intention to recreate the file at the given path.  This is function can be used
    in advance to assure that
       a) any existing file is gone, and
       b) full permissions and directories exist for creation of a new file in it's place
    """
    ex = maybe_remove(filename, strict = True)
    open_foruser(filename, mode='w').close()
    os.remove(filename)

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
