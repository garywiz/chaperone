import inspect
import importlib

# This module contains patches to Python.  A patch wouldn't appear here if it didn't have major impact,
# and they are constructed and researched carefully.  Avoid if possible, please.

# Patch routine for patching classes.  Ignore ALL exceptions, since there could be any number of
# reasons why a distribution may not allow such patching (though most do).  Exact code is compared,
# so there is little chance of an error in deciding if the patch is relevant.

def PATCH_CLASS(module, clsname, member, oldstr, newfunc):
    try:
        cls = getattr(importlib.import_module(module), clsname)
        should_be = ''.join(inspect.getsourcelines(getattr(cls, member))[0])
        if should_be == oldstr:
            setattr(cls, member, newfunc)
    except Exception:
        pass


# PATCH  for Issue23140: https://bugs.python.org/issue23140
# WHERE  asyncio
# IMPACT Eliminates exceptions during process termination
# WHY    There is no workround except upgrading to Python 3.4.3, which dramatically affects
#        distro compatibility.  Mostly, this benefits Ubuntu 14.04LTS.

OLD_process_exited = """    def process_exited(self):
        # wake up futures waiting for wait()
        returncode = self._transport.get_returncode()
        while self._waiters:
            waiter = self._waiters.popleft()
            waiter.set_result(returncode)
"""

def NEW_process_exited(self):
    # wake up futures waiting for wait()
    returncode = self._transport.get_returncode()
    while self._waiters:
        waiter = self._waiters.popleft()
        if not waiter.cancelled():
            waiter.set_result(returncode)

PATCH_CLASS('asyncio.subprocess', 'SubprocessStreamProtocol', 'process_exited', OLD_process_exited, NEW_process_exited)
