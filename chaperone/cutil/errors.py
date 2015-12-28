import errno

class ChError(Exception):

    # Named the same as OSError so that exception code can detect the presence
    # of an errno for reporting purposes
    errno = None
    annotation = None

    def annotate(self, text):
        if self.annotation:
            self.annotation += ' ' + text
        else:
            self.annotation = text

    def __str__(self):
        supmsg = super().__str__()
        if self.annotation:
            supmsg += ' ' + self.annotation
        return supmsg
        
    def __init__(self, message = None, errno = None):
        super().__init__(message)
        if errno is not None:
            self.errno = errno

class ChParameterError(ChError):
    errno = errno.EINVAL

class ChNotFoundError(ChError):
    errno = errno.ENOENT

class ChSystemError(ChError):
    pass

class ChProcessError(ChError):

    def __init__(Self, message = None, errno = None, resultcode = None):
        if resultcode is not None and errno is None:
            errno = resultcode.errno
        super().__init__(message, errno)

class ChVariableError(ChError):
    pass

def get_errno_from_exception(ex):
    try:
        return ex.errno
    except AttributeError:
        return None
