import errno
import select
import socket
import sys

class InterruptedError(OSError):
    pass

class BlockingIOError(OSError):
    pass

class ChildProcessError(OSError):
    pass

class BrokenPipeError(OSError):
    # EPIPE, ESHUTDOWN
    pass

class ConnectionResetError(OSError):
    # ECONNRESET
    pass

class ConnectionRefusedError(OSError):
    pass

class ConnectionAbortedError(OSError):
    pass

# FIXME: Ugly hack to not have to patch various modules
__builtins__['InterruptedError'] = InterruptedError
__builtins__['BlockingIOError'] = BlockingIOError
__builtins__['ChildProcessError'] = ChildProcessError
__builtins__['BrokenPipeError'] = BrokenPipeError
__builtins__['ConnectionResetError'] = ConnectionResetError
__builtins__['ConnectionRefusedError'] = ConnectionRefusedError
__builtins__['ConnectionAbortedError'] = ConnectionAbortedError

_MAP_ERRNO = {
    errno.ECHILD: ChildProcessError,
    errno.EINTR: InterruptedError,
    errno.EAGAIN: BlockingIOError,
    errno.EALREADY: BlockingIOError,
    errno.EINPROGRESS: BlockingIOError,
    errno.EWOULDBLOCK: BlockingIOError,
    errno.ECONNREFUSED: ConnectionRefusedError,
    errno.ECONNABORTED: ConnectionAbortedError,
    errno.EPIPE: BrokenPipeError,
}

if sys.version_info >= (3,):
    def reraise(tp, value, tb=None):
        if value.__traceback__ is not tb:
            raise value.with_traceback(tb)
        raise value
else:
    exec("""def reraise(tp, value, tb=None):
    raise tp, value, tb
""")

def _wrap_error(mapping, key, err_args):
    if key not in mapping:
        return
    new_err_cls = mapping[key]
    new_err = new_err_cls(err_args)

    # raise a new exception with the original traceback
    traceback = sys.exc_info()[2]
    reraise(new_err_cls, new_err, traceback)

def wrap_error(func, *args, **kw):
    """
    Wrap socket.error, IOError, OSError, select.error to raise new specialized
    exceptions of Python 3.3 like InterruptedError (PEP 3151).
    """
    try:
        return func(*args, **kw)
    except (socket.error, IOError, OSError) as err:
        _wrap_error(_MAP_ERRNO, err.errno, err.args)
        raise
    except select.error as err:
        _wrap_error(_MAP_ERRNO, err.args[0], err.args)
        raise

