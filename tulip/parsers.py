"""Parser is a generator function.

Parser receives data with generator's send() method and sends data to
destination DataBuffer. Parser receives ParserBuffer and DataBuffer objects
as a parameters of the first send() call, all subsequent send() calls should
send bytes objects. Parser sends parsed 'term' to desitnation buffer with
DataBuffer.feed_data() method. DataBuffer object should implement two methods.
feed_data() - parser uses this method to send parsed protocol data.
feed_eof() - parser uses this method for indication of end of parsing stream.
To indicate end of incoming data stream EofStream exception should be sent
into parser. Parser could throw exceptions.

There are three stages:

 * Data flow chain:

    1. Application creates StreamBuffer object for storing incoming data.
    2. StreamBuffer creates ParserBuffer as internal data buffer.
    3. Application create parser and set it into stream buffer:

        parser = http_request_parser()
        data_buffer = stream.set_parser(parser)

    3. At this stage StreamBuffer creates DataBuffer object and passes it
       and internal buffer into parser with first send() call.

        def set_parser(self, parser):
            next(parser)
            data_buffer = DataBuffer()
            parser.send((data_buffer, self._buffer))
            return data_buffer

    4. Application waits data on data_buffer.read()

        while True:
             msg = yield form data_buffer.read()
             ...

 * Data flow:

    1. Tulip's transport reads data from socket and sends data to protocol
       with data_received() call.
    2. Protocol sends data to StreamBuffer with feed_data() call.
    3. StreamBuffer sends data into parser with generator's send() method.
    4. Parser processes incoming data and sends parsed data
       to DataBuffer with feed_data()
    4. Application received parsed data from DataBuffer.read()

 * Eof:

    1. StreamBuffer recevies eof with feed_eof() call.
    2. StreamBuffer throws EofStream exception into parser.
    3. Then it unsets parser.

_SocketSocketTransport ->
   -> "protocol" -> StreamBuffer -> "parser" -> DataBuffer <- "application"

"""
__all__ = ['EofStream', 'StreamBuffer', 'StreamProtocol',
           'ParserBuffer', 'DataBuffer', 'lines_parser', 'chunks_parser']

import collections

from . import tasks
from . import futures
from . import protocols


class EofStream(Exception):
    """eof stream indication."""


class StreamBuffer:
    """StreamBuffer manages incoming bytes stream and protocol parsers.

    StreamBuffer uses ParserBuffer as internal buffer.

    set_parser() sets current parser, it creates DataBuffer object
    and sends ParserBuffer and DataBuffer into parser generator.

    unset_parser() sends EofStream into parser and then removes it.
    """

    def __init__(self):
        self._buffer = ParserBuffer()
        self._eof = False
        self._parser = None
        self._parser_buffer = None
        self._exception = None

    def exception(self):
        return self._exception

    def set_exception(self, exc):
        self._exception = exc

        if self._parser_buffer is not None:
            self._parser_buffer.set_exception(exc)
            self._parser = None
            self._parser_buffer = None

    def feed_data(self, data):
        """send data to current parser or store in buffer."""
        if not data:
            return

        if self._parser:
            try:
                self._parser.send(data)
            except StopIteration:
                self._parser = None
                self._parser_buffer = None
            except Exception as exc:
                self._parser_buffer.set_exception(exc)
                self._parser = None
                self._parser_buffer = None
        else:
            self._buffer.feed_data(data)

    def feed_eof(self):
        """send eof to all parsers, recursively."""
        if self._parser:
            try:
                self._parser.throw(EofStream())
            except StopIteration:
                pass
            except EofStream:
                self._parser_buffer.feed_eof()
            except Exception as exc:
                self._parser_buffer.set_exception(exc)

            self._parser = None
            self._parser_buffer = None

        self._eof = True

    def set_parser(self, p):
        """set parser to stream. return parser's DataStream."""
        if self._parser:
            self.unset_parser()

        out = DataBuffer()
        if self._exception:
            out.set_exception(self._exception)
            return out

        # init generator
        next(p)
        try:
            # initialize parser with data and parser buffers
            p.send((out, self._buffer))
        except StopIteration:
            pass
        except Exception as exc:
            out.set_exception(exc)
        else:
            # parser still require more data
            self._parser = p
            self._parser_buffer = out

            if self._eof:
                self.unset_parser()

        return out

    def unset_parser(self):
        """unset parser, send eof to the parser and then remove it."""
        assert self._parser is not None, 'Paser is not set.'

        try:
            self._parser.throw(EofStream())
        except StopIteration:
            pass
        except EofStream:
            self._parser_buffer.feed_eof()
        except Exception as exc:
            self._parser_buffer.set_exception(exc)
        finally:
            self._parser = None
            self._parser_buffer = None


class StreamProtocol(StreamBuffer, protocols.Protocol):
    """Tulip's stream protocol based on StreamBuffer"""

    transport = None

    data_received = StreamBuffer.feed_data

    eof_received = StreamBuffer.feed_eof

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        self.transport = None

        if exc is not None:
            self.set_exception(exc)
        else:
            self.feed_eof()


class DataBuffer:
    """DataBuffer is a destination for parsed data."""

    def __init__(self):
        self._buffer = collections.deque()
        self._eof = False
        self._waiter = None
        self._exception = None

    def exception(self):
        return self._exception

    def set_exception(self, exc):
        self._exception = exc

        waiter = self._waiter
        if waiter is not None:
            self._waiter = None
            if not waiter.cancelled():
                waiter.set_exception(exc)

    def feed_data(self, data):
        self._buffer.append(data)

        waiter = self._waiter
        if waiter is not None:
            self._waiter = None
            waiter.set_result(True)

    def feed_eof(self):
        self._eof = True

        waiter = self._waiter
        if waiter is not None:
            self._waiter = None
            waiter.set_result(False)

    @tasks.coroutine
    def read(self):
        if self._exception is not None:
            raise self._exception

        if not self._buffer and not self._eof:
            assert not self._waiter
            self._waiter = futures.Future()
            yield from self._waiter

        if self._buffer:
            return self._buffer.popleft()
        else:
            return None


class ParserBuffer(bytearray):
    """ParserBuffer is a bytearray extension.

    ParserBuffer provides helper methods for parsers.
    """

    def __init__(self, *args):
        super().__init__(*args)

        self.offset = 0
        self.size = 0
        self._writer = self._feed_data()
        next(self._writer)

    def _shrink(self):
        if self.offset:
            del self[:self.offset]
            self.offset = 0
            self.size = len(self)

    def _feed_data(self):
        while True:
            chunk = yield
            if chunk:
                chunk_len = len(chunk)
                self.size += chunk_len
                self.extend(chunk)

                # shrink buffer
                if (self.offset and len(self) > 5120):
                    self._shrink()

    def feed_data(self, data):
        self._writer.send(data)

    def read(self, size):
        """read() reads specified amount of bytes."""

        while True:
            if self.size >= size:
                start, end = self.offset, self.offset + size
                self.offset = end
                self.size = self.size - size
                return self[start:end]

            self._writer.send((yield))

    def readsome(self, size=None):
        """reads size of less amount of bytes."""

        while True:
            if self.size > 0:
                if size is None or self.size < size:
                    size = self.size

                start, end = self.offset, self.offset + size
                self.offset = end
                self.size = self.size - size

                return self[start:end]

            self._writer.send((yield))

    def readuntil(self, stop, limit=None, exc=ValueError):
        assert isinstance(stop, bytes) and stop, \
            'bytes is required: {!r}'.format(stop)

        stop_len = len(stop)

        while True:
            pos = self.find(stop, self.offset)
            if pos >= 0:
                end = pos + stop_len
                size = end - self.offset
                if limit is not None and size > limit:
                    raise exc('Line is too long.')

                start, self.offset = self.offset, end
                self.size = self.size - size

                return self[start:end]
            else:
                if limit is not None and self.size > limit:
                    raise exc('Line is too long.')

            self._writer.send((yield))

    def skip(self, size):
        """skip() skips specified amount of bytes."""

        while self.size < size:
            self._writer.send((yield))

        self.size -= size
        self.offset += size

    def skipuntil(self, stop):
        """skipuntil() reads until `stop` bytes sequence."""
        assert isinstance(stop, bytes) and stop, \
            'bytes is required: {!r}'.format(stop)

        stop_len = len(stop)

        while True:
            stop_line = self.find(stop, self.offset)
            if stop_line >= 0:
                end = stop_line + stop_len
                self.size = self.size - (end - self.offset)
                self.offset = end
                return
            else:
                self.size = 0
                self.offset = len(self) - 1

            self._writer.send((yield))

    def __bytes__(self):
        return bytes(self[self.offset:])


def lines_parser(limit=2**16, exc=ValueError):
    """Lines parser.

    lines parser splits a bytes stream into a chunks of data, each chunk ends
    with \n symbol."""
    out, buf = yield

    while True:
        out.feed_data((yield from buf.readuntil(b'\n', limit, exc)))


def chunks_parser(size=8196):
    """Chunks parser.

    chunks parser splits a bytes stream into a specified
    size chunks of data."""
    out, buf = yield

    while True:
        out.feed_data((yield from buf.read(size)))
