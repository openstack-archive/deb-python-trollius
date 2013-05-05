"""Tests for base_events.py"""

import concurrent.futures
import logging
import socket
import time
import unittest
import unittest.mock

from tulip import base_events
from tulip import events
from tulip import futures
from tulip import protocols
from tulip import tasks


class BaseEventLoopTests(unittest.TestCase):

    def setUp(self):
        self.loop = base_events.BaseEventLoop()
        self.loop._selector = unittest.mock.Mock()
        self.loop._selector.registered_count.return_value = 1

    def test_not_implemented(self):
        m = unittest.mock.Mock()
        self.assertRaises(
            NotImplementedError,
            self.loop._make_socket_transport, m, m)
        self.assertRaises(
            NotImplementedError,
            self.loop._make_ssl_transport, m, m, m, m)
        self.assertRaises(
            NotImplementedError,
            self.loop._make_datagram_transport, m, m)
        self.assertRaises(
            NotImplementedError, self.loop._process_events, [])
        self.assertRaises(
            NotImplementedError, self.loop._write_to_self)
        self.assertRaises(
            NotImplementedError, self.loop._read_from_self)
        self.assertRaises(
            NotImplementedError,
            self.loop._make_read_pipe_transport, m, m)
        self.assertRaises(
            NotImplementedError,
            self.loop._make_write_pipe_transport, m, m)

    def test__add_callback_handle(self):
        h = events.Handle(lambda: False, ())

        self.loop._add_callback(h)
        self.assertFalse(self.loop._scheduled)
        self.assertIn(h, self.loop._ready)

    def test__add_callback_cancelled_handle(self):
        h = events.Handle(lambda: False, ())
        h.cancel()

        self.loop._add_callback(h)
        self.assertFalse(self.loop._scheduled)
        self.assertFalse(self.loop._ready)

    def test_wrap_future(self):
        f = futures.Future(loop=self.loop)
        self.assertIs(self.loop.wrap_future(f), f)
        f.cancel()

    def test_wrap_future_concurrent(self):
        f = concurrent.futures.Future()
        fut = self.loop.wrap_future(f)
        self.assertIsInstance(fut, futures.Future)
        fut.cancel()

    def test_set_default_executor(self):
        executor = unittest.mock.Mock()
        self.loop.set_default_executor(executor)
        self.assertIs(executor, self.loop._default_executor)

    def test_getnameinfo(self):
        sockaddr = unittest.mock.Mock()
        self.loop.run_in_executor = unittest.mock.Mock()
        self.loop.getnameinfo(sockaddr)
        self.assertEqual(
            (None, socket.getnameinfo, sockaddr, 0),
            self.loop.run_in_executor.call_args[0])

    def test_call_soon(self):
        def cb():
            pass

        h = self.loop.call_soon(cb)
        self.assertEqual(h._callback, cb)
        self.assertIsInstance(h, events.Handle)
        self.assertIn(h, self.loop._ready)

    def test_call_later(self):
        def cb():
            pass

        h = self.loop.call_later(10.0, cb)
        self.assertIsInstance(h, events.TimerHandle)
        self.assertIn(h, self.loop._scheduled)
        self.assertNotIn(h, self.loop._ready)

    def test_call_later_negative_delays(self):
        calls = []

        def cb(arg):
            calls.append(arg)

        self.loop._process_events = unittest.mock.Mock()
        self.loop.call_later(-1, cb, 'a')
        self.loop.call_later(-2, cb, 'b')
        self.loop.run_once()
        self.assertEqual(calls, ['b', 'a'])

    def test_time_and_call_at(self):
        def cb():
            self.loop.stop()

        self.loop._process_events = unittest.mock.Mock()
        when = self.loop.time() + 0.1
        self.loop.call_at(when, cb)
        t0 = self.loop.time()
        self.loop.run_forever()
        t1 = self.loop.time()
        self.assertTrue(0.09 <= t1-t0 <= 0.12, t1-t0)

    def test_run_once_in_executor_handle(self):
        def cb():
            pass

        self.assertRaises(
            AssertionError, self.loop.run_in_executor,
            None, events.Handle(cb, ()), ('',))
        self.assertRaises(
            AssertionError, self.loop.run_in_executor,
            None, events.TimerHandle(10, cb, ()))

    def test_run_once_in_executor_cancelled(self):
        def cb():
            pass
        h = events.Handle(cb, ())
        h.cancel()

        f = self.loop.run_in_executor(None, h)
        self.assertIsInstance(f, futures.Future)
        self.assertTrue(f.done())
        self.assertIsNone(f.result())

    def test_run_once_in_executor_plain(self):
        def cb():
            pass
        h = events.Handle(cb, ())
        f = futures.Future()
        executor = unittest.mock.Mock()
        executor.submit.return_value = f

        self.loop.set_default_executor(executor)

        res = self.loop.run_in_executor(None, h)
        self.assertIs(f, res)

        executor = unittest.mock.Mock()
        executor.submit.return_value = f
        res = self.loop.run_in_executor(executor, h)
        self.assertIs(f, res)
        self.assertTrue(executor.submit.called)

        f.cancel()  # Don't complain about abandoned Future.

    def test_run_once(self):
        self.loop._run_once = unittest.mock.Mock()
        self.loop._run_once.side_effect = base_events._StopError
        self.loop.run_once()
        self.assertTrue(self.loop._run_once.called)

    def test__run_once(self):
        h1 = events.TimerHandle(time.monotonic() + 0.1, lambda: True, ())
        h2 = events.TimerHandle(time.monotonic() + 10.0, lambda: True, ())

        h1.cancel()

        self.loop._process_events = unittest.mock.Mock()
        self.loop._scheduled.append(h1)
        self.loop._scheduled.append(h2)
        self.loop._run_once()

        t = self.loop._selector.select.call_args[0][0]
        self.assertTrue(9.99 < t < 10.1)
        self.assertEqual([h2], self.loop._scheduled)
        self.assertTrue(self.loop._process_events.called)

    def test__run_once_timeout(self):
        h = events.TimerHandle(time.monotonic() + 10.0, lambda: True, ())

        self.loop._process_events = unittest.mock.Mock()
        self.loop._scheduled.append(h)
        self.loop._run_once(1.0)
        self.assertEqual((1.0,), self.loop._selector.select.call_args[0])

    def test__run_once_timeout_with_ready(self):
        # If event loop has ready callbacks, select timeout is always 0.
        h = events.TimerHandle(time.monotonic() + 10.0, lambda: True, ())

        self.loop._process_events = unittest.mock.Mock()
        self.loop._scheduled.append(h)
        self.loop._ready.append(h)
        self.loop._run_once(1.0)

        self.assertEqual((0,), self.loop._selector.select.call_args[0])

    @unittest.mock.patch('tulip.base_events.time')
    @unittest.mock.patch('tulip.base_events.tulip_log')
    def test__run_once_logging(self, m_logging, m_time):
        # Log to INFO level if timeout > 1.0 sec.
        idx = -1
        data = [10.0, 10.0, 12.0, 13.0]

        def monotonic():
            nonlocal data, idx
            idx += 1
            return data[idx]

        m_time.monotonic = monotonic
        m_logging.INFO = logging.INFO
        m_logging.DEBUG = logging.DEBUG

        self.loop._scheduled.append(
            events.TimerHandle(11.0, lambda: True, ()))
        self.loop._process_events = unittest.mock.Mock()
        self.loop._run_once()
        self.assertEqual(logging.INFO, m_logging.log.call_args[0][0])

        idx = -1
        data = [10.0, 10.0, 10.3, 13.0]
        self.loop._scheduled = [events.TimerHandle(11.0, lambda:True, ())]
        self.loop._run_once()
        self.assertEqual(logging.DEBUG, m_logging.log.call_args[0][0])

    def test__run_once_schedule_handle(self):
        handle = None
        processed = False

        def cb(loop):
            nonlocal processed, handle
            processed = True
            handle = loop.call_soon(lambda: True)

        h = events.TimerHandle(time.monotonic() - 1, cb, (self.loop,))

        self.loop._process_events = unittest.mock.Mock()
        self.loop._scheduled.append(h)
        self.loop._run_once()

        self.assertTrue(processed)
        self.assertEqual([handle], list(self.loop._ready))

    def test_run_until_complete_assertion(self):
        self.assertRaises(
            AssertionError, self.loop.run_until_complete, 'blah')

    @unittest.mock.patch('tulip.base_events.socket')
    def test_create_connection_mutiple_errors(self, m_socket):

        class MyProto(protocols.Protocol):
            pass

        @tasks.coroutine
        def getaddrinfo(*args, **kw):
            yield from []
            return [(2, 1, 6, '', ('107.6.106.82', 80)),
                    (2, 1, 6, '', ('107.6.106.82', 80))]

        idx = -1
        errors = ['err1', 'err2']

        def _socket(*args, **kw):
            nonlocal idx, errors
            idx += 1
            raise socket.error(errors[idx])

        m_socket.socket = _socket
        m_socket.error = socket.error

        self.loop.getaddrinfo = getaddrinfo

        task = tasks.Task(
            self.loop.create_connection(MyProto, 'example.com', 80))
        yield from tasks.wait(task)
        exc = task.exception()
        self.assertEqual("Multiple exceptions: err1, err2", str(exc))
