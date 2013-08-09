"""Event loop and event loop policy.

Beyond the PEP:
- Only the main thread has a default event loop.
"""

__all__ = ['AbstractEventLoopPolicy', 'DefaultEventLoopPolicy',
           'AbstractEventLoop', 'TimerHandle', 'Handle', 'make_handle',
           'get_event_loop_policy', 'set_event_loop_policy',
           'get_event_loop', 'set_event_loop', 'new_event_loop',
           ]

import sys
import threading
import socket

from .log import tulip_log


class Handle:
    """Object returned by callback registration methods."""

    def __init__(self, callback, args):
        self._callback = callback
        self._args = args
        self._cancelled = False

    def __repr__(self):
        res = 'Handle({}, {})'.format(self._callback, self._args)
        if self._cancelled:
            res += '<cancelled>'
        return res

    def cancel(self):
        self._cancelled = True

    def _run(self):
        try:
            self._callback(*self._args)
        except Exception:
            tulip_log.exception('Exception in callback %s %r',
                                self._callback, self._args)
        self = None  # Needed to break cycles when an exception occurs.


def make_handle(callback, args):
    # TODO: Inline this?
    assert not isinstance(callback, Handle), 'A Handle is not a callback'
    return Handle(callback, args)


class TimerHandle(Handle):
    """Object returned by timed callback registration methods."""

    def __init__(self, when, callback, args):
        assert when is not None
        super().__init__(callback, args)

        self._when = when

    def __repr__(self):
        res = 'TimerHandle({}, {}, {})'.format(self._when,
                                               self._callback,
                                               self._args)
        if self._cancelled:
            res += '<cancelled>'

        return res

    def __hash__(self):
        return hash(self._when)

    def __lt__(self, other):
        return self._when < other._when

    def __le__(self, other):
        if self._when < other._when:
            return True
        return self.__eq__(other)

    def __gt__(self, other):
        return self._when > other._when

    def __ge__(self, other):
        if self._when > other._when:
            return True
        return self.__eq__(other)

    def __eq__(self, other):
        if isinstance(other, TimerHandle):
            return (self._when == other._when and
                    self._callback == other._callback and
                    self._args == other._args and
                    self._cancelled == other._cancelled)
        return NotImplemented

    def __ne__(self, other):
        equal = self.__eq__(other)
        return NotImplemented if equal is NotImplemented else not equal


class AbstractEventLoop:
    """Abstract event loop."""

    # Running and stopping the event loop.

    def run_forever(self):
        """Run the event loop until stop() is called."""
        raise NotImplementedError

    def run_until_complete(self, future, timeout=None):
        """Run the event loop until a Future is done.

        Return the Future's result, or raise its exception.

        If timeout is not None, run it for at most that long;
        if the Future is still not done, raise TimeoutError
        (but don't cancel the Future).
        """
        raise NotImplementedError

    def stop(self):
        """Stop the event loop as soon as reasonable.

        Exactly how soon that is may depend on the implementation, but
        no more I/O callbacks should be scheduled.
        """
        raise NotImplementedError

    def is_running(self):
        """Return whether the event loop is currently running."""
        raise NotImplementedError

    # Methods scheduling callbacks.  All these return Handles.

    def call_soon(self, callback, *args):
        return self.call_later(0, callback, *args)

    def call_later(self, delay, callback, *args):
        raise NotImplementedError

    def call_at(self, when, callback, *args):
        raise NotImplementedError

    def time(self):
        raise NotImplementedError

    # Methods for interacting with threads.

    def call_soon_threadsafe(self, callback, *args):
        raise NotImplementedError

    def run_in_executor(self, executor, callback, *args):
        raise NotImplementedError

    def set_default_executor(self, executor):
        raise NotImplementedError

    # Network I/O methods returning Futures.

    def getaddrinfo(self, host, port, *, family=0, type=0, proto=0, flags=0):
        raise NotImplementedError

    def getnameinfo(self, sockaddr, flags=0):
        raise NotImplementedError

    def create_connection(self, protocol_factory, host=None, port=None, *,
                          ssl=None, family=0, proto=0, flags=0, sock=None,
                          local_addr=None):
        raise NotImplementedError

    def start_serving(self, protocol_factory, host=None, port=None, *,
                      family=socket.AF_UNSPEC, flags=socket.AI_PASSIVE,
                      sock=None, backlog=100, ssl=None, reuse_address=None):
        """Creates a TCP server bound to host and port and return a
        Task whose result will be a list of socket objects which will
        later be handled by protocol_factory.

        If host is an empty string or None all interfaces are assumed
        and a list of multiple sockets will be returned (most likely
        one for IPv4 and another one for IPv6).

        family can be set to either AF_INET or AF_INET6 to force the
        socket to use IPv4 or IPv6. If not set it will be determined
        from host (defaults to AF_UNSPEC).

        flags is a bitmask for getaddrinfo().

        sock can optionally be specified in order to use a preexisting
        socket object.

        backlog is the maximum number of queued connections passed to
        listen() (defaults to 100).

        ssl can be set to an SSLContext to enable SSL over the
        accepted connections.

        reuse_address tells the kernel to reuse a local socket in
        TIME_WAIT state, without waiting for its natural timeout to
        expire. If not specified will automatically be set to True on
        UNIX.
        """
        raise NotImplementedError

    def stop_serving(self, sock):
        """Stop listening for incoming connections. Close socket."""
        raise NotImplementedError

    def create_datagram_endpoint(self, protocol_factory,
                                 local_addr=None, remote_addr=None, *,
                                 family=0, proto=0, flags=0):
        raise NotImplementedError

    def connect_read_pipe(self, protocol_factory, pipe):
        """Register read pipe in eventloop.

        protocol_factory should instantiate object with Protocol interface.
        pipe is file-like object already switched to nonblocking.
        Return pair (transport, protocol), where transport support
        ReadTransport ABC"""
        # The reason to accept file-like object instead of just file descriptor
        # is: we need to own pipe and close it at transport finishing
        # Can got complicated errors if pass f.fileno(),
        # close fd in pipe transport then close f and vise versa.
        raise NotImplementedError

    def connect_write_pipe(self, protocol_factory, pipe):
        """Register write pipe in eventloop.

        protocol_factory should instantiate object with BaseProtocol interface.
        Pipe is file-like object already switched to nonblocking.
        Return pair (transport, protocol), where transport support
        WriteTransport ABC"""
        # The reason to accept file-like object instead of just file descriptor
        # is: we need to own pipe and close it at transport finishing
        # Can got complicated errors if pass f.fileno(),
        # close fd in pipe transport then close f and vise versa.
        raise NotImplementedError

    #def spawn_subprocess(self, protocol_factory, pipe):
    #    raise NotImplementedError

    # Ready-based callback registration methods.
    # The add_*() methods return None.
    # The remove_*() methods return True if something was removed,
    # False if there was nothing to delete.

    def add_reader(self, fd, callback, *args):
        raise NotImplementedError

    def remove_reader(self, fd):
        raise NotImplementedError

    def add_writer(self, fd, callback, *args):
        raise NotImplementedError

    def remove_writer(self, fd):
        raise NotImplementedError

    # Completion based I/O methods returning Futures.

    def sock_recv(self, sock, nbytes):
        raise NotImplementedError

    def sock_sendall(self, sock, data):
        raise NotImplementedError

    def sock_connect(self, sock, address):
        raise NotImplementedError

    def sock_accept(self, sock):
        raise NotImplementedError

    # Signal handling.

    def add_signal_handler(self, sig, callback, *args):
        raise NotImplementedError

    def remove_signal_handler(self, sig):
        raise NotImplementedError


class AbstractEventLoopPolicy:
    """Abstract policy for accessing the event loop."""

    def get_event_loop(self):
        """XXX"""
        raise NotImplementedError

    def set_event_loop(self, loop):
        """XXX"""
        raise NotImplementedError

    def new_event_loop(self):
        """XXX"""
        raise NotImplementedError


class DefaultEventLoopPolicy(threading.local, AbstractEventLoopPolicy):
    """Default policy implementation for accessing the event loop.

    In this policy, each thread has its own event loop.  However, we
    only automatically create an event loop by default for the main
    thread; other threads by default have no event loop.

    Other policies may have different rules (e.g. a single global
    event loop, or automatically creating an event loop per thread, or
    using some other notion of context to which an event loop is
    associated).
    """

    _loop = None
    _set_called = False

    def get_event_loop(self):
        """Get the event loop.

        This may be None or an instance of EventLoop.
        """
        if (self._loop is None and
            not self._set_called and
            threading.current_thread().name == 'MainThread'):
            self._loop = self.new_event_loop()
        assert self._loop is not None, \
               ('There is no current event loop in thread %r.' %
                threading.current_thread().name)
        return self._loop

    def set_event_loop(self, loop):
        """Set the event loop."""
        # TODO: The isinstance() test violates the PEP.
        self._set_called = True
        assert loop is None or isinstance(loop, AbstractEventLoop)
        self._loop = loop

    def new_event_loop(self):
        """Create a new event loop.

        You must call set_event_loop() to make this the current event
        loop.
        """
        if sys.platform == 'win32':  # pragma: no cover
            from . import windows_events
            return windows_events.SelectorEventLoop()
        else:  # pragma: no cover
            from . import unix_events
            return unix_events.SelectorEventLoop()


# Event loop policy.  The policy itself is always global, even if the
# policy's rules say that there is an event loop per thread (or other
# notion of context).  The default policy is installed by the first
# call to get_event_loop_policy().
_event_loop_policy = None


def get_event_loop_policy():
    """XXX"""
    global _event_loop_policy
    if _event_loop_policy is None:
        _event_loop_policy = DefaultEventLoopPolicy()
    return _event_loop_policy


def set_event_loop_policy(policy):
    """XXX"""
    global _event_loop_policy
    # TODO: The isinstance() test violates the PEP.
    assert policy is None or isinstance(policy, AbstractEventLoopPolicy)
    _event_loop_policy = policy


def get_event_loop():
    """XXX"""
    return get_event_loop_policy().get_event_loop()


def set_event_loop(loop):
    """XXX"""
    get_event_loop_policy().set_event_loop(loop)


def new_event_loop():
    """XXX"""
    return get_event_loop_policy().new_event_loop()
