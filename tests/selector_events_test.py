"""Tests for selector_events.py"""

import errno
import socket
import unittest
import unittest.mock
try:
    import ssl
except ImportError:
    ssl = None

from tulip import futures
from tulip import selectors
from tulip.events import AbstractEventLoop
from tulip.protocols import DatagramProtocol, Protocol
from tulip.selector_events import BaseSelectorEventLoop
from tulip.selector_events import _SelectorSslTransport
from tulip.selector_events import _SelectorSocketTransport
from tulip.selector_events import _SelectorDatagramTransport


class TestBaseSelectorEventLoop(BaseSelectorEventLoop):

    def _make_self_pipe(self):
        self._ssock = unittest.mock.Mock()
        self._csock = unittest.mock.Mock()
        self._internal_fds += 1


class BaseSelectorEventLoopTests(unittest.TestCase):

    def setUp(self):
        self.event_loop = TestBaseSelectorEventLoop(unittest.mock.Mock())

    def test_make_socket_transport(self):
        m = unittest.mock.Mock()
        self.event_loop.add_reader = unittest.mock.Mock()
        self.assertIsInstance(
            self.event_loop._make_socket_transport(m, m),
            _SelectorSocketTransport)

    def test_make_ssl_transport(self):
        m = unittest.mock.Mock()
        self.event_loop.add_reader = unittest.mock.Mock()
        self.event_loop.add_writer = unittest.mock.Mock()
        self.event_loop.remove_reader = unittest.mock.Mock()
        self.event_loop.remove_writer = unittest.mock.Mock()
        self.assertIsInstance(
            self.event_loop._make_ssl_transport(m, m, m, m),
            _SelectorSslTransport)

    def test_close(self):
        ssock = self.event_loop._ssock
        ssock.fileno.return_value = 7
        csock = self.event_loop._csock
        csock.fileno.return_value = 1
        remove_reader = self.event_loop.remove_reader = unittest.mock.Mock()

        self.event_loop._selector.close()
        self.event_loop._selector = selector = unittest.mock.Mock()
        self.event_loop.close()
        self.assertIsNone(self.event_loop._selector)
        self.assertIsNone(self.event_loop._csock)
        self.assertIsNone(self.event_loop._ssock)
        selector.close.assert_called_with()
        ssock.close.assert_called_with()
        csock.close.assert_called_with()
        remove_reader.assert_called_with(7)

        self.event_loop.close()
        self.event_loop.close()

    def test_close_no_selector(self):
        ssock = self.event_loop._ssock
        csock = self.event_loop._csock
        remove_reader = self.event_loop.remove_reader = unittest.mock.Mock()

        self.event_loop._selector.close()
        self.event_loop._selector = None
        self.event_loop.close()
        self.assertIsNone(self.event_loop._selector)
        self.assertFalse(ssock.close.called)
        self.assertFalse(csock.close.called)
        self.assertFalse(remove_reader.called)

    def test_socketpair(self):
        self.assertRaises(NotImplementedError, self.event_loop._socketpair)

    def test_read_from_self_tryagain(self):
        self.event_loop._ssock.recv.side_effect = BlockingIOError
        self.assertIsNone(self.event_loop._read_from_self())

    def test_read_from_self_exception(self):
        self.event_loop._ssock.recv.side_effect = OSError
        self.assertRaises(OSError, self.event_loop._read_from_self)

    def test_write_to_self_tryagain(self):
        self.event_loop._csock.send.side_effect = BlockingIOError
        self.assertIsNone(self.event_loop._write_to_self())

    def test_write_to_self_exception(self):
        self.event_loop._csock.send.side_effect = OSError()
        self.assertRaises(OSError, self.event_loop._write_to_self)

    def test_sock_recv(self):
        sock = unittest.mock.Mock()
        self.event_loop._sock_recv = unittest.mock.Mock()

        f = self.event_loop.sock_recv(sock, 1024)
        self.assertIsInstance(f, futures.Future)
        self.event_loop._sock_recv.assert_called_with(
            f, False, sock, 1024)

    def test__sock_recv_canceled_fut(self):
        sock = unittest.mock.Mock()

        f = futures.Future()
        f.cancel()

        self.event_loop._sock_recv(f, False, sock, 1024)
        self.assertFalse(sock.recv.called)

    def test__sock_recv_unregister(self):
        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10

        f = futures.Future()
        f.cancel()

        self.event_loop.remove_reader = unittest.mock.Mock()
        self.event_loop._sock_recv(f, True, sock, 1024)
        self.assertEqual((10,), self.event_loop.remove_reader.call_args[0])

    def test__sock_recv_tryagain(self):
        f = futures.Future()
        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10
        sock.recv.side_effect = BlockingIOError

        self.event_loop.add_reader = unittest.mock.Mock()
        self.event_loop._sock_recv(f, False, sock, 1024)
        self.assertEqual((10, self.event_loop._sock_recv, f, True, sock, 1024),
                         self.event_loop.add_reader.call_args[0])

    def test__sock_recv_exception(self):
        f = futures.Future()
        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10
        err = sock.recv.side_effect = OSError()

        self.event_loop._sock_recv(f, False, sock, 1024)
        self.assertIs(err, f.exception())

    def test_sock_sendall(self):
        sock = unittest.mock.Mock()
        self.event_loop._sock_sendall = unittest.mock.Mock()

        f = self.event_loop.sock_sendall(sock, b'data')
        self.assertIsInstance(f, futures.Future)
        self.assertEqual(
            (f, False, sock, b'data'),
            self.event_loop._sock_sendall.call_args[0])

    def test_sock_sendall_nodata(self):
        sock = unittest.mock.Mock()
        self.event_loop._sock_sendall = unittest.mock.Mock()

        f = self.event_loop.sock_sendall(sock, b'')
        self.assertIsInstance(f, futures.Future)
        self.assertTrue(f.done())
        self.assertIsNone(f.result())
        self.assertFalse(self.event_loop._sock_sendall.called)

    def test__sock_sendall_canceled_fut(self):
        sock = unittest.mock.Mock()

        f = futures.Future()
        f.cancel()

        self.event_loop._sock_sendall(f, False, sock, b'data')
        self.assertFalse(sock.send.called)

    def test__sock_sendall_unregister(self):
        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10

        f = futures.Future()
        f.cancel()

        self.event_loop.remove_writer = unittest.mock.Mock()
        self.event_loop._sock_sendall(f, True, sock, b'data')
        self.assertEqual((10,), self.event_loop.remove_writer.call_args[0])

    def test__sock_sendall_tryagain(self):
        f = futures.Future()
        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10
        sock.send.side_effect = BlockingIOError

        self.event_loop.add_writer = unittest.mock.Mock()
        self.event_loop._sock_sendall(f, False, sock, b'data')
        self.assertEqual(
            (10, self.event_loop._sock_sendall, f, True, sock, b'data'),
            self.event_loop.add_writer.call_args[0])

    def test__sock_sendall_exception(self):
        f = futures.Future()
        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10
        err = sock.send.side_effect = OSError()

        self.event_loop._sock_sendall(f, False, sock, b'data')
        self.assertIs(f.exception(), err)

    def test__sock_sendall(self):
        sock = unittest.mock.Mock()

        f = futures.Future()
        sock.fileno.return_value = 10
        sock.send.return_value = 4

        self.event_loop._sock_sendall(f, False, sock, b'data')
        self.assertTrue(f.done())
        self.assertIsNone(f.result())

    def test__sock_sendall_partial(self):
        sock = unittest.mock.Mock()

        f = futures.Future()
        sock.fileno.return_value = 10
        sock.send.return_value = 2

        self.event_loop.add_writer = unittest.mock.Mock()
        self.event_loop._sock_sendall(f, False, sock, b'data')
        self.assertFalse(f.done())
        self.assertEqual(
            (10, self.event_loop._sock_sendall, f, True, sock, b'ta'),
            self.event_loop.add_writer.call_args[0])

    def test__sock_sendall_none(self):
        sock = unittest.mock.Mock()

        f = futures.Future()
        sock.fileno.return_value = 10
        sock.send.return_value = 0

        self.event_loop.add_writer = unittest.mock.Mock()
        self.event_loop._sock_sendall(f, False, sock, b'data')
        self.assertFalse(f.done())
        self.assertEqual(
            (10, self.event_loop._sock_sendall, f, True, sock, b'data'),
            self.event_loop.add_writer.call_args[0])

    def test_sock_connect(self):
        sock = unittest.mock.Mock()
        self.event_loop._sock_connect = unittest.mock.Mock()

        f = self.event_loop.sock_connect(sock, ('127.0.0.1', 8080))
        self.assertIsInstance(f, futures.Future)
        self.assertEqual(
            (f, False, sock, ('127.0.0.1', 8080)),
            self.event_loop._sock_connect.call_args[0])

    def test__sock_connect(self):
        f = futures.Future()

        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10

        self.event_loop._sock_connect(f, False, sock, ('127.0.0.1', 8080))
        self.assertTrue(f.done())
        self.assertIsNone(f.result())
        self.assertTrue(sock.connect.called)

    def test__sock_connect_canceled_fut(self):
        sock = unittest.mock.Mock()

        f = futures.Future()
        f.cancel()

        self.event_loop._sock_connect(f, False, sock, ('127.0.0.1', 8080))
        self.assertFalse(sock.connect.called)

    def test__sock_connect_unregister(self):
        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10

        f = futures.Future()
        f.cancel()

        self.event_loop.remove_writer = unittest.mock.Mock()
        self.event_loop._sock_connect(f, True, sock, ('127.0.0.1', 8080))
        self.assertEqual((10,), self.event_loop.remove_writer.call_args[0])

    def test__sock_connect_tryagain(self):
        f = futures.Future()
        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10
        sock.getsockopt.return_value = errno.EAGAIN

        self.event_loop.add_writer = unittest.mock.Mock()
        self.event_loop.remove_writer = unittest.mock.Mock()

        self.event_loop._sock_connect(f, True, sock, ('127.0.0.1', 8080))
        self.assertEqual(
            (10, self.event_loop._sock_connect, f,
             True, sock, ('127.0.0.1', 8080)),
            self.event_loop.add_writer.call_args[0])

    def test__sock_connect_exception(self):
        f = futures.Future()
        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10
        sock.getsockopt.return_value = errno.ENOTCONN

        self.event_loop.remove_writer = unittest.mock.Mock()
        self.event_loop._sock_connect(f, True, sock, ('127.0.0.1', 8080))
        self.assertIsInstance(f.exception(), socket.error)

    def test_sock_accept(self):
        sock = unittest.mock.Mock()
        self.event_loop._sock_accept = unittest.mock.Mock()

        f = self.event_loop.sock_accept(sock)
        self.assertIsInstance(f, futures.Future)
        self.assertEqual(
            (f, False, sock), self.event_loop._sock_accept.call_args[0])

    def test__sock_accept(self):
        f = futures.Future()

        conn = unittest.mock.Mock()

        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10
        sock.accept.return_value = conn, ('127.0.0.1', 1000)

        self.event_loop._sock_accept(f, False, sock)
        self.assertTrue(f.done())
        self.assertEqual((conn, ('127.0.0.1', 1000)), f.result())
        self.assertEqual((False,), conn.setblocking.call_args[0])

    def test__sock_accept_canceled_fut(self):
        sock = unittest.mock.Mock()

        f = futures.Future()
        f.cancel()

        self.event_loop._sock_accept(f, False, sock)
        self.assertFalse(sock.accept.called)

    def test__sock_accept_unregister(self):
        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10

        f = futures.Future()
        f.cancel()

        self.event_loop.remove_reader = unittest.mock.Mock()
        self.event_loop._sock_accept(f, True, sock)
        self.assertEqual((10,), self.event_loop.remove_reader.call_args[0])

    def test__sock_accept_tryagain(self):
        f = futures.Future()
        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10
        sock.accept.side_effect = BlockingIOError

        self.event_loop.add_reader = unittest.mock.Mock()
        self.event_loop._sock_accept(f, False, sock)
        self.assertEqual(
            (10, self.event_loop._sock_accept, f, True, sock),
            self.event_loop.add_reader.call_args[0])

    def test__sock_accept_exception(self):
        f = futures.Future()
        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10
        err = sock.accept.side_effect = OSError()

        self.event_loop._sock_accept(f, False, sock)
        self.assertIs(err, f.exception())

    def test_add_reader(self):
        self.event_loop._selector.get_info.side_effect = KeyError
        cb = lambda: True
        self.event_loop.add_reader(1, cb)

        self.assertTrue(self.event_loop._selector.register.called)
        fd, mask, (r, w) = self.event_loop._selector.register.call_args[0]
        self.assertEqual(1, fd)
        self.assertEqual(selectors.EVENT_READ, mask)
        self.assertEqual(cb, r.callback)
        self.assertEqual(None, w)

    def test_add_reader_existing(self):
        reader = unittest.mock.Mock()
        writer = unittest.mock.Mock()
        self.event_loop._selector.get_info.return_value = (
            selectors.EVENT_WRITE, (reader, writer))
        cb = lambda: True
        self.event_loop.add_reader(1, cb)

        self.assertTrue(reader.cancel.called)
        self.assertFalse(self.event_loop._selector.register.called)
        self.assertTrue(self.event_loop._selector.modify.called)
        fd, mask, (r, w) = self.event_loop._selector.modify.call_args[0]
        self.assertEqual(1, fd)
        self.assertEqual(selectors.EVENT_WRITE | selectors.EVENT_READ, mask)
        self.assertEqual(cb, r.callback)
        self.assertEqual(writer, w)

    def test_add_reader_existing_writer(self):
        writer = unittest.mock.Mock()
        self.event_loop._selector.get_info.return_value = (
            selectors.EVENT_WRITE, (None, writer))
        cb = lambda: True
        self.event_loop.add_reader(1, cb)

        self.assertFalse(self.event_loop._selector.register.called)
        self.assertTrue(self.event_loop._selector.modify.called)
        fd, mask, (r, w) = self.event_loop._selector.modify.call_args[0]
        self.assertEqual(1, fd)
        self.assertEqual(selectors.EVENT_WRITE | selectors.EVENT_READ, mask)
        self.assertEqual(cb, r.callback)
        self.assertEqual(writer, w)

    def test_remove_reader(self):
        self.event_loop._selector.get_info.return_value = (
            selectors.EVENT_READ, (None, None))
        self.assertFalse(self.event_loop.remove_reader(1))

        self.assertTrue(self.event_loop._selector.unregister.called)

    def test_remove_reader_read_write(self):
        reader = unittest.mock.Mock()
        writer = unittest.mock.Mock()
        self.event_loop._selector.get_info.return_value = (
            selectors.EVENT_READ | selectors.EVENT_WRITE, (reader, writer))
        self.assertTrue(
            self.event_loop.remove_reader(1))

        self.assertFalse(self.event_loop._selector.unregister.called)
        self.assertEqual(
            (1, selectors.EVENT_WRITE, (None, writer)),
            self.event_loop._selector.modify.call_args[0])

    def test_remove_reader_unknown(self):
        self.event_loop._selector.get_info.side_effect = KeyError
        self.assertFalse(
            self.event_loop.remove_reader(1))

    def test_add_writer(self):
        self.event_loop._selector.get_info.side_effect = KeyError
        cb = lambda: True
        self.event_loop.add_writer(1, cb)

        self.assertTrue(self.event_loop._selector.register.called)
        fd, mask, (r, w) = self.event_loop._selector.register.call_args[0]
        self.assertEqual(1, fd)
        self.assertEqual(selectors.EVENT_WRITE, mask)
        self.assertEqual(None, r)
        self.assertEqual(cb, w.callback)

    def test_add_writer_existing(self):
        reader = unittest.mock.Mock()
        writer = unittest.mock.Mock()
        self.event_loop._selector.get_info.return_value = (
            selectors.EVENT_READ, (reader, writer))
        cb = lambda: True
        self.event_loop.add_writer(1, cb)

        self.assertTrue(writer.cancel.called)
        self.assertFalse(self.event_loop._selector.register.called)
        self.assertTrue(self.event_loop._selector.modify.called)
        fd, mask, (r, w) = self.event_loop._selector.modify.call_args[0]
        self.assertEqual(1, fd)
        self.assertEqual(selectors.EVENT_WRITE | selectors.EVENT_READ, mask)
        self.assertEqual(reader, r)
        self.assertEqual(cb, w.callback)

    def test_remove_writer(self):
        self.event_loop._selector.get_info.return_value = (
            selectors.EVENT_WRITE, (None, None))
        self.assertFalse(self.event_loop.remove_writer(1))

        self.assertTrue(self.event_loop._selector.unregister.called)

    def test_remove_writer_read_write(self):
        reader = unittest.mock.Mock()
        writer = unittest.mock.Mock()
        self.event_loop._selector.get_info.return_value = (
            selectors.EVENT_READ | selectors.EVENT_WRITE, (reader, writer))
        self.assertTrue(
            self.event_loop.remove_writer(1))

        self.assertFalse(self.event_loop._selector.unregister.called)
        self.assertEqual(
            (1, selectors.EVENT_READ, (reader, None)),
            self.event_loop._selector.modify.call_args[0])

    def test_remove_writer_unknown(self):
        self.event_loop._selector.get_info.side_effect = KeyError
        self.assertFalse(
            self.event_loop.remove_writer(1))

    def test_process_events_read(self):
        reader = unittest.mock.Mock()
        reader.cancelled = False

        self.event_loop._add_callback = unittest.mock.Mock()
        self.event_loop._process_events(
            ((1, selectors.EVENT_READ, (reader, None)),))
        self.assertTrue(self.event_loop._add_callback.called)
        self.event_loop._add_callback.assert_called_with(reader)

    def test_process_events_read_cancelled(self):
        reader = unittest.mock.Mock()
        reader.cancelled = True

        self.event_loop.remove_reader = unittest.mock.Mock()
        self.event_loop._process_events(
            ((1, selectors.EVENT_READ, (reader, None)),))
        self.event_loop.remove_reader.assert_called_with(1)

    def test_process_events_write(self):
        writer = unittest.mock.Mock()
        writer.cancelled = False

        self.event_loop._add_callback = unittest.mock.Mock()
        self.event_loop._process_events(
            ((1, selectors.EVENT_WRITE, (None, writer)),))
        self.event_loop._add_callback.assert_called_with(writer)

    def test_process_events_write_cancelled(self):
        writer = unittest.mock.Mock()
        writer.cancelled = True
        self.event_loop.remove_writer = unittest.mock.Mock()

        self.event_loop._process_events(
            ((1, selectors.EVENT_WRITE, (None, writer)),))
        self.event_loop.remove_writer.assert_called_with(1)


class SelectorSocketTransportTests(unittest.TestCase):

    def setUp(self):
        self.event_loop = unittest.mock.Mock(spec_set=AbstractEventLoop)
        self.sock = unittest.mock.Mock(socket.socket)
        self.sock.fileno.return_value = 7
        self.protocol = unittest.mock.Mock(Protocol)

    def test_ctor(self):
        tr = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        self.event_loop.add_reader.assert_called_with(7, tr._read_ready)
        self.event_loop.call_soon.assert_called_with(
            self.protocol.connection_made, tr)

    def test_ctor_with_waiter(self):
        fut = futures.Future()

        _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol, fut)
        self.assertEqual(2, self.event_loop.call_soon.call_count)
        self.assertEqual(fut.set_result,
                         self.event_loop.call_soon.call_args[0][0])

    def test_read_ready(self):
        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)

        self.sock.recv.return_value = b'data'
        transport._read_ready()

        self.protocol.data_received.assert_called_with(b'data')

    def test_read_ready_eof(self):
        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)

        self.sock.recv.return_value = b''
        transport._read_ready()

        self.assertTrue(self.event_loop.remove_reader.called)
        self.protocol.eof_received.assert_called_with()

    @unittest.mock.patch('logging.exception')
    def test_read_ready_tryagain(self, m_exc):
        self.sock.recv.side_effect = BlockingIOError

        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport._fatal_error = unittest.mock.Mock()
        transport._read_ready()

        self.assertFalse(transport._fatal_error.called)

    @unittest.mock.patch('logging.exception')
    def test_read_ready_err(self, m_exc):
        err = self.sock.recv.side_effect = OSError()

        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport._fatal_error = unittest.mock.Mock()
        transport._read_ready()

        transport._fatal_error.assert_called_with(err)

    def test_abort(self):
        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport._close = unittest.mock.Mock()

        transport.abort()
        transport._close.assert_called_with(None)

    def test_write(self):
        data = b'data'
        self.sock.send.return_value = len(data)

        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport.write(data)
        self.sock.send.assert_called_with(data)

    def test_write_no_data(self):
        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport._buffer.append(b'data')
        transport.write(b'')
        self.assertFalse(self.sock.send.called)
        self.assertEqual([b'data'], transport._buffer)

    def test_write_buffer(self):
        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport._buffer.append(b'data1')
        transport.write(b'data2')
        self.assertFalse(self.sock.send.called)
        self.assertEqual([b'data1', b'data2'], transport._buffer)

    def test_write_partial(self):
        data = b'data'
        self.sock.send.return_value = 2

        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport.write(data)

        self.assertTrue(self.event_loop.add_writer.called)
        self.assertEqual(
            transport._write_ready, self.event_loop.add_writer.call_args[0][1])

        self.assertEqual([b'ta'], transport._buffer)

    def test_write_partial_none(self):
        data = b'data'
        self.sock.send.return_value = 0
        self.sock.fileno.return_value = 7

        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport.write(data)

        self.event_loop.add_writer.assert_called_with(
            7, transport._write_ready)
        self.assertEqual([b'data'], transport._buffer)

    def test_write_tryagain(self):
        self.sock.send.side_effect = BlockingIOError

        data = b'data'
        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport.write(data)

        self.assertTrue(self.event_loop.add_writer.called)
        self.assertEqual(
            transport._write_ready, self.event_loop.add_writer.call_args[0][1])

        self.assertEqual([b'data'], transport._buffer)

    @unittest.mock.patch('tulip.selector_events.tulip_log')
    def test_write_exception(self, m_log):
        err = self.sock.send.side_effect = OSError()

        data = b'data'
        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport._fatal_error = unittest.mock.Mock()
        transport.write(data)
        transport._fatal_error.assert_called_with(err)
        self.assertEqual(transport._conn_lost, 1)

        self.sock.reset_mock()
        transport.write(data)
        self.assertFalse(self.sock.send.called)
        self.assertEqual(transport._conn_lost, 2)
        transport.write(data)
        transport.write(data)
        transport.write(data)
        transport.write(data)
        m_log.warning.assert_called_with('socket.send() raised exception.')

    def test_write_str(self):
        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        self.assertRaises(AssertionError, transport.write, 'str')

    def test_write_closing(self):
        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport.close()
        self.assertRaises(AssertionError, transport.write, b'data')

    def test_write_ready(self):
        data = b'data'
        self.sock.send.return_value = len(data)

        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport._buffer.append(data)
        transport._write_ready()
        self.assertTrue(self.sock.send.called)
        self.assertEqual(self.sock.send.call_args[0], (data,))
        self.assertTrue(self.event_loop.remove_writer.called)

    def test_write_ready_closing(self):
        data = b'data'
        self.sock.send.return_value = len(data)

        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport._closing = True
        transport._buffer.append(data)
        transport._write_ready()
        self.sock.send.assert_called_with(data)
        self.event_loop.remove_writer.assert_called_with(7)
        self.sock.close.assert_called_with()
        self.protocol.connection_lost.assert_called_with(None)

    def test_write_ready_no_data(self):
        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        self.assertRaises(AssertionError, transport._write_ready)

    def test_write_ready_partial(self):
        data = b'data'
        self.sock.send.return_value = 2

        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport._buffer.append(data)
        transport._write_ready()
        self.assertFalse(self.event_loop.remove_writer.called)
        self.assertEqual([b'ta'], transport._buffer)

    def test_write_ready_partial_none(self):
        data = b'data'
        self.sock.send.return_value = 0

        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport._buffer.append(data)
        transport._write_ready()
        self.assertFalse(self.event_loop.remove_writer.called)
        self.assertEqual([b'data'], transport._buffer)

    def test_write_ready_tryagain(self):
        self.sock.send.side_effect = BlockingIOError

        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport._buffer = [b'data1', b'data2']
        transport._write_ready()

        self.assertFalse(self.event_loop.remove_writer.called)
        self.assertEqual([b'data1data2'], transport._buffer)

    def test_write_ready_exception(self):
        err = self.sock.send.side_effect = OSError()

        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport._fatal_error = unittest.mock.Mock()
        transport._buffer.append(b'data')
        transport._write_ready()
        transport._fatal_error.assert_called_with(err)
        self.assertEqual(transport._conn_lost, 1)

    def test_close(self):
        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport.close()

        self.assertTrue(transport._closing)
        self.event_loop.remove_reader.assert_called_with(7)
        self.protocol.connection_lost(None)

    def test_close_write_buffer(self):
        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        self.event_loop.reset_mock()
        transport._buffer.append(b'data')
        transport.close()

        self.assertTrue(self.event_loop.remove_reader.called)
        self.assertFalse(self.event_loop.call_soon.called)

    @unittest.mock.patch('tulip.log.tulip_log.exception')
    def test_fatal_error(self, m_exc):
        exc = OSError()
        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport._buffer.append(b'data')
        transport._fatal_error(exc)

        self.assertEqual([], transport._buffer)
        self.event_loop.remove_reader.assert_called_with(7)
        self.event_loop.remove_writer.assert_called_with(7)
        self.event_loop.call_soon.assert_called_with(
            transport._call_connection_lost, exc)
        m_exc.assert_called_with('Fatal error for %s', transport)

    def test_connection_lost(self):
        exc = object()
        transport = _SelectorSocketTransport(
            self.event_loop, self.sock, self.protocol)
        transport._call_connection_lost(exc)

        self.protocol.connection_lost.assert_called_with(exc)
        self.sock.close.assert_called_with()


@unittest.skipIf(ssl is None, 'No ssl module')
class SelectorSslTransportTests(unittest.TestCase):

    def setUp(self):
        self.loop = unittest.mock.Mock(spec_set=AbstractEventLoop)
        self.sock = unittest.mock.Mock(socket.socket)
        self.sock.fileno.return_value = 7
        self.protocol = unittest.mock.Mock(spec_set=Protocol)
        self.sslsock = unittest.mock.Mock()
        self.sslsock.fileno.return_value = 1
        self.sslcontext = unittest.mock.Mock()
        self.sslcontext.wrap_socket.return_value = self.sslsock

    def _make_one(self, create_waiter=None):
        transport = _SelectorSslTransport(
            self.loop, self.sock, self.protocol, self.sslcontext)
        self.loop.reset_mock()
        self.sock.reset_mock()
        self.protocol.reset_mock()
        self.sslsock.reset_mock()
        self.sslcontext.reset_mock()
        return transport

    def test_on_handshake(self):
        tr = self._make_one()
        tr._waiter = futures.Future()
        tr._on_handshake()
        self.assertTrue(self.sslsock.do_handshake.called)
        self.assertTrue(self.loop.remove_reader.called)
        self.assertTrue(self.loop.remove_writer.called)
        self.assertEqual((1, tr._on_ready,),
                         self.loop.add_reader.call_args[0])
        self.assertEqual((1, tr._on_ready,),
                         self.loop.add_writer.call_args[0])
        self.assertEqual((tr._waiter.set_result, None),
                         self.loop.call_soon.call_args[0])
        tr._waiter.cancel()

    def test_on_handshake_reader_retry(self):
        self.sslsock.do_handshake.side_effect = ssl.SSLWantReadError
        transport = self._make_one()
        transport._on_handshake()
        self.assertEqual((1, transport._on_handshake,),
                         self.loop.add_reader.call_args[0])

    def test_on_handshake_writer_retry(self):
        self.sslsock.do_handshake.side_effect = ssl.SSLWantWriteError
        transport = self._make_one()
        transport._on_handshake()
        self.assertEqual((1, transport._on_handshake,),
                         self.loop.add_writer.call_args[0])

    def test_on_handshake_exc(self):
        exc = ValueError()
        self.sslsock.do_handshake.side_effect = exc
        transport = self._make_one()
        transport._waiter = futures.Future()
        transport._on_handshake()
        self.assertTrue(self.sslsock.close.called)
        self.assertTrue(transport._waiter.done())
        self.assertIs(exc, transport._waiter.exception())

    def test_on_handshake_base_exc(self):
        transport = self._make_one()
        transport._waiter = futures.Future()
        exc = BaseException()
        self.sslsock.do_handshake.side_effect = exc
        self.assertRaises(BaseException, transport._on_handshake)
        self.assertTrue(self.sslsock.close.called)
        self.assertTrue(transport._waiter.done())
        self.assertIs(exc, transport._waiter.exception())

    def test_write_no_data(self):
        transport = self._make_one()
        transport._buffer.append(b'data')
        transport.write(b'')
        self.assertEqual([b'data'], transport._buffer)

    def test_write_str(self):
        transport = self._make_one()
        self.assertRaises(AssertionError, transport.write, 'str')

    def test_write_closing(self):
        transport = self._make_one()
        transport.close()
        self.assertRaises(AssertionError, transport.write, b'data')

    @unittest.mock.patch('tulip.selector_events.tulip_log')
    def test_write_exception(self, m_log):
        transport = self._make_one()
        transport._conn_lost = 1
        transport.write(b'data')
        self.assertEqual(transport._buffer, [])
        transport.write(b'data')
        transport.write(b'data')
        transport.write(b'data')
        transport.write(b'data')
        m_log.warning.assert_called_with('socket.send() raised exception.')

    def test_abort(self):
        transport = self._make_one()
        transport._close = unittest.mock.Mock()
        transport.abort()
        transport._close.assert_called_with(None)

    @unittest.mock.patch('tulip.log.tulip_log.exception')
    def test_fatal_error(self, m_exc):
        exc = OSError()
        transport = self._make_one()
        transport._buffer.append(b'data')
        transport._fatal_error(exc)

        self.assertEqual([], transport._buffer)
        self.assertTrue(self.loop.remove_writer.called)
        self.assertTrue(self.loop.remove_reader.called)
        self.loop.call_soon.assert_called_with(
            self.protocol.connection_lost, exc)
        m_exc.assert_called_with('Fatal error for %s', transport)

    def test_close(self):
        transport = self._make_one()
        transport.close()
        self.assertTrue(transport._closing)
        self.assertTrue(self.loop.remove_reader.called)
        self.loop.call_soon.assert_called_with(
            self.protocol.connection_lost, None)

    def test_close_write_buffer1(self):
        transport = self._make_one()
        transport._buffer.append(b'data')
        transport.close()

        self.assertTrue(self.loop.remove_reader.called)
        self.assertFalse(self.loop.call_soon.called)

    def test_on_ready_closed(self):
        self.sslsock.fileno.return_value = -1
        transport = self._make_one()
        transport._on_ready()
        self.assertFalse(self.sslsock.recv.called)

    def test_on_ready_recv(self):
        self.sslsock.recv.return_value = b'data'
        transport = self._make_one()
        transport._on_ready()
        self.assertTrue(self.sslsock.recv.called)
        self.assertEqual((b'data',), self.protocol.data_received.call_args[0])

    def test_on_ready_recv_eof(self):
        self.sslsock.recv.return_value = b''
        transport = self._make_one()
        transport._on_ready()
        self.assertTrue(self.loop.remove_reader.called)
        self.assertTrue(self.loop.remove_writer.called)
        self.assertTrue(self.sslsock.close.called)
        self.protocol.connection_lost.assert_called_with(None)

    def test_on_ready_recv_retry(self):
        self.sslsock.recv.side_effect = ssl.SSLWantReadError
        transport = self._make_one()
        transport._on_ready()
        self.assertTrue(self.sslsock.recv.called)
        self.assertFalse(self.protocol.data_received.called)

        self.sslsock.recv.side_effect = ssl.SSLWantWriteError
        transport._on_ready()
        self.assertFalse(self.protocol.data_received.called)

        self.sslsock.recv.side_effect = BlockingIOError
        transport._on_ready()
        self.assertFalse(self.protocol.data_received.called)

    def test_on_ready_recv_exc(self):
        err = self.sslsock.recv.side_effect = OSError()
        transport = self._make_one()
        transport._fatal_error = unittest.mock.Mock()
        transport._on_ready()
        transport._fatal_error.assert_called_with(err)

    def test_on_ready_send(self):
        self.sslsock.recv.side_effect = ssl.SSLWantReadError
        self.sslsock.send.return_value = 4
        transport = self._make_one()
        transport._buffer = [b'data']
        transport._on_ready()
        self.assertEqual([], transport._buffer)
        self.assertTrue(self.sslsock.send.called)

    def test_on_ready_send_none(self):
        self.sslsock.recv.side_effect = ssl.SSLWantReadError
        self.sslsock.send.return_value = 0
        transport = self._make_one()
        transport._buffer = [b'data1', b'data2']
        transport._on_ready()
        self.assertTrue(self.sslsock.send.called)
        self.assertEqual([b'data1data2'], transport._buffer)

    def test_on_ready_send_partial(self):
        self.sslsock.recv.side_effect = ssl.SSLWantReadError
        self.sslsock.send.return_value = 2
        transport = self._make_one()
        transport._buffer = [b'data1', b'data2']
        transport._on_ready()
        self.assertTrue(self.sslsock.send.called)
        self.assertEqual([b'ta1data2'], transport._buffer)

    def test_on_ready_send_closing_partial(self):
        self.sslsock.recv.side_effect = ssl.SSLWantReadError
        self.sslsock.send.return_value = 2
        transport = self._make_one()
        transport._buffer = [b'data1', b'data2']
        transport._on_ready()
        self.assertTrue(self.sslsock.send.called)
        self.assertFalse(self.sslsock.close.called)

    def test_on_ready_send_closing(self):
        self.sslsock.recv.side_effect = ssl.SSLWantReadError
        self.sslsock.send.return_value = 4
        transport = self._make_one()
        transport.close()
        transport._buffer = [b'data']
        transport._on_ready()
        self.assertTrue(self.sslsock.close.called)
        self.assertTrue(self.loop.remove_writer.called)
        self.loop.call_soon.assert_called_with(
            self.protocol.connection_lost, None)

    def test_on_ready_send_retry(self):
        self.sslsock.recv.side_effect = ssl.SSLWantReadError

        transport = self._make_one()
        transport._buffer = [b'data']

        self.sslsock.send.side_effect = ssl.SSLWantReadError
        transport._on_ready()
        self.assertTrue(self.sslsock.send.called)
        self.assertEqual([b'data'], transport._buffer)

        self.sslsock.send.side_effect = ssl.SSLWantWriteError
        transport._on_ready()
        self.assertEqual([b'data'], transport._buffer)

        self.sslsock.send.side_effect = BlockingIOError()
        transport._on_ready()
        self.assertEqual([b'data'], transport._buffer)

    def test_on_ready_send_exc(self):
        self.sslsock.recv.side_effect = ssl.SSLWantReadError
        err = self.sslsock.send.side_effect = OSError()

        transport = self._make_one()
        transport._buffer = [b'data']
        transport._fatal_error = unittest.mock.Mock()
        transport._on_ready()
        transport._fatal_error.assert_called_with(err)
        self.assertEqual([], transport._buffer)
        self.assertEqual(transport._conn_lost, 1)


class SelectorDatagramTransportTests(unittest.TestCase):

    def setUp(self):
        self.event_loop = unittest.mock.Mock(spec_set=AbstractEventLoop)
        self.sock = unittest.mock.Mock(spec_set=socket.socket)
        self.sock.fileno.return_value = 7
        self.protocol = unittest.mock.Mock(spec_set=DatagramProtocol)

    def test_read_ready(self):
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)

        self.sock.recvfrom.return_value = (b'data', ('0.0.0.0', 1234))
        transport._read_ready()

        self.protocol.datagram_received.assert_called_with(
            b'data', ('0.0.0.0', 1234))

    def test_read_ready_tryagain(self):
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)

        self.sock.recvfrom.side_effect = BlockingIOError
        transport._fatal_error = unittest.mock.Mock()
        transport._read_ready()

        self.assertFalse(transport._fatal_error.called)

    def test_read_ready_err(self):
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)

        err = self.sock.recvfrom.side_effect = OSError()
        transport._fatal_error = unittest.mock.Mock()
        transport._read_ready()

        transport._fatal_error.assert_called_with(err)

    def test_abort(self):
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport._close = unittest.mock.Mock()

        transport.abort()
        transport._close.assert_called_with(None)

    def test_sendto(self):
        data = b'data'
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport.sendto(data, ('0.0.0.0', 1234))
        self.assertTrue(self.sock.sendto.called)
        self.assertEqual(
            self.sock.sendto.call_args[0], (data, ('0.0.0.0', 1234)))

    def test_sendto_no_data(self):
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport._buffer.append((b'data', ('0.0.0.0', 12345)))
        transport.sendto(b'', ())
        self.assertFalse(self.sock.sendto.called)
        self.assertEqual(
            [(b'data', ('0.0.0.0', 12345))], list(transport._buffer))

    def test_sendto_buffer(self):
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport._buffer.append((b'data1', ('0.0.0.0', 12345)))
        transport.sendto(b'data2', ('0.0.0.0', 12345))
        self.assertFalse(self.sock.sendto.called)
        self.assertEqual(
            [(b'data1', ('0.0.0.0', 12345)),
             (b'data2', ('0.0.0.0', 12345))],
            list(transport._buffer))

    def test_sendto_tryagain(self):
        data = b'data'

        self.sock.sendto.side_effect = BlockingIOError

        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport.sendto(data, ('0.0.0.0', 12345))

        self.assertTrue(self.event_loop.add_writer.called)
        self.assertEqual(
            transport._sendto_ready,
            self.event_loop.add_writer.call_args[0][1])

        self.assertEqual(
            [(b'data', ('0.0.0.0', 12345))], list(transport._buffer))

    @unittest.mock.patch('tulip.selector_events.tulip_log')
    def test_sendto_exception(self, m_log):
        data = b'data'
        err = self.sock.sendto.side_effect = OSError()

        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport._fatal_error = unittest.mock.Mock()
        transport.sendto(data, ())

        self.assertEqual(transport._conn_lost, 1)
        self.assertTrue(transport._fatal_error.called)
        transport._fatal_error.assert_called_with(err)

        transport._address = ('123',)
        transport.sendto(data)
        transport.sendto(data)
        transport.sendto(data)
        transport.sendto(data)
        transport.sendto(data)
        m_log.warning.assert_called_with('socket.send() raised exception.')

    def test_sendto_connection_refused(self):
        data = b'data'

        self.sock.sendto.side_effect = ConnectionRefusedError

        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport._fatal_error = unittest.mock.Mock()
        transport.sendto(data, ())

        self.assertEqual(transport._conn_lost, 0)
        self.assertFalse(transport._fatal_error.called)

    def test_sendto_connection_refused_connected(self):
        data = b'data'

        self.sock.send.side_effect = ConnectionRefusedError

        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol, ('0.0.0.0', 1))
        transport._fatal_error = unittest.mock.Mock()
        transport.sendto(data)

        self.assertEqual(transport._conn_lost, 1)
        self.assertTrue(transport._fatal_error.called)

    def test_sendto_str(self):
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        self.assertRaises(AssertionError, transport.sendto, 'str', ())

    def test_sendto_connected_addr(self):
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol, ('0.0.0.0', 1))
        self.assertRaises(
            AssertionError, transport.sendto, b'str', ('0.0.0.0', 2))

    def test_sendto_closing(self):
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport.close()
        self.assertRaises(AssertionError, transport.sendto, b'data', ())

    def test_sendto_ready(self):
        data = b'data'
        self.sock.sendto.return_value = len(data)

        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport._buffer.append((data, ('0.0.0.0', 12345)))
        transport._sendto_ready()
        self.assertTrue(self.sock.sendto.called)
        self.assertEqual(
            self.sock.sendto.call_args[0], (data, ('0.0.0.0', 12345)))
        self.assertTrue(self.event_loop.remove_writer.called)

    def test_sendto_ready_closing(self):
        data = b'data'
        self.sock.send.return_value = len(data)

        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport._closing = True
        transport._buffer.append((data, ()))
        transport._sendto_ready()
        self.sock.sendto.assert_called_with(data, ())
        self.event_loop.remove_writer.assert_called_with(7)
        self.sock.close.assert_called_with()
        self.protocol.connection_lost.assert_called_with(None)

    def test_sendto_ready_no_data(self):
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport._sendto_ready()
        self.assertFalse(self.sock.sendto.called)
        self.assertTrue(self.event_loop.remove_writer.called)

    def test_sendto_ready_tryagain(self):
        self.sock.sendto.side_effect = BlockingIOError

        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport._buffer.extend([(b'data1', ()), (b'data2', ())])
        transport._sendto_ready()

        self.assertFalse(self.event_loop.remove_writer.called)
        self.assertEqual(
            [(b'data1', ()), (b'data2', ())],
            list(transport._buffer))

    def test_sendto_ready_exception(self):
        err = self.sock.sendto.side_effect = OSError()

        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport._fatal_error = unittest.mock.Mock()
        transport._buffer.append((b'data', ()))
        transport._sendto_ready()

        transport._fatal_error.assert_called_with(err)

    def test_sendto_ready_connection_refused(self):
        self.sock.sendto.side_effect = ConnectionRefusedError

        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport._fatal_error = unittest.mock.Mock()
        transport._buffer.append((b'data', ()))
        transport._sendto_ready()

        self.assertFalse(transport._fatal_error.called)

    def test_sendto_ready_connection_refused_connection(self):
        self.sock.send.side_effect = ConnectionRefusedError

        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol, ('0.0.0.0', 1))
        transport._fatal_error = unittest.mock.Mock()
        transport._buffer.append((b'data', ()))
        transport._sendto_ready()

        self.assertTrue(transport._fatal_error.called)

    def test_close(self):
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport.close()

        self.assertTrue(transport._closing)
        self.event_loop.remove_reader.assert_called_with(7)
        self.event_loop.call_soon.assert_called_with(
            transport._call_connection_lost, None)

    def test_close_write_buffer(self):
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport._buffer.append((b'data', ()))
        transport.close()

        self.event_loop.remove_reader.assert_called_with(7)
        self.assertFalse(self.protocol.connection_lost.called)

    @unittest.mock.patch('tulip.log.tulip_log.exception')
    def test_fatal_error(self, m_exc):
        exc = OSError()
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        self.event_loop.reset_mock()
        transport._buffer.append((b'data', ()))
        transport._fatal_error(exc)

        self.assertEqual([], list(transport._buffer))
        self.event_loop.remove_writer.assert_called_with(7)
        self.event_loop.remove_reader.assert_called_with(7)
        self.event_loop.call_soon.assert_called_with(
            transport._call_connection_lost, exc)
        m_exc.assert_called_with('Fatal error for %s', transport)

    @unittest.mock.patch('tulip.log.tulip_log.exception')
    def test_fatal_error_connected(self, m_exc):
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol, ('0.0.0.0', 1))
        err = ConnectionRefusedError()
        transport._fatal_error(err)
        self.protocol.connection_refused.assert_called_with(err)
        m_exc.assert_called_with('Fatal error for %s', transport)

    def test_transport_closing(self):
        exc = object()
        transport = _SelectorDatagramTransport(
            self.event_loop, self.sock, self.protocol)
        transport._call_connection_lost(exc)

        self.protocol.connection_lost.assert_called_with(exc)
        self.sock.close.assert_called_with()
