
IS_EVENT = lambda e: e.startswith('on') and len(e) > 2 and e[2:3].isupper()

def SWALLOW_EVENT(*args, **kwargs):
    pass


class EventSource:
    """
    This is a elegant generic class to set up and handle events.

    Events are always identified by keyword arguments of the format
    onXxxxx.

      def __init__(self, **kwargs):
        events = EventSource()
        kwargs = events.add(**kwargs)

      def foo(self):
        self.events.onMiscEvent()

      
    """

    __events = None

    def __init__(self, **kwargs):
        self.__events = dict()
        if kwargs:
            self._exec_kwargs(self._do_add, kwargs)

    def __getattribute__(self, key):
        if IS_EVENT(key):
            return self.__events.get(key, SWALLOW_EVENT)

        return object.__getattribute__(self, key)

    def _exec_kwargs(self, oper, kwargs):
        events = [e for e in kwargs.keys() if IS_EVENT(e)]
        if not events:
            return kwargs

        for e in events:
            oper(e, kwargs[e])
            del kwargs[e]

        return kwargs

    def clear(self):
        "Removes all event handlers."
        self.__events.clear()

    def reset(self, **kwargs):
        "Removes all event handlers and sets new ones."
        self.__events.clear()
        return self._exec_kwargs(self._do_add, kwargs)

    def add(self, **kwargs):
        """
        Adds one or more events:
           add(onError = handler, onExit = handler)
       
        Returns the kwargs not processed.
        """
        return self._exec_kwargs(self._do_add, kwargs)

    def remove(self, **kwargs):
        """
        Removes one or more events:
           remove(onError = handler, onExit = handler)
       
        Returns the kwargs not processed.
        """
        return self._exec_kwargs(self._do_remove, kwargs)

    def _do_add(self, name, value):
        assert callable(value)

        e = self.__events.get(name)

        # No such event, add a singleton
        if not e:
            self.__events[name] = value
            return

        # Add to multi-event dispatcher
        try:
            e.__eventlist.append(value)
            return
        except AttributeError:
            pass
        
        # Create multi-event dispatcher

        displist = [e, value]
        def dispatcher(*args, _displist = displist, **kwargs):
            for edisp in _displist:
                edisp(*args, **kwargs)
        dispatcher.__eventlist = displist

        self.__events[name] = dispatcher

    def _do_remove(self, name, value):
        e = self.__events.get(name)

        if not name:
            return

        try:
            e.__eventlist.remove(value)
        except ValueError:
            return                      # not in list, ignore
        except AttributeError:
            try:
                del self.__events[name] # singleton
            except KeyError:
                return                  # no singleton, ignore
