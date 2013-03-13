"""Stream-related things."""

__all__ = ['StreamReader']

import collections

from . import futures
from . import tasks


class StreamReader:

    def __init__(self, limit=2**16):
        self.limit = limit  # Max line length.  (Security feature.)
        self.buffer = collections.deque()  # Deque of bytes objects.
        self.byte_count = 0  # Bytes in buffer.
        self.eof = False  # Whether we're done.
        self.waiter = None  # A future.
        self._exception = None

    def exception(self):
        return self._exception

    def set_exception(self, exc):
        self._exception = exc

        if self.waiter is not None:
            self.waiter.set_exception(exc)

    def feed_eof(self):
        self.eof = True
        waiter = self.waiter
        if waiter is not None:
            self.waiter = None
            waiter.set_result(True)

    def feed_data(self, data):
        if not data:
            return

        self.buffer.append(data)
        self.byte_count += len(data)

        waiter = self.waiter
        if waiter is not None:
            self.waiter = None
            waiter.set_result(False)

    @tasks.coroutine
    def readline(self):
        if self._exception is not None:
            raise self._exception

        parts = []
        parts_size = 0
        not_enough = True

        while not_enough:
            while self.buffer and not_enough:
                data = self.buffer.popleft()
                ichar = data.find(b'\n')
                if ichar < 0:
                    parts.append(data)
                    parts_size += len(data)
                else:
                    ichar += 1
                    head, tail = data[:ichar], data[ichar:]
                    if tail:
                        self.buffer.appendleft(tail)
                    not_enough = False
                    parts.append(head)
                    parts_size += len(head)

                if parts_size > self.limit:
                    self.byte_count -= parts_size
                    raise ValueError('Line is too long')

            if self.eof:
                break

            if not_enough:
                assert self.waiter is None
                self.waiter = futures.Future()
                yield from self.waiter

        line = b''.join(parts)
        self.byte_count -= parts_size

        return line

    @tasks.coroutine
    def read(self, n=-1):
        if self._exception is not None:
            raise self._exception

        if not n:
            return b''

        if n < 0:
            while not self.eof:
                assert not self.waiter
                self.waiter = futures.Future()
                yield from self.waiter
        else:
            if not self.byte_count and not self.eof:
                assert not self.waiter
                self.waiter = futures.Future()
                yield from self.waiter

        if n < 0 or self.byte_count <= n:
            data = b''.join(self.buffer)
            self.buffer.clear()
            self.byte_count = 0
            return data

        parts = []
        parts_bytes = 0
        while self.buffer and parts_bytes < n:
            data = self.buffer.popleft()
            data_bytes = len(data)
            if n < parts_bytes + data_bytes:
                data_bytes = n - parts_bytes
                data, rest = data[:data_bytes], data[data_bytes:]
                self.buffer.appendleft(rest)

            parts.append(data)
            parts_bytes += data_bytes
            self.byte_count -= data_bytes

        return b''.join(parts)

    @tasks.coroutine
    def readexactly(self, n):
        if self._exception is not None:
            raise self._exception

        if n <= 0:
            return b''

        while self.byte_count < n and not self.eof:
            assert not self.waiter
            self.waiter = futures.Future()
            yield from self.waiter

        return (yield from self.read(n))
