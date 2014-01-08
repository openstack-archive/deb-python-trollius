__all__ = ['BlockingIOError', 'BrokenPipeError', 'ChildProcessError',
           'ConnectionRefusedError', 'ConnectionResetError',
           'InterruptedError', 'ConnectionAbortedError',
           ]

import errno
import select
import socket
import sys

PY33 = (sys.version_info >= (3, 3))

if PY33:
    import builtins
    BlockingIOError = builtins.BlockingIOError
    BrokenPipeError = builtins.BrokenPipeError
    ChildProcessError = builtins.ChildProcessError
    ConnectionRefusedError = builtins.ConnectionRefusedError
    ConnectionResetError = builtins.ConnectionResetError
    InterruptedError = builtins.InterruptedError
    ConnectionAbortedError = builtins.ConnectionAbortedError
else:
    # Python < 3.3
    class BlockingIOError(OSError):
        pass

    class BrokenPipeError(OSError):
        pass

    class ChildProcessError(OSError):
        pass

    class ConnectionRefusedError(OSError):
        pass

    class InterruptedError(OSError):
        pass

    class ConnectionResetError(OSError):
        pass

    class ConnectionAbortedError(OSError):
        pass

_MAP_ERRNO = {
    errno.EAGAIN: BlockingIOError,
    errno.EALREADY: BlockingIOError,
    errno.ECHILD: ChildProcessError,
    errno.ECONNABORTED: ConnectionAbortedError,
    errno.ECONNREFUSED: ConnectionRefusedError,
    errno.ECONNRESET: ConnectionResetError,
    errno.EINPROGRESS: BlockingIOError,
    errno.EINTR: InterruptedError,
    errno.EPIPE: BrokenPipeError,
    errno.ESHUTDOWN: BrokenPipeError,
    errno.EWOULDBLOCK: BlockingIOError,
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

