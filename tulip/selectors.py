"""Select module.

This module supports asynchronous I/O on multiple file descriptors.
"""

import logging

from select import *


# generic events, that must be mapped to implementation-specific ones
# read event
SELECT_IN  = (1 << 0)
# write event
SELECT_OUT = (1 << 1)
# connect event
SELECT_CONNECT = SELECT_OUT


def _fileobj_to_fd(fileobj):
    """Return a file descriptor from a file object.

    Parameters:
    fileobj -- file descriptor, or any object with a `fileno()` method

    Returns:
    corresponding file descriptor
    """
    if isinstance(fileobj, int):
        fd = fileobj
    else:
        try:
            fd = int(fileobj.fileno())
        except (ValueError, TypeError):
            raise ValueError("Invalid file object: {!r}".format(fileobj))
    return fd


class _Key:
    """Object used internally to associate a file object to its backing file
    descriptor, selected event mask and attached data."""

    def __init__(self, fileobj, events, data=None):
        self.fileobj = fileobj
        self.fd = _fileobj_to_fd(fileobj)
        self.events = events
        self.data = data

    def __repr__(self):
        return '{}<fileobje={}, fd={}, events={:#x}, data={}>'.format(
            self.__class__.__name__,
            self.fileobj, self.fd, self.events, self.data)


class _BaseSelector:
    """Base selector class.

    A selector supports registering file objects to be monitored for specific
    I/O events.

    A file object is a file descriptor or any object with a `fileno()` method.
    An arbitrary object can be attached to the file object, which can be used
    for example to store context information, a callback, etc.

    A selector can use various implementations (select(), poll(), epoll()...)
    depending on the platform. The default `Selector` class uses the most
    performant implementation on the current platform.
    """

    def __init__(self):
        # this maps file descriptors to keys
        self._fd_to_key = {}
        # this maps file objects to keys - for fast (un)registering
        self._fileobj_to_key = {}

    def register(self, fileobj, events, data=None):
        """Register a file object.

        Parameters:
        fileobj -- file object
        events  -- events to monitor (bitwise mask of SELECT_IN|SELECT_OUT)
        data    -- attached data

        Returns:
        _Key instance
        """
        if (not events) or (events & ~(SELECT_IN|SELECT_OUT)):
            raise ValueError("Invalid events: {}".format(events))

        if fileobj in self._fileobj_to_key:
            raise ValueError("{!r} is already registered".format(fileobj))

        key = _Key(fileobj, events, data)
        self._fd_to_key[key.fd] = key
        self._fileobj_to_key[fileobj] = key
        return key

    def unregister(self, fileobj):
        """Unregister a file object.

        Parameters:
        fileobj -- file object

        Returns:
        _Key instance
        """
        try:
            key = self._fileobj_to_key[fileobj]
            del self._fd_to_key[key.fd]
            del self._fileobj_to_key[fileobj]
        except KeyError:
            raise ValueError("{!r} is not registered".format(fileobj))
        return key

    def modify(self, fileobj, events, data=None):
        """Change a registered file object monitored events or attached data.

        Parameters:
        fileobj -- file object
        events  -- events to monitor (bitwise mask of SELECT_IN|SELECT_OUT)
        data    -- attached data
        """
        self.unregister(fileobj)
        self.register(fileobj, events, data)

    def select(self, timeout=None):
        """Perform the actual selection, until some monitored file objects are
        ready or a timeout expires.
        
        Parameters:
        timeout -- if timeout > 0, this specifies the maximum wait time, in
                   seconds
                   if timeout == 0, the select() call won't block, and will
                   report the currently ready file objects
                   if timeout is None, select() will block until a monitored
                   file object becomes ready

        Returns:
        list of (fileobj, events, attached data) for ready file objects
        `events` is a bitwise mask of SELECT_IN|SELECT_OUT
        """
        raise NotImplementedError()

    def close(self):
        """Close the selector.

        This must be called to make sure that any underlying resource is freed.
        """
        self._fd_to_key.clear()
        self._fileobj_to_key.clear()

    def get_info(self, fileobj):
        """Return information about a registered file object.

        Returns:
        (events, data) associated to this file object

        Raises KeyError if the file object is not registered.
        """
        try:
            key = self._fileobj_to_key[fileobj]
        except KeyError:
            raise KeyError("{} is not registered".format(fileobj))
        return key.events, key.data

    def registered_count(self):
        """Return the number of registered file objects.

        Returns:
        number of currently registered file objects
        """
        return len(self._fd_to_key)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _key_from_fd(self, fd):
        """Return the key associated to a given file descriptor.

        Parameters:
        fd -- file descriptor

        Returns:
        corresponding key
        """
        try:
            return self._fd_to_key[fd]
        except KeyError:
            raise RuntimeError("No key found for fd {}".format(fd))


class SelectSelector(_BaseSelector):
    """Select-based selector."""

    def __init__(self):
        super().__init__()
        self._readers = set()
        self._writers = set()

    def register(self, fileobj, events, data=None):
        key = super().register(fileobj, events, data)
        if events & SELECT_IN:
            self._readers.add(key.fd)
        if events & SELECT_OUT:
            self._writers.add(key.fd)
        return key

    def unregister(self, fileobj):
        key = super().unregister(fileobj)
        self._readers.discard(key.fd)
        self._writers.discard(key.fd)
        return key

    def select(self, timeout=None):
        r, w, _ = select(self._readers, self._writers, [], timeout)
        r = set(r)
        w = set(w)
        ready = []
        for fd in r | w:
            events = 0
            if fd in r:
                events |= SELECT_IN
            if fd in w:
                events |= SELECT_OUT

            key = self._key_from_fd(fd)
            ready.append((key.fileobj, events, key.data))
        return ready


if 'poll' in globals():

    class PollSelector(_BaseSelector):
        """Poll-based selector."""
    
        def __init__(self):
            super().__init__()
            self._poll = poll()
    
        def register(self, fileobj, events, data=None):
            key = super().register(fileobj, events, data)
            poll_events = 0
            if events & SELECT_IN:
                poll_events |= POLLIN
            if events & SELECT_OUT:
                poll_events |= POLLOUT
            self._poll.register(key.fd, poll_events)
            return key
    
        def unregister(self, fileobj):
            key = super().unregister(fileobj)
            self._poll.unregister(key.fd)
            return key
    
        def select(self, timeout=None):
            timeout = None if timeout is None else int(1000 * timeout)
            ready = []
            for fd, event in self._poll.poll(timeout):
                events = 0
                if event & ~POLLIN:
                    events |= SELECT_OUT
                if event & ~POLLOUT:
                    events |= SELECT_IN
    
                key = self._key_from_fd(fd)
                ready.append((key.fileobj, events, key.data))
            return ready


if 'epoll' in globals():

    class EpollSelector(_BaseSelector):
        """Epoll-based selector."""
    
        def __init__(self):
            super().__init__()
            self._epoll = epoll()
    
        def register(self, fileobj, events, data=None):
            key = super().register(fileobj, events, data)
            epoll_events = 0
            if events & SELECT_IN:
                epoll_events |= EPOLLIN
            if events & SELECT_OUT:
                epoll_events |= EPOLLOUT
            self._epoll.register(key.fd, epoll_events)
            return key
    
        def unregister(self, fileobj):
            key = super().unregister(fileobj)
            self._epoll.unregister(key.fd)
            return key
    
        def select(self, timeout=None):
            timeout = -1 if timeout is None else timeout
            max_ev = self.registered_count()
            ready = []
            for fd, event in self._epoll.poll(timeout, max_ev):
                events = 0
                if event & ~EPOLLIN:
                    events |= SELECT_OUT
                if event & ~EPOLLOUT:
                    events |= SELECT_IN
    
                key = self._key_from_fd(fd)
                ready.append((key.fileobj, events, key.data))
            return ready
    
        def close(self):
            super().close()
            self._epoll.close()


if 'kqueue' in globals():

    class KqueueSelector(_BaseSelector):
        """Kqueue-based selector."""
    
        def __init__(self):
            super().__init__()
            self._kqueue = kqueue()

        def unregister(self, fileobj):
            key = super().unregister(fileobj)
            mask = 0
            if key.events & SELECT_IN:
                mask |= KQ_FILTER_READ
            if key.events & SELECT_OUT:
                mask |= KQ_FILTER_WRITE
            kev = kevent(key.fd, mask, KQ_EV_DELETE)
            self._kqueue.control([kev], 0, 0)
            return key
    
        def register(self, fileobj, events, data=None):
            key = super().register(fileobj, events, data)
            if events & SELECT_IN:
                kev = kevent(key.fd, KQ_FILTER_READ, KQ_EV_ADD)
                self._kqueue.control([kev], 0, 0)
            if events & SELECT_OUT:
                kev = kevent(key.fd, KQ_FILTER_WRITE, KQ_EV_ADD)
                self._kqueue.control([kev], 0, 0)
            return key
    
        def select(self, timeout=None):
            max_ev = self.registered_count()
            ready = []
            for kev in self._kqueue.control(None, max_ev, timeout):
                fd = kev.ident
                flag = kev.filter
                events = 0
                if flag == KQ_FILTER_READ:
                    events |= SELECT_IN
                if flag == KQ_FILTER_WRITE:
                    events |= SELECT_OUT

                key = self._key_from_fd(fd)
                ready.append((key.fileobj, events, key.data))
            return ready
    
        def close(self):
            super().close()
            self._kqueue.close()


# Choose the best implementation: roughly, epoll|kqueue > poll > select.
# select() also can't accept a FD > FD_SETSIZE (usually around 1024)
if 'KqueueSelector' in globals():
    Selector = KqueueSelector
elif 'EpollSelector' in globals():
    Selector = EpollSelector
elif 'PollSelector' in globals():
    Selector = PollSelector
else:
    Selector = SelectSelector
