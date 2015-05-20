import copy

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
