import fcntl
import os
import traceback

from . import transports
from . import events


class UnixSubprocessTransport(transports.Transport):
    """Transport class managing a subprocess.

    TODO: Separate this into something that just handles pipe I/O,
    and something else that handles pipe setup, fork, and exec.
    """

    def __init__(self, protocol, args):
        self._protocol = protocol  # Not a factory! :-)
        self._args = args  # args[0] must be full path of binary.
        self._event_loop = events.get_event_loop()
        self._buffer = []
        self._eof = False
        rstdin, self._wstdin = os.pipe()
        self._rstdout, wstdout = os.pipe()

        # TODO: This is incredibly naive.  Should look at
        # subprocess.py for all the precautions around fork/exec.
        pid = os.fork()
        if not pid:
            # Child.
            try:
                os.dup2(rstdin, 0)
                os.dup2(wstdout, 1)
                # TODO: What to do with stderr?
                os.execv(args[0], args)
            except:
                try:
                    traceback.print_traceback()
                finally:
                    os._exit(127)

        # Parent.
        os.close(rstdin)
        os.close(wstdout)
        _setnonblocking(self._wstdin)
        _setnonblocking(self._rstdout)
        self._event_loop.call_soon(self._protocol.connection_made, self)
        self._event_loop.add_reader(self._rstdout, self._stdout_callback)

    def write(self, data):
        assert not self._eof
        if not data:
            return
        if not self._buffer:
            # Attempt to write it right away first.
            try:
                n = os.write(self._wstdin, data)
            except BlockingIOError:
                n = 0
            except Exception as exc:
                self._fatal_error(exc)
                return
            if n >= len(data):
                return
            if n > 0:
                data = data[n:]
            self._event_loop.add_writer(self._wstdin, self._stdin_callback)
        self._buffer.append(data)

    def write_eof(self):
        assert not self._eof
        assert self._wstdin >= 0
        self._eof = True
        if not self._buffer:
            self._event_loop.remove_writer(self._wstdin)
            os.close(self._wstdin)
            self._wstdin = -1

    def close(self):
        if not self._eof:
            self.write_eof()
        # XXX What else?

    def _fatal_error(self, exc):
        logging.error('Fatal error: %r', exc)
        if self._rstdout >= 0:
            os.close(self._rstdout)
            self._rstdout = -1
        if self._wstdin >= 0:
            os.close(self._wstdin)
            self._wstdin = -1
        self._eof = True
        self._buffer = None

    def _stdin_callback(self):
        data = b''.join(self._buffer)
        self._buffer = []
        try:
            if data:
                n = os.write(self._wstdin, data)
            else:
                n = 0
        except BlockingIOError:
            n = 0
        except Exception as exc:
            self._fatal_error(exc)
            return
        if n >= len(data):
            self._event_loop.remove_writer(self._wstdin)
            if self._eof:
                os.close(self._wstdin)
                self._wstdin = -1
            return
        if n > 0:
            data = data[n:]
        self._buffer.append(data)  # Try again later.

    def _stdout_callback(self):
        try:
            data = os.read(self._rstdout, 1024)
        except BlockingIOError:
            return
        if data:
            self._event_loop.call_soon(self._protocol.data_received, data)
        else:
            self._event_loop.remove_reader(self._rstdout)
            os.close(self._rstdout)
            self._rstdout = -1
            self._event_loop.call_soon(self._protocol.eof_received)


def _setnonblocking(fd):
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
