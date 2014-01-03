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

_BLOCKING_ERRORS = set((
))

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

def _wrap_errno(number, err_args):
    if number not in _MAP_ERRNO:
        return
    new_err_cls = _MAP_ERRNO[number]
    new_err = new_err_cls(err_args)

    # raise a new exception with the original traceback
    traceback = sys.exc_info()[2]
    raise new_err_cls, new_err, traceback

def wrap_error(func, *args, **kw):
    """
    Wrap socket.error, IOError, OSError, select.error to raise new specialized
    exceptions of Python 3.3 like InterruptedError (PEP 3151).
    """
    try:
        return func(*args, **kw)
    except (socket.error, IOError, OSError) as err:
        _wrap_errno(err.errno, err.args)
        raise
    except select.error as err:
        _wrap_errno(err.args[0], err.args)
        raise

