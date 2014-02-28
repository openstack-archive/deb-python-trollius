"""A Future class similar to the one in PEP 3148."""

__all__ = ['CancelledError', 'TimeoutError',
           'InvalidStateError',
           'Future', 'wrap_future',
           ]

import logging
import sys
import traceback

from . import events
from . import executor

# States for Future.
_PENDING = 'PENDING'
_CANCELLED = 'CANCELLED'
_FINISHED = 'FINISHED'

_PY34 = sys.version_info >= (3, 4)

Error = executor.Error
CancelledError = executor.CancelledError
TimeoutError = executor.TimeoutError

STACK_DEBUG = logging.DEBUG - 1  # heavy-duty debugging


class InvalidStateError(Error):
    """The operation is not allowed in this state."""
    # TODO: Show the future, its state, the method, and the required state.


class _TracebackLogger(object):
    """Helper to log a traceback upon destruction if not cleared.

    This solves a nasty problem with Futures and Tasks that have an
    exception set: if nobody asks for the exception, the exception is
    never logged.  This violates the Zen of Python: 'Errors should
    never pass silently.  Unless explicitly silenced.'

    However, we don't want to log the exception as soon as
    set_exception() is called: if the calling code is written
    properly, it will get the exception and handle it properly.  But
    we *do* want to log it if result() or exception() was never called
    -- otherwise developers waste a lot of time wondering why their
    buggy code fails silently.

    An earlier attempt added a __del__() method to the Future class
    itself, but this backfired because the presence of __del__()
    prevents garbage collection from breaking cycles.  A way out of
    this catch-22 is to avoid having a __del__() method on the Future
    class itself, but instead to have a reference to a helper object
    with a __del__() method that logs the traceback, where we ensure
    that the helper object doesn't participate in cycles, and only the
    Future has a reference to it.

    The helper object is added when set_exception() is called.  When
    the Future is collected, and the helper is present, the helper
    object is also collected, and its __del__() method will log the
    traceback.  When the Future's result() or exception() method is
    called (and a helper object is present), it removes the the helper
    object, after calling its clear() method to prevent it from
    logging.

    One downside is that we do a fair amount of work to extract the
    traceback from the exception, even when it is never logged.  It
    would seem cheaper to just store the exception object, but that
    references the traceback, which references stack frames, which may
    reference the Future, which references the _TracebackLogger, and
    then the _TracebackLogger would be included in a cycle, which is
    what we're trying to avoid!  As an optimization, we don't
    immediately format the exception; we only do the work when
    activate() is called, which call is delayed until after all the
    Future's callbacks have run.  Since usually a Future has at least
    one callback (typically set by 'yield From') and usually that
    callback extracts the callback, thereby removing the need to
    format the exception.

    PS. I don't claim credit for this solution.  I first heard of it
    in a discussion about closing files when they are collected.
    """

    __slots__ = ['exc', 'tb', 'loop']

    def __init__(self, exc, loop):
        self.loop = loop
        self.exc = exc
        self.tb = None

    def activate(self):
        exc = self.exc
        if exc is not None:
            self.exc = None
            self.tb = traceback.format_exception(exc.__class__, exc,
                                                 exc.__traceback__)

    def clear(self):
        self.exc = None
        self.tb = None

    def __del__(self):
        if self.tb:
            msg = 'Future/Task exception was never retrieved:\n{tb}'
            context = {
                'message': msg.format(tb=''.join(self.tb)),
            }
            self.loop.call_exception_handler(context)


class Future(object):
    """This class is *almost* compatible with concurrent.futures.Future.

    Differences:

    - result() and exception() do not take a timeout argument and
      raise an exception when the future isn't done yet.

    - Callbacks registered with add_done_callback() are always called
      via the event loop's call_soon_threadsafe().

    - This class is not compatible with the wait() and as_completed()
      methods in the concurrent.futures package.

    (In Python 3.4 or later we may be able to unify the implementations.)
    """

    # Class variables serving as defaults for instance variables.
    _state = _PENDING
    _result = None
    _exception = None
    _loop = None

    _log_traceback = False   # Used for Python >= 3.4
    _tb_logger = None        # Used for Python <= 3.3

    def __init__(self, loop=None):
        """Initialize the future.

        The optional event_loop argument allows to explicitly set the event
        loop object used by the future. If it's not provided, the future uses
        the default event loop.
        """
        if loop is None:
            self._loop = events.get_event_loop()
        else:
            self._loop = loop
        self._callbacks = []

    def __repr__(self):
        res = self.__class__.__name__
        if self._state == _FINISHED:
            if self._exception is not None:
                res += '<exception={0!r}>'.format(self._exception)
            else:
                res += '<result={0!r}>'.format(self._result)
        elif self._callbacks:
            size = len(self._callbacks)
            if size > 2:
                res += '<{0}, [{1}, <{2} more>, {3}]>'.format(
                    self._state, self._callbacks[0],
                    size-2, self._callbacks[-1])
            else:
                res += '<{0}, {1}>'.format(self._state, self._callbacks)
        else:
            res += '<{0}>'.format(self._state)
        return res

    if _PY34:
        def __del__(self):
            if not self._log_traceback:
                # set_exception() was not called, or result() or exception()
                # has consumed the exception
                return
            exc = self._exception
            context = {
                'message': 'Future/Task exception was never retrieved',
                'exception': exc,
                'future': self,
            }
            self._loop.call_exception_handler(context)

    def cancel(self):
        """Cancel the future and schedule callbacks.

        If the future is already done or cancelled, return False.  Otherwise,
        change the future's state to cancelled, schedule the callbacks and
        return True.
        """
        if self._state != _PENDING:
            return False
        self._state = _CANCELLED
        self._schedule_callbacks()
        return True

    def _schedule_callbacks(self):
        """Internal: Ask the event loop to call all callbacks.

        The callbacks are scheduled to be called as soon as possible. Also
        clears the callback list.
        """
        callbacks = self._callbacks[:]
        if not callbacks:
            return

        self._callbacks[:] = []
        for callback in callbacks:
            self._loop.call_soon(callback, self)

    def cancelled(self):
        """Return True if the future was cancelled."""
        return self._state == _CANCELLED

    # Don't implement running(); see http://bugs.python.org/issue18699

    def done(self):
        """Return True if the future is done.

        Done means either that a result / exception are available, or that the
        future was cancelled.
        """
        return self._state != _PENDING

    def result(self):
        """Return the result this future represents.

        If the future has been cancelled, raises CancelledError.  If the
        future's result isn't yet available, raises InvalidStateError.  If
        the future is done and has an exception set, this exception is raised.
        """
        if self._state == _CANCELLED:
            raise CancelledError
        if self._state != _FINISHED:
            raise InvalidStateError('Result is not ready.')
        self._log_traceback = False
        if self._tb_logger is not None:
            self._tb_logger.clear()
            self._tb_logger = None
        if self._exception is not None:
            raise self._exception
        return self._result

    def exception(self):
        """Return the exception that was set on this future.

        The exception (or None if no exception was set) is returned only if
        the future is done.  If the future has been cancelled, raises
        CancelledError.  If the future isn't done yet, raises
        InvalidStateError.
        """
        if self._state == _CANCELLED:
            raise CancelledError
        if self._state != _FINISHED:
            raise InvalidStateError('Exception is not set.')
        self._log_traceback = False
        if self._tb_logger is not None:
            self._tb_logger.clear()
            self._tb_logger = None
        return self._exception

    def add_done_callback(self, fn):
        """Add a callback to be run when the future becomes done.

        The callback is called with a single argument - the future object. If
        the future is already done when this is called, the callback is
        scheduled with call_soon.
        """
        if self._state != _PENDING:
            self._loop.call_soon(fn, self)
        else:
            self._callbacks.append(fn)

    # New method not in PEP 3148.

    def remove_done_callback(self, fn):
        """Remove all instances of a callback from the "call when done" list.

        Returns the number of callbacks removed.
        """
        filtered_callbacks = [f for f in self._callbacks if f != fn]
        removed_count = len(self._callbacks) - len(filtered_callbacks)
        if removed_count:
            self._callbacks[:] = filtered_callbacks
        return removed_count

    # So-called internal methods (note: no set_running_or_notify_cancel()).

    def set_result(self, result):
        """Mark the future done and set its result.

        If the future is already done when this method is called, raises
        InvalidStateError.
        """
        if self._state != _PENDING:
            raise InvalidStateError('{0}: {1!r}'.format(self._state, self))
        self._result = result
        self._state = _FINISHED
        self._schedule_callbacks()

    def set_exception(self, exception):
        """Mark the future done and set an exception.

        If the future is already done when this method is called, raises
        InvalidStateError.
        """
        if self._state != _PENDING:
            raise InvalidStateError('{0}: {1!r}'.format(self._state, self))
        if isinstance(exception, type):
            exception = exception()
        self._exception = exception
        self._state = _FINISHED
        self._schedule_callbacks()
        if _PY34:
            self._log_traceback = True
        else:
            self._tb_logger = _TracebackLogger(exception, self._loop)
            if hasattr(exception, '__traceback__'):
                # Python 3: exception contains a link to the traceback

                # Arrange for the logger to be activated after all callbacks
                # have had a chance to call result() or exception().
                self._loop.call_soon(self._tb_logger.activate)
            else:
                if self._loop.get_debug():
                    frame = sys._getframe(1)
                    tb = ['Traceback (most recent call last):\n']
                    tb += traceback.format_stack(frame)
                    tb += traceback.format_exception_only(type(exception), exception)
                    self._tb_logger.tb = tb
                else:
                    self._tb_logger.tb = traceback.format_exception_only(
                                                        type(exception),
                                                        exception)

                self._tb_logger.exc = None

    # Truly internal methods.

    def _copy_state(self, other):
        """Internal helper to copy state from another Future.

        The other Future may be a concurrent.futures.Future.
        """
        assert other.done()
        if self.cancelled():
            return
        assert not self.done()
        if other.cancelled():
            self.cancel()
        else:
            exception = other.exception()
            if exception is not None:
                self.set_exception(exception)
            else:
                result = other.result()
                self.set_result(result)

def wrap_future(fut, loop=None):
    """Wrap concurrent.futures.Future object."""
    if isinstance(fut, Future):
        return fut
    assert isinstance(fut, executor.Future), \
        'concurrent.futures.Future is expected, got {0!r}'.format(fut)
    if loop is None:
        loop = events.get_event_loop()
    new_future = Future(loop=loop)

    def _check_cancel_other(f):
        if f.cancelled():
            fut.cancel()

    new_future.add_done_callback(_check_cancel_other)
    fut.add_done_callback(
        lambda future: loop.call_soon_threadsafe(
            new_future._copy_state, fut))
    return new_future
