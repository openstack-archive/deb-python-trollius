import functools
import inspect
import os
import sys
try:
    import asyncio
except ImportError:
    asyncio = None

from . import compat
from . import futures
from .log import logger

# If you set _DEBUG to true, @coroutine will wrap the resulting
# generator objects in a CoroWrapper instance (defined below).  That
# instance will log a message when the generator is never iterated
# over, which may happen when you forget to use "yield" with a
# coroutine call.  Note that the value of the _DEBUG flag is taken
# when the decorator is used, so to be of any use it must be set
# before you define your coroutines.  A downside of using this feature
# is that tracebacks show entries for the CoroWrapper.__next__ method
# when _DEBUG is true.
_DEBUG = (not sys.flags.ignore_environment
          and bool(os.environ.get('TROLLIUSDEBUG')))


if compat.PY33:
    # Don't use the Return class on Python 3.3 and later to support asyncio
    # coroutines (to avoid the warning emited in Return destructor).
    #
    # The problem is that Return inherits from StopIteration.  "yield from
    # trollius_coroutine". Task._step() does not receive the Return exception,
    # because "yield from" handles it internally. So it's not possible to set
    # the raised attribute to True to avoid the warning in Return destructor.
    def Return(*args):
        if not args:
            value = None
        elif len(args) == 1:
            value = args[0]
        else:
            value = args
        return StopIteration(value)
else:
    class Return(StopIteration):
        def __init__(self, *args):
            StopIteration.__init__(self)
            if not args:
                self.value = None
            elif len(args) == 1:
                self.value = args[0]
            else:
                self.value = args
            self.raised = False

        def __del__(self):
            if not self.raised:
                logger.error('Return(%r) used without raise', self.value)


class CoroWrapper(object):
    # Wrapper for coroutine in _DEBUG mode.

    __slots__ = ['gen', 'func', '__name__', '__doc__', '__weakref__']

    def __init__(self, gen, func):
        assert inspect.isgenerator(gen), gen
        self.gen = gen
        self.func = func

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.gen)
    next = __next__

    def send(self, *value):
        # We use `*value` because of a bug in CPythons prior
        # to 3.4.1. See issue #21209 and test_yield_from_corowrapper
        # for details.  This workaround should be removed in 3.5.0.
        if len(value) == 1:
            value = value[0]
        return self.gen.send(value)

    def throw(self, exc):
        return self.gen.throw(exc)

    def close(self):
        return self.gen.close()

    @property
    def gi_frame(self):
        return self.gen.gi_frame

    @property
    def gi_running(self):
        return self.gen.gi_running

    @property
    def gi_code(self):
        return self.gen.gi_code

    def __del__(self):
        # Be careful accessing self.gen.frame -- self.gen might not exist.
        gen = getattr(self, 'gen', None)
        frame = getattr(gen, 'gi_frame', None)
        if frame is not None and frame.f_lasti == -1:
            func = self.func
            code = func.__code__
            filename = code.co_filename
            lineno = code.co_firstlineno
            logger.error(
                'Coroutine %r defined at %s:%s was never yielded from',
                func.__name__, filename, lineno)


def coroutine(func):
    """Decorator to mark coroutines.

    If the coroutine is not yielded from before it is destroyed,
    an error message is logged.
    """
    if inspect.isgeneratorfunction(func):
        coro = func
    else:
        @functools.wraps(func)
        def coro(*args, **kw):
            res = func(*args, **kw)
            if isinstance(res, futures.Future) or inspect.isgenerator(res):
                res = yield From(res)
            raise Return(res)

    if not _DEBUG:
        wrapper = coro
    else:
        @functools.wraps(func)
        def wrapper(*args, **kwds):
            w = CoroWrapper(coro(*args, **kwds), func)
            w.__name__ = coro.__name__
            w.__doc__ = coro.__doc__
            return w

    wrapper._is_coroutine = True  # For iscoroutinefunction().
    return wrapper


def iscoroutinefunction(func):
    """Return True if func is a decorated coroutine function."""
    return getattr(func, '_is_coroutine', False)


if asyncio is not None:
    # Accept also asyncio Future objects for interoperability
    _COROUTINE_TYPES = (CoroWrapper, asyncio.tasks.CoroWrapper)
else:
    _COROUTINE_TYPES = CoroWrapper


def iscoroutine(obj):
    """Return True if obj is a coroutine object."""
    return isinstance(obj, _COROUTINE_TYPES) or inspect.isgenerator(obj)

class FromWrapper(object):
    __slots__ = ('obj',)

    def __init__(self, obj):
        if isinstance(obj, FromWrapper):
            obj = obj.obj
            assert not isinstance(obj, FromWrapper)
        self.obj = obj

def From(obj):
    if not _DEBUG:
        return obj
    else:
        return FromWrapper(obj)
