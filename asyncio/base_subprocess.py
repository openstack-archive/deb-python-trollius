import collections
import subprocess

from . import protocols
from . import tasks
from . import transports


STDIN = 0
STDOUT = 1
STDERR = 2


class BaseSubprocessTransport(transports.SubprocessTransport):

    def __init__(self, loop, protocol, args, shell,
                 stdin, stdout, stderr, bufsize,
                 extra=None, **kwargs):
        super().__init__(extra)
        self._protocol = protocol
        self._loop = loop

        self._pipes = {}
        if stdin == subprocess.PIPE:
            self._pipes[STDIN] = None
        if stdout == subprocess.PIPE:
            self._pipes[STDOUT] = None
        if stderr == subprocess.PIPE:
            self._pipes[STDERR] = None
        self._pending_calls = collections.deque()
        self._finished = False
        self._returncode = None
        self._start(args=args, shell=shell, stdin=stdin, stdout=stdout,
                    stderr=stderr, bufsize=bufsize, **kwargs)
        self._extra['subprocess'] = self._proc

    def _start(self, args, shell, stdin, stdout, stderr, bufsize, **kwargs):
        raise NotImplementedError

    def _make_write_subprocess_pipe_proto(self, fd):
        raise NotImplementedError

    def _make_read_subprocess_pipe_proto(self, fd):
        raise NotImplementedError

    def close(self):
        for proto in self._pipes.values():
            proto.pipe.close()
        if self._returncode is None:
            self.terminate()

    def get_pid(self):
        return self._proc.pid

    def get_returncode(self):
        return self._returncode

    def get_pipe_transport(self, fd):
        if fd in self._pipes:
            return self._pipes[fd].pipe
        else:
            return None

    def send_signal(self, signal):
        self._proc.send_signal(signal)

    def terminate(self):
        self._proc.terminate()

    def kill(self):
        self._proc.kill()

    @tasks.coroutine
    def _post_init(self):
        proc = self._proc
        loop = self._loop
        if proc.stdin is not None:
            transp, proto = yield from loop.connect_write_pipe(
                lambda: WriteSubprocessPipeProto(self, STDIN),
                proc.stdin)
        if proc.stdout is not None:
            transp, proto = yield from loop.connect_read_pipe(
                lambda: ReadSubprocessPipeProto(self, STDOUT),
                proc.stdout)
        if proc.stderr is not None:
            transp, proto = yield from loop.connect_read_pipe(
                lambda: ReadSubprocessPipeProto(self, STDERR),
                proc.stderr)
        if not self._pipes:
            self._try_connected()

    def _call(self, cb, *data):
        if self._pending_calls is not None:
            self._pending_calls.append((cb, data))
        else:
            self._loop.call_soon(cb, *data)

    def _try_connected(self):
        assert self._pending_calls is not None
        if all(p is not None and p.connected for p in self._pipes.values()):
            self._loop.call_soon(self._protocol.connection_made, self)
            for callback, data in self._pending_calls:
                self._loop.call_soon(callback, *data)
            self._pending_calls = None

    def _pipe_connection_lost(self, fd, exc):
        self._call(self._protocol.pipe_connection_lost, fd, exc)
        self._try_finish()

    def _pipe_data_received(self, fd, data):
        self._call(self._protocol.pipe_data_received, fd, data)

    def _process_exited(self, returncode):
        assert returncode is not None, returncode
        assert self._returncode is None, self._returncode
        self._returncode = returncode
        self._loop._subprocess_closed(self)
        self._call(self._protocol.process_exited)
        self._try_finish()

    def _try_finish(self):
        assert not self._finished
        if self._returncode is None:
            return
        if all(p is not None and p.disconnected
               for p in self._pipes.values()):
            self._finished = True
            self._loop.call_soon(self._call_connection_lost, None)

    def _call_connection_lost(self, exc):
        try:
            self._protocol.connection_lost(exc)
        finally:
            self._proc = None
            self._protocol = None
            self._loop = None


class WriteSubprocessPipeProto(protocols.BaseProtocol):
    pipe = None

    def __init__(self, proc, fd):
        self.proc = proc
        self.fd = fd
        self.connected = False
        self.disconnected = False
        proc._pipes[fd] = self

    def connection_made(self, transport):
        self.connected = True
        self.pipe = transport
        self.proc._try_connected()

    def connection_lost(self, exc):
        self.disconnected = True
        self.proc._pipe_connection_lost(self.fd, exc)

    def eof_received(self):
        pass


class ReadSubprocessPipeProto(WriteSubprocessPipeProto,
                              protocols.Protocol):

    def data_received(self, data):
        self.proc._pipe_data_received(self.fd, data)
