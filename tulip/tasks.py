"""Support for tasks, coroutines and the scheduler."""

__all__ = ['coroutine', 'Task',
           'FIRST_COMPLETED', 'FIRST_EXCEPTION', 'ALL_COMPLETED',
           'wait', 'wait_for', 'as_completed', 'sleep', 'async',
           ]

import collections
import concurrent.futures
import functools
import inspect

from . import events
from . import futures


def coroutine(func):
    """Decorator to mark coroutines.

    Decorator wraps non generator functions and returns generator wrapper.
    If non generator function returns generator of Future it yield-from it.

    TODO: This is a feel-good API only. It is not enforced.
    """
    if inspect.isgeneratorfunction(func):
        coro = func
    else:
        @functools.wraps(func)
        def coro(*args, **kw):
            res = func(*args, **kw)
            if isinstance(res, futures.Future) or inspect.isgenerator(res):
                res = yield from res
            return res

    coro._is_coroutine = True  # Not sure who can use this.
    return coro


# TODO: Do we need this?
def iscoroutinefunction(func):
    """Return True if func is a decorated coroutine function."""
    return (inspect.isgeneratorfunction(func) and
            getattr(func, '_is_coroutine', False))


# TODO: Do we need this?
def iscoroutine(obj):
    """Return True if obj is a coroutine object."""
    return inspect.isgenerator(obj)  # TODO: And what?


class Task(futures.Future):
    """A coroutine wrapped in a Future."""

    def __init__(self, coro, *, loop=None):
        assert inspect.isgenerator(coro)  # Must be a coroutine *object*.
        super().__init__(loop=loop)
        self._coro = coro
        self._fut_waiter = None
        self._must_cancel = False
        self._loop.call_soon(self._step)

    def __repr__(self):
        res = super().__repr__()
        if (self._must_cancel and
            self._state == futures._PENDING and
            '<PENDING' in res):
            res = res.replace('<PENDING', '<CANCELLING', 1)
        i = res.find('<')
        if i < 0:
            i = len(res)
        res = res[:i] + '(<{}>)'.format(self._coro.__name__) + res[i:]
        return res

    def cancel(self):
        if self.done():
            return False
        if self._fut_waiter is not None:
            # XXX: What to do if self._fut_waiter.cancel() returns False?
            # If that's anready cancelled future everything is ok.
            # What are other possible scenarios?
            waiter, self._fut_waiter = self._fut_waiter, None
            if waiter.cancel():
                return True
        # It must be the case that self._step is already scheduled.
        self._must_cancel = True
        return True

    def _step(self, value=None, exc=None):
        assert not self.done(), \
            '_step(): already done: {!r}, {!r}, {!r}'.format(self, value, exc)
        if self._must_cancel:
            assert self._fut_waiter is None
            exc = futures.CancelledError()
            value = None
        coro = self._coro
        self._fut_waiter = None
        # Call either coro.throw(exc) or coro.send(value).
        try:
            if exc is not None:
                result = coro.throw(exc)
            elif value is not None:
                result = coro.send(value)
            else:
                result = next(coro)
        except StopIteration as exc:
            self.set_result(exc.value)
        except futures.CancelledError as exc:
            super().cancel()  # I.e., Future.cancel(self).
        except Exception as exc:
            self.set_exception(exc)
        except BaseException as exc:
            self.set_exception(exc)
            raise
        else:
            if isinstance(result, futures.Future):
                # Yielded Future must come from Future.__iter__().
                if result._blocking:
                    result._blocking = False
                    result.add_done_callback(self._wakeup)
                    self._fut_waiter = result
                else:
                    self._loop.call_soon(
                        self._step, None,
                        RuntimeError(
                            'yield was used instead of yield from '
                            'in task {!r} with {!r}'.format(self, result)))
            elif result is None:
                # Bare yield relinquishes control for one event loop iteration.
                self._loop.call_soon(self._step)
            elif inspect.isgenerator(result):
                # Yielding a generator is just wrong.
                self._loop.call_soon(
                    self._step, None,
                    RuntimeError(
                        'yield was used instead of yield from for '
                        'generator in task {!r} with {}'.format(
                            self, result)))
            else:
                # Yielding something else is an error.
                self._loop.call_soon(
                    self._step, None,
                    RuntimeError(
                        'Task got bad yield: {!r}'.format(result)))
        self = None

    def _wakeup(self, future):
        try:
            value = future.result()
        except Exception as exc:
            self._step(None, exc)
        else:
            self._step(value, None)
        self = None  # Needed to break cycles when an exception occurs.


# wait() and as_completed() similar to those in PEP 3148.

FIRST_COMPLETED = concurrent.futures.FIRST_COMPLETED
FIRST_EXCEPTION = concurrent.futures.FIRST_EXCEPTION
ALL_COMPLETED = concurrent.futures.ALL_COMPLETED


@coroutine
def wait(fs, *, loop=None, timeout=None, return_when=ALL_COMPLETED):
    """Wait for the Futures and coroutines given by fs to complete.

    Coroutines will be wrapped in Tasks.

    Returns two sets of Future: (done, pending).

    Usage:

        done, pending = yield from tulip.wait(fs)

    Note: This does not raise TimeoutError! Futures that aren't done
    when the timeout occurs are returned in the second set.
    """
    if not fs:
        raise ValueError('Set of coroutines/Futures is empty.')

    if loop is None:
        loop = events.get_event_loop()

    fs = set(async(f, loop=loop) for f in fs)

    if return_when not in (FIRST_COMPLETED, FIRST_EXCEPTION, ALL_COMPLETED):
        raise ValueError('Invalid return_when value: {}'.format(return_when))
    return (yield from _wait(fs, timeout, return_when, loop))


@coroutine
def wait_for(fut, timeout, *, loop=None):
    """Wait for the single Future or coroutine to complete, with timeout.

    Coroutine will be wrapped in Task.

    Returns result of the Future or coroutine.  Raises TimeoutError when
    timeout occurs.

    Usage:

        result = yield from tulip.wait_for(fut, 10.0)

    """
    if loop is None:
        loop = events.get_event_loop()

    fut = async(fut, loop=loop)

    done, pending = yield from _wait([fut], timeout, FIRST_COMPLETED, loop)
    if done:
        return done.pop().result()

    raise futures.TimeoutError()


@coroutine
def _wait(fs, timeout, return_when, loop):
    """Internal helper for wait(return_when=FIRST_COMPLETED).

    The fs argument must be a set of Futures.
    The timeout argument is like for wait().
    """
    assert fs, 'Set of Futures is empty.'
    waiter = futures.Future(loop=loop)
    timeout_handle = None
    if timeout is not None:
        timeout_handle = loop.call_later(timeout, waiter.cancel)
    counter = len(fs)

    def _on_completion(f):
        nonlocal counter
        counter -= 1
        if (counter <= 0 or
            return_when == FIRST_COMPLETED or
            return_when == FIRST_EXCEPTION and (not f.cancelled() and
                                                f.exception() is not None)):
            if timeout_handle is not None:
                timeout_handle.cancel()
            waiter.cancel()

    for f in fs:
        f.add_done_callback(_on_completion)
    try:
        yield from waiter
    except futures.CancelledError:
        pass
    done, pending = set(), set()
    for f in fs:
        f.remove_done_callback(_on_completion)
        if f.done():
            done.add(f)
        else:
            pending.add(f)
    return done, pending


# This is *not* a @coroutine!  It is just an iterator (yielding Futures).
def as_completed(fs, *, loop=None, timeout=None):
    """Return an iterator whose values, when waited for, are Futures.

    This differs from PEP 3148; the proper way to use this is:

        for f in as_completed(fs):
            result = yield from f  # The 'yield from' may raise.
            # Use result.

    Raises TimeoutError if the timeout occurs before all Futures are
    done.

    Note: The futures 'f' are not necessarily members of fs.
    """
    loop = loop if loop is not None else events.get_event_loop()
    deadline = None if timeout is None else loop.time() + timeout
    todo = set(async(f, loop=loop) for f in fs)
    completed = collections.deque()

    @coroutine
    def _wait_for_one():
        while not completed:
            timeout = None
            if deadline is not None:
                timeout = deadline - loop.time()
                if timeout < 0:
                    raise futures.TimeoutError()
            done, pending = yield from _wait(
                todo, timeout, FIRST_COMPLETED, loop)
            # Multiple callers might be waiting for the same events
            # and getting the same outcome.  Dedupe by updating todo.
            for f in done:
                if f in todo:
                    todo.remove(f)
                    completed.append(f)
        f = completed.popleft()
        return f.result()  # May raise.

    for _ in range(len(todo)):
        yield _wait_for_one()


@coroutine
def sleep(delay, result=None, *, loop=None):
    """Coroutine that completes after a given time (in seconds)."""
    future = futures.Future(loop=loop)
    h = future._loop.call_later(delay, future.set_result, result)
    try:
        return (yield from future)
    finally:
        h.cancel()


def async(coro_or_future, *, loop=None):
    """Wrap a coroutine in a future.

    If the argument is a Future, it is returned directly.
    """
    if isinstance(coro_or_future, futures.Future):
        if loop is not None and loop is not coro_or_future._loop:
            raise ValueError('loop argument must agree with Future')
        return coro_or_future
    elif iscoroutine(coro_or_future):
        return Task(coro_or_future, loop=loop)
    else:
        raise TypeError('A Future or coroutine is required')
