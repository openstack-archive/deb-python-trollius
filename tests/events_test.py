"""Tests for events.py."""

import gc
import io
import os
import re
import signal
import socket
try:
    import ssl
except ImportError:
    ssl = None
import sys
import threading
import time
import errno
import unittest
import unittest.mock
from test.support import find_unused_port


from tulip import futures
from tulip import events
from tulip import transports
from tulip import protocols
from tulip import selector_events
from tulip import tasks
from tulip import test_utils


class MyProto(protocols.Protocol):
    done = None

    def __init__(self, create_future=False):
        self.state = 'INITIAL'
        self.nbytes = 0
        if create_future:
            self.done = futures.Future()

    def connection_made(self, transport):
        self.transport = transport
        assert self.state == 'INITIAL', self.state
        self.state = 'CONNECTED'
        transport.write(b'GET / HTTP/1.0\r\nHost: example.com\r\n\r\n')

    def data_received(self, data):
        assert self.state == 'CONNECTED', self.state
        self.nbytes += len(data)

    def eof_received(self):
        assert self.state == 'CONNECTED', self.state
        self.state = 'EOF'

    def connection_lost(self, exc):
        assert self.state in ('CONNECTED', 'EOF'), self.state
        self.state = 'CLOSED'
        if self.done:
            self.done.set_result(None)


class MyDatagramProto(protocols.DatagramProtocol):
    done = None

    def __init__(self, create_future=False):
        self.state = 'INITIAL'
        self.nbytes = 0
        if create_future:
            self.done = futures.Future()

    def connection_made(self, transport):
        self.transport = transport
        assert self.state == 'INITIAL', self.state
        self.state = 'INITIALIZED'

    def datagram_received(self, data, addr):
        assert self.state == 'INITIALIZED', self.state
        self.nbytes += len(data)

    def connection_refused(self, exc):
        assert self.state == 'INITIALIZED', self.state

    def connection_lost(self, exc):
        assert self.state == 'INITIALIZED', self.state
        self.state = 'CLOSED'
        if self.done:
            self.done.set_result(None)


class MyReadPipeProto(protocols.Protocol):
    done = None

    def __init__(self, create_future=False):
        self.state = ['INITIAL']
        self.nbytes = 0
        self.transport = None
        if create_future:
            self.done = futures.Future()

    def connection_made(self, transport):
        self.transport = transport
        assert self.state == ['INITIAL'], self.state
        self.state.append('CONNECTED')

    def data_received(self, data):
        assert self.state == ['INITIAL', 'CONNECTED'], self.state
        self.nbytes += len(data)

    def eof_received(self):
        assert self.state == ['INITIAL', 'CONNECTED'], self.state
        self.state.append('EOF')
        self.transport.close()

    def connection_lost(self, exc):
        assert self.state == ['INITIAL', 'CONNECTED', 'EOF'], self.state
        self.state.append('CLOSED')
        if self.done:
            self.done.set_result(None)


class MyWritePipeProto(protocols.Protocol):
    done = None

    def __init__(self, create_future=False):
        self.state = 'INITIAL'
        self.transport = None
        if create_future:
            self.done = futures.Future()

    def connection_made(self, transport):
        self.transport = transport
        assert self.state == 'INITIAL', self.state
        self.state = 'CONNECTED'

    def connection_lost(self, exc):
        assert self.state == 'CONNECTED', self.state
        self.state = 'CLOSED'
        if self.done:
            self.done.set_result(None)


class EventLoopTestsMixin:

    def setUp(self):
        super().setUp()
        self.loop = self.create_event_loop()
        events.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()
        gc.collect()
        super().tearDown()

    def test_run_nesting(self):
        @tasks.coroutine
        def coro():
            self.assertTrue(self.loop.is_running())
            self.loop.run_until_complete(tasks.sleep(0.1))

        self.assertRaises(
            RuntimeError, self.loop.run_until_complete, coro())

    def test_run_once_nesting(self):
        @tasks.coroutine
        def coro():
            tasks.sleep(0.1)
            self.loop.run_once()

        self.assertRaises(
            RuntimeError,
            self.loop.run_until_complete, coro())

    def test_run_once_block(self):
        called = False

        def callback():
            nonlocal called
            called = True

        def run():
            time.sleep(0.1)
            self.loop.call_soon_threadsafe(callback)

        self.loop.run_once(0)  # windows iocp

        t = threading.Thread(target=run)
        t0 = time.monotonic()
        t.start()
        self.loop.run_once(None)
        t1 = time.monotonic()
        t.join()
        self.assertTrue(called)
        self.assertTrue(0.09 < t1-t0 <= 0.15)

    def test_call_later(self):
        results = []

        def callback(arg):
            results.append(arg)
            self.loop.stop()

        self.loop.call_later(0.1, callback, 'hello world')
        t0 = time.monotonic()
        self.loop.run_forever()
        t1 = time.monotonic()
        self.assertEqual(results, ['hello world'])
        self.assertTrue(0.09 <= t1-t0 <= 0.12)

    def test_call_soon(self):
        results = []

        def callback(arg1, arg2):
            results.append((arg1, arg2))
            self.loop.stop()

        self.loop.call_soon(callback, 'hello', 'world')
        self.loop.run_forever()
        self.assertEqual(results, [('hello', 'world')])

    def test_call_soon_threadsafe(self):
        results = []

        def callback(arg):
            results.append(arg)
            if len(results) >= 2:
                self.loop.stop()

        def run_in_thread():
            self.loop.call_soon_threadsafe(callback, 'hello')

        t = threading.Thread(target=run_in_thread)
        self.loop.call_later(0.1, callback, 'world')
        t0 = time.monotonic()
        t.start()
        self.loop.run_forever()
        t1 = time.monotonic()
        t.join()
        self.assertEqual(results, ['hello', 'world'])
        self.assertTrue(t1-t0 >= 0.09)

    def test_call_soon_threadsafe_same_thread(self):
        results = []

        def callback(arg):
            results.append(arg)
            if len(results) >= 2:
                self.loop.stop()

        self.loop.call_later(0.1, callback, 'world')
        self.loop.call_soon_threadsafe(callback, 'hello')
        self.loop.run_forever()
        self.assertEqual(results, ['hello', 'world'])

    def test_run_in_executor(self):
        def run(arg):
            time.sleep(0.1)
            return arg
        f2 = self.loop.run_in_executor(None, run, 'yo')
        res = self.loop.run_until_complete(f2)
        self.assertEqual(res, 'yo')

    def test_reader_callback(self):
        r, w = test_utils.socketpair()
        bytes_read = []

        def reader():
            try:
                data = r.recv(1024)
            except BlockingIOError:
                # Spurious readiness notifications are possible
                # at least on Linux -- see man select.
                return
            if data:
                bytes_read.append(data)
            else:
                self.assertTrue(self.loop.remove_reader(r.fileno()))
                r.close()

        self.loop.add_reader(r.fileno(), reader)
        self.loop.call_later(0.05, w.send, b'abc')
        self.loop.call_later(0.1, w.send, b'def')
        self.loop.call_later(0.15, w.close)
        self.loop.call_later(0.16, self.loop.stop)
        self.loop.run_forever()
        self.assertEqual(b''.join(bytes_read), b'abcdef')

    def test_writer_callback(self):
        r, w = test_utils.socketpair()
        w.setblocking(False)
        self.loop.add_writer(w.fileno(), w.send, b'x'*(256*1024))

        def remove_writer():
            self.assertTrue(self.loop.remove_writer(w.fileno()))

        self.loop.call_later(0.1, remove_writer)
        self.loop.call_later(0.11, self.loop.stop)
        self.loop.run_forever()
        w.close()
        data = r.recv(256*1024)
        r.close()
        self.assertTrue(len(data) >= 200)

    def test_sock_client_ops(self):
        with test_utils.run_test_server(self.loop) as httpd:
            sock = socket.socket()
            sock.setblocking(False)
            self.loop.run_until_complete(
                self.loop.sock_connect(sock, httpd.address))
            self.loop.run_until_complete(
                self.loop.sock_sendall(sock, b'GET / HTTP/1.0\r\n\r\n'))
            data = self.loop.run_until_complete(
                self.loop.sock_recv(sock, 1024))
            # consume data
            self.loop.run_until_complete(
                self.loop.sock_recv(sock, 1024))
            sock.close()

        self.assertTrue(re.match(rb'HTTP/1.0 200 OK', data), data)

    def test_sock_client_fail(self):
        # Make sure that we will get an unused port
        address = None
        try:
            s = socket.socket()
            s.bind(('127.0.0.1', 0))
            address = s.getsockname()
        finally:
            s.close()

        sock = socket.socket()
        sock.setblocking(False)
        with self.assertRaises(ConnectionRefusedError):
            self.loop.run_until_complete(
                self.loop.sock_connect(sock, address))
        sock.close()

    def test_sock_accept(self):
        listener = socket.socket()
        listener.setblocking(False)
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        client = socket.socket()
        client.connect(listener.getsockname())

        f = self.loop.sock_accept(listener)
        conn, addr = self.loop.run_until_complete(f)
        self.assertEqual(conn.gettimeout(), 0)
        self.assertEqual(addr, client.getsockname())
        self.assertEqual(client.getpeername(), listener.getsockname())
        client.close()
        conn.close()
        listener.close()

    @unittest.skipUnless(hasattr(signal, 'SIGKILL'), 'No SIGKILL')
    def test_add_signal_handler(self):
        caught = 0

        def my_handler():
            nonlocal caught
            caught += 1

        # Check error behavior first.
        self.assertRaises(
            TypeError, self.loop.add_signal_handler, 'boom', my_handler)
        self.assertRaises(
            TypeError, self.loop.remove_signal_handler, 'boom')
        self.assertRaises(
            ValueError, self.loop.add_signal_handler, signal.NSIG+1,
            my_handler)
        self.assertRaises(
            ValueError, self.loop.remove_signal_handler, signal.NSIG+1)
        self.assertRaises(
            ValueError, self.loop.add_signal_handler, 0, my_handler)
        self.assertRaises(
            ValueError, self.loop.remove_signal_handler, 0)
        self.assertRaises(
            ValueError, self.loop.add_signal_handler, -1, my_handler)
        self.assertRaises(
            ValueError, self.loop.remove_signal_handler, -1)
        self.assertRaises(
            RuntimeError, self.loop.add_signal_handler, signal.SIGKILL,
            my_handler)
        # Removing SIGKILL doesn't raise, since we don't call signal().
        self.assertFalse(self.loop.remove_signal_handler(signal.SIGKILL))
        # Now set a handler and handle it.
        self.loop.add_signal_handler(signal.SIGINT, my_handler)
        self.loop.run_once()
        os.kill(os.getpid(), signal.SIGINT)
        self.loop.run_once()
        self.assertEqual(caught, 1)
        # Removing it should restore the default handler.
        self.assertTrue(self.loop.remove_signal_handler(signal.SIGINT))
        self.assertEqual(signal.getsignal(signal.SIGINT),
                         signal.default_int_handler)
        # Removing again returns False.
        self.assertFalse(self.loop.remove_signal_handler(signal.SIGINT))

    @unittest.skipUnless(hasattr(signal, 'SIGALRM'), 'No SIGALRM')
    def test_signal_handling_while_selecting(self):
        # Test with a signal actually arriving during a select() call.
        caught = 0

        def my_handler():
            nonlocal caught
            caught += 1

        self.loop.add_signal_handler(signal.SIGALRM, my_handler)

        signal.setitimer(signal.ITIMER_REAL, 0.1, 0)  # Send SIGALRM once.
        self.loop.call_later(0.15, self.loop.stop)
        self.loop.run_forever()
        self.assertEqual(caught, 1)

    @unittest.skipUnless(hasattr(signal, 'SIGALRM'), 'No SIGALRM')
    def test_signal_handling_args(self):
        some_args = (42,)
        caught = 0

        def my_handler(*args):
            nonlocal caught
            caught += 1
            self.assertEqual(args, some_args)

        self.loop.add_signal_handler(signal.SIGALRM, my_handler, *some_args)

        signal.setitimer(signal.ITIMER_REAL, 0.1, 0)  # Send SIGALRM once.
        self.loop.call_later(0.15, self.loop.stop)
        self.loop.run_forever()
        self.assertEqual(caught, 1)

    def test_create_connection(self):
        with test_utils.run_test_server(self.loop) as httpd:
            f = self.loop.create_connection(
                lambda: MyProto(create_future=True), *httpd.address)
            tr, pr = self.loop.run_until_complete(f)
            self.assertTrue(isinstance(tr, transports.Transport))
            self.assertTrue(isinstance(pr, protocols.Protocol))
            self.loop.run_until_complete(pr.done)
            self.assertTrue(pr.nbytes > 0)

    def test_create_connection_sock(self):
        with test_utils.run_test_server(self.loop) as httpd:
            sock = None
            infos = self.loop.run_until_complete(
                self.loop.getaddrinfo(
                    *httpd.address, type=socket.SOCK_STREAM))
            for family, type, proto, cname, address in infos:
                try:
                    sock = socket.socket(family=family, type=type, proto=proto)
                    sock.setblocking(False)
                    self.loop.run_until_complete(
                        self.loop.sock_connect(sock, address))
                except:
                    pass
                else:
                    break
            else:
                assert False, 'Can not create socket.'

            f = self.loop.create_connection(
                lambda: MyProto(create_future=True), sock=sock)
            tr, pr = self.loop.run_until_complete(f)
            self.assertTrue(isinstance(tr, transports.Transport))
            self.assertTrue(isinstance(pr, protocols.Protocol))
            self.loop.run_until_complete(pr.done)
            self.assertTrue(pr.nbytes > 0)

    @unittest.skipIf(ssl is None, 'No ssl module')
    def test_create_ssl_connection(self):
        with test_utils.run_test_server(
                self.loop, use_ssl=True) as httpd:
            f = self.loop.create_connection(
                lambda: MyProto(create_future=True), *httpd.address, ssl=True)
            tr, pr = self.loop.run_until_complete(f)
            self.assertTrue(isinstance(tr, transports.Transport))
            self.assertTrue(isinstance(pr, protocols.Protocol))
            self.assertTrue('ssl' in tr.__class__.__name__.lower())
            self.assertTrue(
                hasattr(tr.get_extra_info('socket'), 'getsockname'))
            self.loop.run_until_complete(pr.done)
            self.assertTrue(pr.nbytes > 0)

    def test_create_connection_local_addr(self):
        with test_utils.run_test_server(self.loop) as httpd:
            port = find_unused_port()
            f = self.loop.create_connection(
                lambda: MyProto(create_future=True),
                *httpd.address, local_addr=(httpd.address[0], port))
            tr, pr = self.loop.run_until_complete(f)
            expected = pr.transport.get_extra_info('socket').getsockname()[1]
            self.assertEqual(port, expected)

    def test_create_connection_local_addr_in_use(self):
        with test_utils.run_test_server(self.loop) as httpd:
            f = self.loop.create_connection(
                lambda: MyProto(create_future=True),
                *httpd.address, local_addr=httpd.address)
            with self.assertRaises(socket.error) as cm:
                self.loop.run_until_complete(f)
            self.assertEqual(cm.exception.errno, errno.EADDRINUSE)
            self.assertIn(str(httpd.address), cm.exception.strerror)

    def test_start_serving(self):
        proto = None

        def factory():
            nonlocal proto
            proto = MyProto()
            return proto

        f = self.loop.start_serving(factory, '0.0.0.0', 0)
        socks = self.loop.run_until_complete(f)
        self.assertEqual(len(socks), 1)
        sock = socks[0]
        host, port = sock.getsockname()
        self.assertEqual(host, '0.0.0.0')
        client = socket.socket()
        client.connect(('127.0.0.1', port))
        client.send(b'xxx')
        self.loop.run_once()
        self.assertIsInstance(proto, MyProto)
        self.assertEqual('INITIAL', proto.state)
        self.loop.run_once()
        self.assertEqual('CONNECTED', proto.state)
        self.loop.run_once(0.001)  # windows iocp
        self.assertEqual(3, proto.nbytes)

        # extra info is available
        self.assertIsNotNone(proto.transport.get_extra_info('socket'))
        conn = proto.transport.get_extra_info('socket')
        self.assertTrue(hasattr(conn, 'getsockname'))
        self.assertEqual(
            '127.0.0.1', proto.transport.get_extra_info('addr')[0])

        # close connection
        proto.transport.close()
        self.loop.run_once(0.001)  # windows iocp

        self.assertEqual('CLOSED', proto.state)

        # the client socket must be closed after to avoid ECONNRESET upon
        # recv()/send() on the serving socket
        client.close()

    @unittest.skipIf(ssl is None, 'No ssl module')
    def test_start_serving_ssl(self):
        proto = None

        class ClientMyProto(MyProto):
            def connection_made(self, transport):
                self.transport = transport
                assert self.state == 'INITIAL', self.state
                self.state = 'CONNECTED'

        def factory():
            nonlocal proto
            proto = MyProto(create_future=True)
            return proto

        here = os.path.dirname(__file__)
        sslcontext = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        sslcontext.load_cert_chain(
            certfile=os.path.join(here, 'sample.crt'),
            keyfile=os.path.join(here, 'sample.key'))

        f = self.loop.start_serving(
            factory, '127.0.0.1', 0, ssl=sslcontext)

        sock = self.loop.run_until_complete(f)[0]
        host, port = sock.getsockname()
        self.assertEqual(host, '127.0.0.1')

        f_c = self.loop.create_connection(ClientMyProto, host, port, ssl=True)
        client, pr = self.loop.run_until_complete(f_c)

        client.write(b'xxx')
        self.loop.run_once()
        self.assertIsInstance(proto, MyProto)
        self.loop.run_once()
        self.assertEqual('CONNECTED', proto.state)
        self.assertEqual(3, proto.nbytes)

        # extra info is available
        self.assertIsNotNone(proto.transport.get_extra_info('socket'))
        conn = proto.transport.get_extra_info('socket')
        self.assertTrue(hasattr(conn, 'getsockname'))
        self.assertEqual(
            '127.0.0.1', proto.transport.get_extra_info('addr')[0])

        # close connection
        proto.transport.close()
        self.loop.run_until_complete(proto.done)
        self.assertEqual('CLOSED', proto.state)

        # the client socket must be closed after to avoid ECONNRESET upon
        # recv()/send() on the serving socket
        client.close()

    def test_start_serving_sock(self):
        proto = futures.Future()

        class TestMyProto(MyProto):
            def connection_made(self, transport):
                super().connection_made(transport)
                proto.set_result(self)

        sock_ob = socket.socket(type=socket.SOCK_STREAM)
        sock_ob.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock_ob.bind(('0.0.0.0', 0))

        f = self.loop.start_serving(TestMyProto, sock=sock_ob)
        sock = self.loop.run_until_complete(f)[0]
        self.assertIs(sock, sock_ob)

        host, port = sock.getsockname()
        self.assertEqual(host, '0.0.0.0')
        client = socket.socket()
        client.connect(('127.0.0.1', port))
        client.send(b'xxx')
        self.loop.run_until_complete(proto)
        sock.close()
        client.close()

    def test_start_serving_addrinuse(self):
        sock_ob = socket.socket(type=socket.SOCK_STREAM)
        sock_ob.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock_ob.bind(('0.0.0.0', 0))

        f = self.loop.start_serving(MyProto, sock=sock_ob)
        sock = self.loop.run_until_complete(f)[0]
        host, port = sock.getsockname()

        f = self.loop.start_serving(MyProto, host=host, port=port)
        with self.assertRaises(socket.error) as cm:
            self.loop.run_until_complete(f)
        self.assertEqual(cm.exception.errno, errno.EADDRINUSE)

    @unittest.skipUnless(socket.has_ipv6, 'IPv6 not supported')
    def test_start_serving_dual_stack(self):
        f_proto = futures.Future()

        class TestMyProto(MyProto):
            def connection_made(self, transport):
                super().connection_made(transport)
                f_proto.set_result(self)

        port = find_unused_port()
        f = self.loop.start_serving(TestMyProto, host=None, port=port)
        socks = self.loop.run_until_complete(f)
        client = socket.socket()
        client.connect(('127.0.0.1', port))
        client.send(b'xxx')
        proto = self.loop.run_until_complete(f_proto)
        proto.transport.close()
        client.close()

        f_proto = futures.Future()
        client = socket.socket(socket.AF_INET6)
        client.connect(('::1', port))
        client.send(b'xxx')
        proto = self.loop.run_until_complete(f_proto)
        proto.transport.close()
        client.close()

        for s in socks:
            s.close()

    def test_stop_serving(self):
        f = self.loop.start_serving(MyProto, '0.0.0.0', 0)
        sock = self.loop.run_until_complete(f)[0]
        host, port = sock.getsockname()

        client = socket.socket()
        client.connect(('127.0.0.1', port))
        client.send(b'xxx')
        client.close()

        self.loop.stop_serving(sock)

        client = socket.socket()
        self.assertRaises(
            ConnectionRefusedError, client.connect, ('127.0.0.1', port))

    def test_create_datagram_endpoint(self):
        class TestMyDatagramProto(MyDatagramProto):
            def __init__(self):
                super().__init__(create_future=True)

            def datagram_received(self, data, addr):
                super().datagram_received(data, addr)
                self.transport.sendto(b'resp:'+data, addr)

        coro = self.loop.create_datagram_endpoint(
            TestMyDatagramProto, local_addr=('127.0.0.1', 0))
        s_transport, server = self.loop.run_until_complete(coro)
        host, port = s_transport.get_extra_info('addr')

        coro = self.loop.create_datagram_endpoint(
            lambda: MyDatagramProto(create_future=True),
            remote_addr=(host, port))
        transport, client = self.loop.run_until_complete(coro)

        self.assertEqual('INITIALIZED', client.state)
        transport.sendto(b'xxx')
        self.loop.run_once(None)
        self.assertEqual(3, server.nbytes)
        self.loop.run_once(None)

        # received
        self.assertEqual(8, client.nbytes)

        # extra info is available
        self.assertIsNotNone(transport.get_extra_info('socket'))
        conn = transport.get_extra_info('socket')
        self.assertTrue(hasattr(conn, 'getsockname'))

        # close connection
        transport.close()
        self.loop.run_until_complete(client.done)
        self.assertEqual('CLOSED', client.state)
        server.transport.close()

    def test_internal_fds(self):
        loop = self.create_event_loop()
        if not isinstance(loop, selector_events.BaseSelectorEventLoop):
            return

        self.assertEqual(1, loop._internal_fds)
        loop.close()
        self.assertEqual(0, loop._internal_fds)
        self.assertIsNone(loop._csock)
        self.assertIsNone(loop._ssock)

    @unittest.skipUnless(sys.platform != 'win32',
                         "Don't support pipes for Windows")
    def test_read_pipe(self):
        proto = None

        def factory():
            nonlocal proto
            proto = MyReadPipeProto(create_future=True)
            return proto

        rpipe, wpipe = os.pipe()
        pipeobj = io.open(rpipe, 'rb', 1024)

        @tasks.task
        def connect():
            t, p = yield from self.loop.connect_read_pipe(factory, pipeobj)
            self.assertIs(p, proto)
            self.assertIs(t, proto.transport)
            self.assertEqual(['INITIAL', 'CONNECTED'], proto.state)
            self.assertEqual(0, proto.nbytes)

        self.loop.run_until_complete(connect())

        os.write(wpipe, b'1')
        self.loop.run_once()
        self.assertEqual(1, proto.nbytes)

        os.write(wpipe, b'2345')
        self.loop.run_once()
        self.assertEqual(['INITIAL', 'CONNECTED'], proto.state)
        self.assertEqual(5, proto.nbytes)

        os.close(wpipe)
        self.loop.run_until_complete(proto.done)
        self.assertEqual(
            ['INITIAL', 'CONNECTED', 'EOF', 'CLOSED'], proto.state)
        # extra info is available
        self.assertIsNotNone(proto.transport.get_extra_info('pipe'))

    @unittest.skipUnless(sys.platform != 'win32',
                         "Don't support pipes for Windows")
    def test_write_pipe(self):
        proto = None
        transport = None

        def factory():
            nonlocal proto
            proto = MyWritePipeProto(create_future=True)
            return proto

        rpipe, wpipe = os.pipe()
        pipeobj = io.open(wpipe, 'wb', 1024)

        @tasks.task
        def connect():
            nonlocal transport
            t, p = yield from self.loop.connect_write_pipe(factory, pipeobj)
            self.assertIs(p, proto)
            self.assertIs(t, proto.transport)
            self.assertEqual('CONNECTED', proto.state)
            transport = t

        self.loop.run_until_complete(connect())

        transport.write(b'1')
        self.loop.run_once()
        data = os.read(rpipe, 1024)
        self.assertEqual(b'1', data)

        transport.write(b'2345')
        self.loop.run_once()
        data = os.read(rpipe, 1024)
        self.assertEqual(b'2345', data)
        self.assertEqual('CONNECTED', proto.state)

        os.close(rpipe)

        # extra info is available
        self.assertIsNotNone(proto.transport.get_extra_info('pipe'))

        # close connection
        proto.transport.close()
        self.loop.run_until_complete(proto.done)
        self.assertEqual('CLOSED', proto.state)


if sys.platform == 'win32':
    from tulip import windows_events

    class SelectEventLoopTests(EventLoopTestsMixin, unittest.TestCase):

        def create_event_loop(self):
            return windows_events.SelectorEventLoop()

    class ProactorEventLoopTests(EventLoopTestsMixin, unittest.TestCase):

        def create_event_loop(self):
            return windows_events.ProactorEventLoop()
        def test_create_ssl_connection(self):
            raise unittest.SkipTest("IocpEventLoop imcompatible with SSL")
        def test_start_serving_ssl(self):
            raise unittest.SkipTest("IocpEventLoop imcompatible with SSL")
        def test_reader_callback(self):
            raise unittest.SkipTest("IocpEventLoop does not have add_reader()")
        def test_reader_callback_cancel(self):
            raise unittest.SkipTest("IocpEventLoop does not have add_reader()")
        def test_writer_callback(self):
            raise unittest.SkipTest("IocpEventLoop does not have add_writer()")
        def test_writer_callback_cancel(self):
            raise unittest.SkipTest("IocpEventLoop does not have add_writer()")
        def test_create_datagram_endpoint(self):
            raise unittest.SkipTest(
                "IocpEventLoop does not have create_datagram_endpoint()")
        def test_stop_serving(self):
            raise unittest.SkipTest(
                "IocpEventLoop does not support stop_serving()")
else:
    from tulip import selectors
    from tulip import unix_events

    if hasattr(selectors, 'KqueueSelector'):
        class KqueueEventLoopTests(EventLoopTestsMixin, unittest.TestCase):

            def create_event_loop(self):
                return unix_events.SelectorEventLoop(
                    selectors.KqueueSelector())

    if hasattr(selectors, 'EpollSelector'):
        class EPollEventLoopTests(EventLoopTestsMixin, unittest.TestCase):

            def create_event_loop(self):
                return unix_events.SelectorEventLoop(selectors.EpollSelector())

    if hasattr(selectors, 'PollSelector'):
        class PollEventLoopTests(EventLoopTestsMixin, unittest.TestCase):

            def create_event_loop(self):
                return unix_events.SelectorEventLoop(selectors.PollSelector())

    # Should always exist.
    class SelectEventLoopTests(EventLoopTestsMixin, unittest.TestCase):

        def create_event_loop(self):
            return unix_events.SelectorEventLoop(selectors.SelectSelector())


class HandleTests(unittest.TestCase):

    def test_handle(self):
        def callback(*args):
            return args

        args = ()
        h = events.Handle(callback, args)
        self.assertIs(h._callback, callback)
        self.assertIs(h._args, args)
        self.assertFalse(h._cancelled)

        r = repr(h)
        self.assertTrue(r.startswith(
            'Handle('
            '<function HandleTests.test_handle.<locals>.callback'))
        self.assertTrue(r.endswith('())'))

        h.cancel()
        self.assertTrue(h._cancelled)

        r = repr(h)
        self.assertTrue(r.startswith(
            'Handle('
            '<function HandleTests.test_handle.<locals>.callback'))
        self.assertTrue(r.endswith('())<cancelled>'))

    def test_make_handle(self):
        def callback(*args):
            return args
        h1 = events.Handle(callback, ())
        self.assertRaises(
            AssertionError, events.make_handle, h1, ())

    @unittest.mock.patch('tulip.events.tulip_log')
    def test_callback_with_exception(self, log):
        def callback():
            raise ValueError()

        h = events.Handle(callback, ())
        h._run()
        self.assertTrue(log.exception.called)


class TimerTests(unittest.TestCase):

    def test_hash(self):
        when = time.monotonic()
        h = events.TimerHandle(when, lambda: False, ())
        self.assertEqual(hash(h), hash(when))

    def test_timer(self):
        def callback(*args):
            return args

        args = ()
        when = time.monotonic()
        h = events.TimerHandle(when, callback, args)
        self.assertIs(h._callback, callback)
        self.assertIs(h._args, args)
        self.assertFalse(h._cancelled)

        r = repr(h)
        self.assertTrue(r.endswith('())'))

        h.cancel()
        self.assertTrue(h._cancelled)

        r = repr(h)
        self.assertTrue(r.endswith('())<cancelled>'))

        self.assertRaises(AssertionError,
                          events.TimerHandle, None, callback, args)

    def test_timer_comparison(self):
        def callback(*args):
            return args

        when = time.monotonic()

        h1 = events.TimerHandle(when, callback, ())
        h2 = events.TimerHandle(when, callback, ())
        self.assertFalse(h1 < h2)
        self.assertFalse(h2 < h1)
        self.assertTrue(h1 <= h2)
        self.assertTrue(h2 <= h1)
        self.assertFalse(h1 > h2)
        self.assertFalse(h2 > h1)
        self.assertTrue(h1 >= h2)
        self.assertTrue(h2 >= h1)
        self.assertTrue(h1 == h2)
        self.assertFalse(h1 != h2)

        h2.cancel()
        self.assertFalse(h1 == h2)

        h1 = events.TimerHandle(when, callback, ())
        h2 = events.TimerHandle(when + 10.0, callback, ())
        self.assertTrue(h1 < h2)
        self.assertFalse(h2 < h1)
        self.assertTrue(h1 <= h2)
        self.assertFalse(h2 <= h1)
        self.assertFalse(h1 > h2)
        self.assertTrue(h2 > h1)
        self.assertFalse(h1 >= h2)
        self.assertTrue(h2 >= h1)
        self.assertFalse(h1 == h2)
        self.assertTrue(h1 != h2)

        h3 = events.Handle(callback, ())
        self.assertIs(NotImplemented, h1.__eq__(h3))
        self.assertIs(NotImplemented, h1.__ne__(h3))


class AbstractEventLoopTests(unittest.TestCase):

    def test_not_implemented(self):
        f = unittest.mock.Mock()
        loop = events.AbstractEventLoop()
        self.assertRaises(
            NotImplementedError, loop.run_forever)
        self.assertRaises(
            NotImplementedError, loop.run_once)
        self.assertRaises(
            NotImplementedError, loop.run_until_complete, None)
        self.assertRaises(
            NotImplementedError, loop.stop)
        self.assertRaises(
            NotImplementedError, loop.is_running)
        self.assertRaises(
            NotImplementedError, loop.call_later, None, None)
        self.assertRaises(
            NotImplementedError, loop.call_at, f, f)
        self.assertRaises(
            NotImplementedError, loop.call_soon, None)
        self.assertRaises(
            NotImplementedError, loop.time)
        self.assertRaises(
            NotImplementedError, loop.call_soon_threadsafe, None)
        self.assertRaises(
            NotImplementedError, loop.run_in_executor, f, f)
        self.assertRaises(
            NotImplementedError, loop.set_default_executor, f)
        self.assertRaises(
            NotImplementedError, loop.getaddrinfo, 'localhost', 8080)
        self.assertRaises(
            NotImplementedError, loop.getnameinfo, ('localhost', 8080))
        self.assertRaises(
            NotImplementedError, loop.create_connection, f)
        self.assertRaises(
            NotImplementedError, loop.start_serving, f)
        self.assertRaises(
            NotImplementedError, loop.stop_serving, f)
        self.assertRaises(
            NotImplementedError, loop.create_datagram_endpoint, f)
        self.assertRaises(
            NotImplementedError, loop.add_reader, 1, f)
        self.assertRaises(
            NotImplementedError, loop.remove_reader, 1)
        self.assertRaises(
            NotImplementedError, loop.add_writer, 1, f)
        self.assertRaises(
            NotImplementedError, loop.remove_writer, 1)
        self.assertRaises(
            NotImplementedError, loop.sock_recv, f, 10)
        self.assertRaises(
            NotImplementedError, loop.sock_sendall, f, 10)
        self.assertRaises(
            NotImplementedError, loop.sock_connect, f, f)
        self.assertRaises(
            NotImplementedError, loop.sock_accept, f)
        self.assertRaises(
            NotImplementedError, loop.add_signal_handler, 1, f)
        self.assertRaises(
            NotImplementedError, loop.remove_signal_handler, 1)
        self.assertRaises(
            NotImplementedError, loop.remove_signal_handler, 1)
        self.assertRaises(
            NotImplementedError, loop.connect_read_pipe, f,
            unittest.mock.sentinel.pipe)
        self.assertRaises(
            NotImplementedError, loop.connect_write_pipe, f,
            unittest.mock.sentinel.pipe)


class ProtocolsAbsTests(unittest.TestCase):

    def test_empty(self):
        f = unittest.mock.Mock()
        p = protocols.Protocol()
        self.assertIsNone(p.connection_made(f))
        self.assertIsNone(p.connection_lost(f))
        self.assertIsNone(p.data_received(f))
        self.assertIsNone(p.eof_received())

        dp = protocols.DatagramProtocol()
        self.assertIsNone(dp.connection_made(f))
        self.assertIsNone(dp.connection_lost(f))
        self.assertIsNone(dp.connection_refused(f))
        self.assertIsNone(dp.datagram_received(f, f))


class PolicyTests(unittest.TestCase):

    def test_event_loop_policy(self):
        policy = events.AbstractEventLoopPolicy()
        self.assertRaises(NotImplementedError, policy.get_event_loop)
        self.assertRaises(NotImplementedError, policy.set_event_loop, object())
        self.assertRaises(NotImplementedError, policy.new_event_loop)

    def test_get_event_loop(self):
        policy = events.DefaultEventLoopPolicy()
        self.assertIsNone(policy._loop)

        loop = policy.get_event_loop()
        self.assertIsInstance(loop, events.AbstractEventLoop)

        self.assertIs(policy._loop, loop)
        self.assertIs(loop, policy.get_event_loop())

    @unittest.mock.patch('tulip.events.threading')
    def test_get_event_loop_thread(self, m_threading):
        m_t = m_threading.current_thread.return_value = unittest.mock.Mock()
        m_t.name = 'Thread 1'

        policy = events.DefaultEventLoopPolicy()
        self.assertIsNone(policy.get_event_loop())

    def test_new_event_loop(self):
        policy = events.DefaultEventLoopPolicy()

        event_loop = policy.new_event_loop()
        self.assertIsInstance(event_loop, events.AbstractEventLoop)

    def test_set_event_loop(self):
        policy = events.DefaultEventLoopPolicy()
        old_event_loop = policy.get_event_loop()

        self.assertRaises(AssertionError, policy.set_event_loop, object())

        event_loop = policy.new_event_loop()
        policy.set_event_loop(event_loop)
        self.assertIs(event_loop, policy.get_event_loop())
        self.assertIsNot(old_event_loop, policy.get_event_loop())

    def test_get_event_loop_policy(self):
        policy = events.get_event_loop_policy()
        self.assertIsInstance(policy, events.AbstractEventLoopPolicy)
        self.assertIs(policy, events.get_event_loop_policy())

    def test_set_event_loop_policy(self):
        self.assertRaises(
            AssertionError, events.set_event_loop_policy, object())

        old_policy = events.get_event_loop_policy()

        policy = events.DefaultEventLoopPolicy()
        events.set_event_loop_policy(policy)
        self.assertIs(policy, events.get_event_loop_policy())
        self.assertIsNot(policy, old_policy)


if __name__ == '__main__':
    unittest.main()
