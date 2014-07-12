"""Tests for tasks.py."""

import re
import sys
import types
import unittest
import weakref

import trollius as asyncio
from trollius import From, Return
from trollius import coroutines
from trollius import test_support as support
from trollius import test_utils
from trollius.test_support import assert_python_ok
from trollius.test_utils import mock


PY3 = (sys.version_info >= (3,))
PY34 = (sys.version_info >= (3, 4))
PY35 = (sys.version_info >= (3, 5))


@asyncio.coroutine
def coroutine_function():
    pass


def format_coroutine(qualname, state, src, source_traceback, generator=False):
    if generator:
        state = '%s' % state
    else:
        state = '%s, defined' % state
    if source_traceback is not None:
        frame = source_traceback[-1]
        return ('coro=<%s() %s at %s> created at %s:%s'
                % (qualname, state, src, frame[0], frame[1]))
    else:
        return 'coro=<%s() %s at %s>' % (qualname, state, src)


class Dummy:

    def __repr__(self):
        return '<Dummy>'

    def __call__(self, *args):
        pass


class TaskTests(test_utils.TestCase):

    def setUp(self):
        self.loop = self.new_test_loop()

    def test_task_class(self):
        @asyncio.coroutine
        def notmuch():
            return 'ok'
        t = asyncio.Task(notmuch(), loop=self.loop)
        self.loop.run_until_complete(t)
        self.assertTrue(t.done())
        self.assertEqual(t.result(), 'ok')
        self.assertIs(t._loop, self.loop)

        loop = asyncio.new_event_loop()
        self.set_event_loop(loop)
        t = asyncio.Task(notmuch(), loop=loop)
        self.assertIs(t._loop, loop)
        loop.run_until_complete(t)
        loop.close()

    def test_async_coroutine(self):
        @asyncio.coroutine
        def notmuch():
            return 'ok'
        t = asyncio.async(notmuch(), loop=self.loop)
        self.loop.run_until_complete(t)
        self.assertTrue(t.done())
        self.assertEqual(t.result(), 'ok')
        self.assertIs(t._loop, self.loop)

        loop = asyncio.new_event_loop()
        self.set_event_loop(loop)
        t = asyncio.async(notmuch(), loop=loop)
        self.assertIs(t._loop, loop)
        loop.run_until_complete(t)
        loop.close()

    def test_async_future(self):
        f_orig = asyncio.Future(loop=self.loop)
        f_orig.set_result('ko')

        f = asyncio.async(f_orig)
        self.loop.run_until_complete(f)
        self.assertTrue(f.done())
        self.assertEqual(f.result(), 'ko')
        self.assertIs(f, f_orig)

        loop = asyncio.new_event_loop()
        self.set_event_loop(loop)

        with self.assertRaises(ValueError):
            f = asyncio.async(f_orig, loop=loop)

        loop.close()

        f = asyncio.async(f_orig, loop=self.loop)
        self.assertIs(f, f_orig)

    def test_async_task(self):
        @asyncio.coroutine
        def notmuch():
            return 'ok'
        t_orig = asyncio.Task(notmuch(), loop=self.loop)
        t = asyncio.async(t_orig)
        self.loop.run_until_complete(t)
        self.assertTrue(t.done())
        self.assertEqual(t.result(), 'ok')
        self.assertIs(t, t_orig)

        loop = asyncio.new_event_loop()
        self.set_event_loop(loop)

        with self.assertRaises(ValueError):
            t = asyncio.async(t_orig, loop=loop)

        loop.close()

        t = asyncio.async(t_orig, loop=self.loop)
        self.assertIs(t, t_orig)

    def test_async_neither(self):
        with self.assertRaises(TypeError):
            asyncio.async('ok')

    def test_task_repr(self):
        @asyncio.coroutine
        def noop():
            yield From(None)
            raise Return('abc')

        @asyncio.coroutine
        def notmuch():
            yield From(noop())
            raise Return('abc')

        # test coroutine function
        self.assertEqual(notmuch.__name__, 'notmuch')
        if PY35:
            self.assertEqual(notmuch.__qualname__,
                             'TaskTests.test_task_repr.<locals>.notmuch')
        self.assertEqual(notmuch.__module__, __name__)

        filename, lineno = test_utils.get_function_source(notmuch)
        src = "%s:%s" % (filename, lineno)

        # test coroutine object
        gen = notmuch()
        if PY35 or (coroutines._DEBUG and PY3):
            coro_qualname = 'TaskTests.test_task_repr.<locals>.notmuch'
        else:
            coro_qualname = 'notmuch'
        self.assertEqual(gen.__name__, 'notmuch')
        if PY35:
            self.assertEqual(gen.__qualname__,
                             coro_qualname)

        # test pending Task
        t = asyncio.Task(gen, loop=self.loop)
        t.add_done_callback(Dummy())

        coro = format_coroutine(coro_qualname, 'running', src,
                                t._source_traceback, generator=True)
        self.assertEqual(repr(t),
                         '<Task pending %s cb=[<Dummy>()]>' % coro)

        # test cancelling Task
        t.cancel()  # Does not take immediate effect!
        self.assertEqual(repr(t),
                         '<Task cancelling %s cb=[<Dummy>()]>' % coro)

        # test cancelled Task
        self.assertRaises(asyncio.CancelledError,
                          self.loop.run_until_complete, t)
        coro = format_coroutine(coro_qualname, 'done', src,
                                t._source_traceback)
        self.assertEqual(repr(t),
                         '<Task cancelled %s>' % coro)

        # test finished Task
        t = asyncio.Task(notmuch(), loop=self.loop)
        self.loop.run_until_complete(t)
        coro = format_coroutine(coro_qualname, 'done', src,
                                t._source_traceback)
        self.assertEqual(repr(t),
                         "<Task finished %s result='abc'>" % coro)

    def test_task_repr_coro_decorator(self):
        @asyncio.coroutine
        def notmuch():
            # notmuch() function doesn't use yield: it will be wrapped by
            # @coroutine decorator
            return 123

        # test coroutine function
        self.assertEqual(notmuch.__name__, 'notmuch')
        if PY35:
            self.assertEqual(notmuch.__qualname__,
                             'TaskTests.test_task_repr_coro_decorator.<locals>.notmuch')
        self.assertEqual(notmuch.__module__, __name__)

        # test coroutine object
        gen = notmuch()
        if PY35 or coroutines._DEBUG:
            # On Python >= 3.5, generators now inherit the name of the
            # function, as expected, and have a qualified name (__qualname__
            # attribute).
            coro_name = 'notmuch'
            if PY35 or (coroutines._DEBUG and PY3):
                coro_qualname = 'TaskTests.test_task_repr_coro_decorator.<locals>.notmuch'
            else:
                coro_qualname = 'notmuch'
        else:
            # On Python < 3.5, generators inherit the name of the code, not of
            # the function. See: http://bugs.python.org/issue21205
            coro_name = coro_qualname = 'coro'
        self.assertEqual(gen.__name__, coro_name)
        if PY35:
            self.assertEqual(gen.__qualname__, coro_qualname)

        # test repr(CoroWrapper)
        if coroutines._DEBUG:
            # format the coroutine object
            if coroutines._DEBUG:
                filename, lineno = test_utils.get_function_source(notmuch)
                frame = gen._source_traceback[-1]
                coro = ('%s() running, defined at %s:%s, created at %s:%s'
                        % (coro_qualname, filename, lineno,
                           frame[0], frame[1]))
            else:
                code = gen.gi_code
                coro = ('%s() running at %s:%s'
                        % (coro_qualname, code.co_filename, code.co_firstlineno))

            self.assertEqual(repr(gen), '<CoroWrapper %s>' % coro)

        # test pending Task
        t = asyncio.Task(gen, loop=self.loop)
        t.add_done_callback(Dummy())

        # format the coroutine object
        if coroutines._DEBUG:
            src = '%s:%s' % test_utils.get_function_source(notmuch)
        else:
            code = gen.gi_code
            src = '%s:%s' % (code.co_filename, code.co_firstlineno)
        coro = format_coroutine(coro_qualname, 'running', src,
                                t._source_traceback,
                                generator=not coroutines._DEBUG)
        self.assertEqual(repr(t),
                         '<Task pending %s cb=[<Dummy>()]>' % coro)
        self.loop.run_until_complete(t)

    def test_task_repr_wait_for(self):
        @asyncio.coroutine
        def wait_for(fut):
            res = yield From(fut)
            raise Return(res)

        fut = asyncio.Future(loop=self.loop)
        task = asyncio.Task(wait_for(fut), loop=self.loop)
        test_utils.run_briefly(self.loop)
        self.assertRegex(repr(task),
                         '<Task .* wait_for=%s>' % re.escape(repr(fut)))

        fut.set_result(None)
        self.loop.run_until_complete(task)

    def test_task_basics(self):
        @asyncio.coroutine
        def outer():
            a = yield From(inner1())
            b = yield From(inner2())
            raise Return(a+b)

        @asyncio.coroutine
        def inner1():
            return 42

        @asyncio.coroutine
        def inner2():
            return 1000

        t = outer()
        self.assertEqual(self.loop.run_until_complete(t), 1042)

    def test_cancel(self):

        def gen():
            when = yield
            self.assertAlmostEqual(10.0, when)
            yield 0

        loop = self.new_test_loop(gen)

        @asyncio.coroutine
        def task():
            yield From(asyncio.sleep(10.0, loop=loop))
            raise Return(12)

        t = asyncio.Task(task(), loop=loop)
        test_utils.run_briefly(loop)
        loop.call_soon(t.cancel)
        with self.assertRaises(asyncio.CancelledError):
            loop.run_until_complete(t)
        self.assertTrue(t.done())
        self.assertTrue(t.cancelled())
        self.assertFalse(t.cancel())

    def test_cancel_yield(self):
        @asyncio.coroutine
        def task():
            yield From(None)
            yield From(None)
            raise Return(12)

        t = asyncio.Task(task(), loop=self.loop)
        test_utils.run_briefly(self.loop)  # start coro
        t.cancel()
        self.assertRaises(
            asyncio.CancelledError, self.loop.run_until_complete, t)
        self.assertTrue(t.done())
        self.assertTrue(t.cancelled())
        self.assertFalse(t.cancel())

    def test_cancel_inner_future(self):
        f = asyncio.Future(loop=self.loop)

        @asyncio.coroutine
        def task():
            yield From(f)
            raise Return(12)

        t = asyncio.Task(task(), loop=self.loop)
        test_utils.run_briefly(self.loop)  # start task
        f.cancel()
        with self.assertRaises(asyncio.CancelledError):
            self.loop.run_until_complete(t)
        self.assertTrue(f.cancelled())
        self.assertTrue(t.cancelled())

    def test_cancel_both_task_and_inner_future(self):
        f = asyncio.Future(loop=self.loop)

        @asyncio.coroutine
        def task():
            yield From(f)
            raise Return(12)

        t = asyncio.Task(task(), loop=self.loop)
        test_utils.run_briefly(self.loop)

        f.cancel()
        t.cancel()

        with self.assertRaises(asyncio.CancelledError):
            self.loop.run_until_complete(t)

        self.assertTrue(t.done())
        self.assertTrue(f.cancelled())
        self.assertTrue(t.cancelled())

    def test_cancel_task_catching(self):
        fut1 = asyncio.Future(loop=self.loop)
        fut2 = asyncio.Future(loop=self.loop)

        @asyncio.coroutine
        def task():
            yield From(fut1)
            try:
                yield From(fut2)
            except asyncio.CancelledError:
                raise Return(42)

        t = asyncio.Task(task(), loop=self.loop)
        test_utils.run_briefly(self.loop)
        self.assertIs(t._fut_waiter, fut1)  # White-box test.
        fut1.set_result(None)
        test_utils.run_briefly(self.loop)
        self.assertIs(t._fut_waiter, fut2)  # White-box test.
        t.cancel()
        self.assertTrue(fut2.cancelled())
        res = self.loop.run_until_complete(t)
        self.assertEqual(res, 42)
        self.assertFalse(t.cancelled())

    def test_cancel_task_ignoring(self):
        fut1 = asyncio.Future(loop=self.loop)
        fut2 = asyncio.Future(loop=self.loop)
        fut3 = asyncio.Future(loop=self.loop)

        @asyncio.coroutine
        def task():
            yield From(fut1)
            try:
                yield From(fut2)
            except asyncio.CancelledError:
                pass
            res = yield From(fut3)
            raise Return(res)

        t = asyncio.Task(task(), loop=self.loop)
        test_utils.run_briefly(self.loop)
        self.assertIs(t._fut_waiter, fut1)  # White-box test.
        fut1.set_result(None)
        test_utils.run_briefly(self.loop)
        self.assertIs(t._fut_waiter, fut2)  # White-box test.
        t.cancel()
        self.assertTrue(fut2.cancelled())
        test_utils.run_briefly(self.loop)
        self.assertIs(t._fut_waiter, fut3)  # White-box test.
        fut3.set_result(42)
        res = self.loop.run_until_complete(t)
        self.assertEqual(res, 42)
        self.assertFalse(fut3.cancelled())
        self.assertFalse(t.cancelled())

    def test_cancel_current_task(self):
        loop = asyncio.new_event_loop()
        self.set_event_loop(loop)

        @asyncio.coroutine
        def task():
            t.cancel()
            self.assertTrue(t._must_cancel)  # White-box test.
            # The sleep should be cancelled immediately.
            yield From(asyncio.sleep(100, loop=loop))
            raise Return(12)

        t = asyncio.Task(task(), loop=loop)
        self.assertRaises(
            asyncio.CancelledError, loop.run_until_complete, t)
        self.assertTrue(t.done())
        self.assertFalse(t._must_cancel)  # White-box test.
        self.assertFalse(t.cancel())

    def test_stop_while_run_in_complete(self):

        def gen():
            when = yield
            self.assertAlmostEqual(0.1, when)
            when = yield 0.1
            self.assertAlmostEqual(0.2, when)
            when = yield 0.1
            self.assertAlmostEqual(0.3, when)
            yield 0.1

        loop = self.new_test_loop(gen)

        non_local = {'x': 0}
        waiters = []

        @asyncio.coroutine
        def task():
            while non_local['x'] < 10:
                waiters.append(asyncio.sleep(0.1, loop=loop))
                yield From(waiters[-1])
                non_local['x'] += 1
                if non_local['x'] == 3:
                    loop.stop()

        t = asyncio.Task(task(), loop=loop)
        with self.assertRaises(RuntimeError) as cm:
            loop.run_until_complete(t)
        self.assertEqual(str(cm.exception),
                         'Event loop stopped before Future completed.')
        self.assertFalse(t.done())
        self.assertEqual(non_local['x'], 3)
        self.assertAlmostEqual(0.3, loop.time())

        # close generators
        for w in waiters:
            w.close()
        t.cancel()
        self.assertRaises(asyncio.CancelledError, loop.run_until_complete, t)

    def test_wait_for(self):

        @asyncio.coroutine
        def gen():
            when = yield
            self.assertAlmostEqual(0.2, when)
            when = yield 0
            self.assertAlmostEqual(0.1, when)
            when = yield 0.1

        loop = self.new_test_loop(gen)

        non_local = {'foo_running': None}

        @asyncio.coroutine
        def foo():
            non_local['foo_running'] = True
            try:
                yield From(asyncio.sleep(0.2, loop=loop))
            finally:
                non_local['foo_running'] = False
            raise Return('done')

        fut = asyncio.Task(foo(), loop=loop)
        test_utils.run_briefly(loop)

        with self.assertRaises(asyncio.TimeoutError):
            loop.run_until_complete(asyncio.wait_for(fut, 0.1, loop=loop))

        # Trollius issue #2: need to run the loop briefly to ensure that the
        # cancellation is propagated to all tasks
        waiter = asyncio.Future(loop=loop)
        fut.add_done_callback(lambda f: waiter.set_result(True))
        loop.run_until_complete(waiter)

        self.assertTrue(fut.done())
        # it should have been cancelled due to the timeout
        self.assertTrue(fut.cancelled())
        self.assertAlmostEqual(0.1, loop.time())
        self.assertEqual(non_local['foo_running'], False)

    def test_wait_for_blocking(self):
        loop = self.new_test_loop()

        @asyncio.coroutine
        def coro():
            return 'done'

        res = loop.run_until_complete(asyncio.wait_for(coro(),
                                                       timeout=None,
                                                       loop=loop))
        self.assertEqual(res, 'done')

    def test_wait_for_with_global_loop(self):

        def gen():
            when = yield
            self.assertAlmostEqual(0.2, when)
            when = yield 0
            self.assertAlmostEqual(0.01, when)
            yield 0.01

        loop = self.new_test_loop(gen)

        @asyncio.coroutine
        def foo():
            yield From(asyncio.sleep(0.2, loop=loop))
            raise Return('done')

        asyncio.set_event_loop(loop)
        try:
            fut = asyncio.Task(foo(), loop=loop)
            test_utils.run_briefly(loop)
            with self.assertRaises(asyncio.TimeoutError):
                loop.run_until_complete(asyncio.wait_for(fut, 0.01))
        finally:
            asyncio.set_event_loop(None)

        # Trollius issue #2: need to run the loop briefly to ensure that the
        # cancellation is propagated to all tasks
        waiter = asyncio.Future(loop=loop)
        fut.add_done_callback(lambda f: waiter.set_result(True))
        loop.run_until_complete(waiter)

        self.assertAlmostEqual(0.01, loop.time())
        self.assertTrue(fut.done())
        self.assertTrue(fut.cancelled())

    def test_wait(self):

        def gen():
            when = yield
            self.assertAlmostEqual(0.1, when)
            when = yield 0
            self.assertAlmostEqual(0.15, when)
            yield 0.15

        loop = self.new_test_loop(gen)

        a = asyncio.Task(asyncio.sleep(0.1, loop=loop), loop=loop)
        b = asyncio.Task(asyncio.sleep(0.15, loop=loop), loop=loop)

        @asyncio.coroutine
        def foo():
            done, pending = yield From(asyncio.wait([b, a], loop=loop))
            self.assertEqual(done, set([a, b]))
            self.assertEqual(pending, set())
            raise Return(42)

        res = loop.run_until_complete(asyncio.Task(foo(), loop=loop))
        self.assertEqual(res, 42)
        self.assertAlmostEqual(0.15, loop.time())

        # Doing it again should take no time and exercise a different path.
        res = loop.run_until_complete(asyncio.Task(foo(), loop=loop))
        self.assertAlmostEqual(0.15, loop.time())
        self.assertEqual(res, 42)

    def test_wait_with_global_loop(self):

        def gen():
            when = yield
            self.assertAlmostEqual(0.01, when)
            when = yield 0
            self.assertAlmostEqual(0.015, when)
            yield 0.015

        loop = self.new_test_loop(gen)

        a = asyncio.Task(asyncio.sleep(0.01, loop=loop), loop=loop)
        b = asyncio.Task(asyncio.sleep(0.015, loop=loop), loop=loop)

        @asyncio.coroutine
        def foo():
            done, pending = yield From(asyncio.wait([b, a]))
            self.assertEqual(done, set([a, b]))
            self.assertEqual(pending, set())
            raise Return(42)

        asyncio.set_event_loop(loop)
        res = loop.run_until_complete(
            asyncio.Task(foo(), loop=loop))

        self.assertEqual(res, 42)

    def test_wait_duplicate_coroutines(self):
        @asyncio.coroutine
        def coro(s):
            return s
        c = coro('test')

        task = asyncio.Task(
            asyncio.wait([c, c, coro('spam')], loop=self.loop),
            loop=self.loop)

        done, pending = self.loop.run_until_complete(task)

        self.assertFalse(pending)
        self.assertEqual(set(f.result() for f in done), set(('test', 'spam')))

    def test_wait_errors(self):
        self.assertRaises(
            ValueError, self.loop.run_until_complete,
            asyncio.wait(set(), loop=self.loop))

        self.assertRaises(
            ValueError, self.loop.run_until_complete,
            asyncio.wait([asyncio.sleep(10.0, loop=self.loop)],
                         return_when=-1, loop=self.loop))

    def test_wait_first_completed(self):

        def gen():
            when = yield
            self.assertAlmostEqual(10.0, when)
            when = yield 0
            self.assertAlmostEqual(0.1, when)
            yield 0.1

        loop = self.new_test_loop(gen)

        a = asyncio.Task(asyncio.sleep(10.0, loop=loop), loop=loop)
        b = asyncio.Task(asyncio.sleep(0.1, loop=loop), loop=loop)
        task = asyncio.Task(
            asyncio.wait([b, a], return_when=asyncio.FIRST_COMPLETED,
                         loop=loop),
            loop=loop)

        done, pending = loop.run_until_complete(task)
        self.assertEqual(set((b,)), done)
        self.assertEqual(set((a,)), pending)
        self.assertFalse(a.done())
        self.assertTrue(b.done())
        self.assertIsNone(b.result())
        self.assertAlmostEqual(0.1, loop.time())

        # move forward to close generator
        loop.advance_time(10)
        loop.run_until_complete(asyncio.wait([a, b], loop=loop))

    def test_wait_really_done(self):
        # there is possibility that some tasks in the pending list
        # became done but their callbacks haven't all been called yet

        @asyncio.coroutine
        def coro1():
            yield From(None)

        @asyncio.coroutine
        def coro2():
            yield From(None)
            yield From(None)

        a = asyncio.Task(coro1(), loop=self.loop)
        b = asyncio.Task(coro2(), loop=self.loop)
        task = asyncio.Task(
            asyncio.wait([b, a], return_when=asyncio.FIRST_COMPLETED,
                         loop=self.loop),
            loop=self.loop)

        done, pending = self.loop.run_until_complete(task)
        self.assertEqual(set((a, b)), done)
        self.assertTrue(a.done())
        self.assertIsNone(a.result())
        self.assertTrue(b.done())
        self.assertIsNone(b.result())

    def test_wait_first_exception(self):

        def gen():
            when = yield
            self.assertAlmostEqual(10.0, when)
            yield 0

        loop = self.new_test_loop(gen)

        # first_exception, task already has exception
        a = asyncio.Task(asyncio.sleep(10.0, loop=loop), loop=loop)

        @asyncio.coroutine
        def exc():
            raise ZeroDivisionError('err')

        b = asyncio.Task(exc(), loop=loop)
        task = asyncio.Task(
            asyncio.wait([b, a], return_when=asyncio.FIRST_EXCEPTION,
                         loop=loop),
            loop=loop)

        done, pending = loop.run_until_complete(task)
        self.assertEqual(set((b,)), done)
        self.assertEqual(set((a,)), pending)
        self.assertAlmostEqual(0, loop.time())

        # move forward to close generator
        loop.advance_time(10)
        loop.run_until_complete(asyncio.wait([a, b], loop=loop))

    def test_wait_first_exception_in_wait(self):

        def gen():
            when = yield
            self.assertAlmostEqual(10.0, when)
            when = yield 0
            self.assertAlmostEqual(0.01, when)
            yield 0.01

        loop = self.new_test_loop(gen)

        # first_exception, exception during waiting
        a = asyncio.Task(asyncio.sleep(10.0, loop=loop), loop=loop)

        @asyncio.coroutine
        def exc():
            yield From(asyncio.sleep(0.01, loop=loop))
            raise ZeroDivisionError('err')

        b = asyncio.Task(exc(), loop=loop)
        task = asyncio.wait([b, a], return_when=asyncio.FIRST_EXCEPTION,
                            loop=loop)

        done, pending = loop.run_until_complete(task)
        self.assertEqual(set((b,)), done)
        self.assertEqual(set((a,)), pending)
        self.assertAlmostEqual(0.01, loop.time())

        # move forward to close generator
        loop.advance_time(10)
        loop.run_until_complete(asyncio.wait([a, b], loop=loop))

    def test_wait_with_exception(self):

        def gen():
            when = yield
            self.assertAlmostEqual(0.1, when)
            when = yield 0
            self.assertAlmostEqual(0.15, when)
            yield 0.15

        loop = self.new_test_loop(gen)

        a = asyncio.Task(asyncio.sleep(0.1, loop=loop), loop=loop)

        @asyncio.coroutine
        def sleeper():
            yield From(asyncio.sleep(0.15, loop=loop))
            raise ZeroDivisionError('really')

        b = asyncio.Task(sleeper(), loop=loop)

        @asyncio.coroutine
        def foo():
            done, pending = yield From(asyncio.wait([b, a], loop=loop))
            self.assertEqual(len(done), 2)
            self.assertEqual(pending, set())
            errors = set(f for f in done if f.exception() is not None)
            self.assertEqual(len(errors), 1)

        loop.run_until_complete(asyncio.Task(foo(), loop=loop))
        self.assertAlmostEqual(0.15, loop.time())

        loop.run_until_complete(asyncio.Task(foo(), loop=loop))
        self.assertAlmostEqual(0.15, loop.time())

    def test_wait_with_timeout(self):

        def gen():
            when = yield
            self.assertAlmostEqual(0.1, when)
            when = yield 0
            self.assertAlmostEqual(0.15, when)
            when = yield 0
            self.assertAlmostEqual(0.11, when)
            yield 0.11

        loop = self.new_test_loop(gen)

        a = asyncio.Task(asyncio.sleep(0.1, loop=loop), loop=loop)
        b = asyncio.Task(asyncio.sleep(0.15, loop=loop), loop=loop)

        @asyncio.coroutine
        def foo():
            done, pending = yield From(asyncio.wait([b, a], timeout=0.11,
                                               loop=loop))
            self.assertEqual(done, set([a]))
            self.assertEqual(pending, set([b]))

        loop.run_until_complete(asyncio.Task(foo(), loop=loop))
        self.assertAlmostEqual(0.11, loop.time())

        # move forward to close generator
        loop.advance_time(10)
        loop.run_until_complete(asyncio.wait([a, b], loop=loop))

    def test_wait_concurrent_complete(self):

        def gen():
            when = yield
            self.assertAlmostEqual(0.1, when)
            when = yield 0
            self.assertAlmostEqual(0.15, when)
            when = yield 0
            self.assertAlmostEqual(0.1, when)
            yield 0.1

        loop = self.new_test_loop(gen)

        a = asyncio.Task(asyncio.sleep(0.1, loop=loop), loop=loop)
        b = asyncio.Task(asyncio.sleep(0.15, loop=loop), loop=loop)

        done, pending = loop.run_until_complete(
            asyncio.wait([b, a], timeout=0.1, loop=loop))

        self.assertEqual(done, set([a]))
        self.assertEqual(pending, set([b]))
        self.assertAlmostEqual(0.1, loop.time())

        # move forward to close generator
        loop.advance_time(10)
        loop.run_until_complete(asyncio.wait([a, b], loop=loop))

    def test_as_completed(self):

        def gen():
            yield 0
            yield 0
            yield 0.01
            yield 0

        loop = self.new_test_loop(gen)
        completed = set()
        non_local = {'time_shifted': False}

        @asyncio.coroutine
        def sleeper(dt, x):
            yield From(asyncio.sleep(dt, loop=loop))
            completed.add(x)
            if not non_local['time_shifted'] and 'a' in completed and 'b' in completed:
                non_local['time_shifted'] = True
                loop.advance_time(0.14)
            raise Return(x)

        a = sleeper(0.01, 'a')
        b = sleeper(0.01, 'b')
        c = sleeper(0.15, 'c')

        @asyncio.coroutine
        def foo():
            values = []
            for f in asyncio.as_completed([b, c, a], loop=loop):
                values.append((yield From(f)))
            raise Return(values)

        res = loop.run_until_complete(asyncio.Task(foo(), loop=loop))
        self.assertAlmostEqual(0.15, loop.time())
        self.assertTrue('a' in res[:2])
        self.assertTrue('b' in res[:2])
        self.assertEqual(res[2], 'c')

        # Doing it again should take no time and exercise a different path.
        res = loop.run_until_complete(asyncio.Task(foo(), loop=loop))
        self.assertAlmostEqual(0.15, loop.time())

    def test_as_completed_with_timeout(self):

        def gen():
            yield
            yield 0
            yield 0
            yield 0.1

        loop = self.new_test_loop(gen)

        a = asyncio.sleep(0.1, 'a', loop=loop)
        b = asyncio.sleep(0.15, 'b', loop=loop)

        @asyncio.coroutine
        def foo():
            values = []
            for f in asyncio.as_completed([a, b], timeout=0.12, loop=loop):
                if values:
                    loop.advance_time(0.02)
                try:
                    v = yield From(f)
                    values.append((1, v))
                except asyncio.TimeoutError as exc:
                    values.append((2, exc))
            raise Return(values)

        res = loop.run_until_complete(asyncio.Task(foo(), loop=loop))
        self.assertEqual(len(res), 2, res)
        self.assertEqual(res[0], (1, 'a'))
        self.assertEqual(res[1][0], 2)
        self.assertIsInstance(res[1][1], asyncio.TimeoutError)
        self.assertAlmostEqual(0.12, loop.time())

        # move forward to close generator
        loop.advance_time(10)
        loop.run_until_complete(asyncio.wait([a, b], loop=loop))

    def test_as_completed_with_unused_timeout(self):

        def gen():
            yield
            yield 0
            yield 0.01

        loop = self.new_test_loop(gen)

        a = asyncio.sleep(0.01, 'a', loop=loop)

        @asyncio.coroutine
        def foo():
            for f in asyncio.as_completed([a], timeout=1, loop=loop):
                v = yield From(f)
                self.assertEqual(v, 'a')

        loop.run_until_complete(asyncio.Task(foo(), loop=loop))

    def test_as_completed_reverse_wait(self):

        def gen():
            yield 0
            yield 0.05
            yield 0

        loop = self.new_test_loop(gen)

        a = asyncio.sleep(0.05, 'a', loop=loop)
        b = asyncio.sleep(0.10, 'b', loop=loop)
        fs = set((a, b))
        futs = list(asyncio.as_completed(fs, loop=loop))
        self.assertEqual(len(futs), 2)

        x = loop.run_until_complete(futs[1])
        self.assertEqual(x, 'a')
        self.assertAlmostEqual(0.05, loop.time())
        loop.advance_time(0.05)
        y = loop.run_until_complete(futs[0])
        self.assertEqual(y, 'b')
        self.assertAlmostEqual(0.10, loop.time())

    def test_as_completed_concurrent(self):

        def gen():
            when = yield
            self.assertAlmostEqual(0.05, when)
            when = yield 0
            self.assertAlmostEqual(0.05, when)
            yield 0.05

        loop = self.new_test_loop(gen)

        a = asyncio.sleep(0.05, 'a', loop=loop)
        b = asyncio.sleep(0.05, 'b', loop=loop)
        fs = set((a, b))
        futs = list(asyncio.as_completed(fs, loop=loop))
        self.assertEqual(len(futs), 2)
        waiter = asyncio.wait(futs, loop=loop)
        done, pending = loop.run_until_complete(waiter)
        self.assertEqual(set(f.result() for f in done), set(('a', 'b')))

    def test_as_completed_duplicate_coroutines(self):

        @asyncio.coroutine
        def coro(s):
            return s

        @asyncio.coroutine
        def runner():
            result = []
            c = coro('ham')
            for f in asyncio.as_completed([c, c, coro('spam')],
                                          loop=self.loop):
                result.append((yield From(f)))
            raise Return(result)

        fut = asyncio.Task(runner(), loop=self.loop)
        self.loop.run_until_complete(fut)
        result = fut.result()
        self.assertEqual(set(result), set(('ham', 'spam')))
        self.assertEqual(len(result), 2)

    def test_sleep(self):

        def gen():
            when = yield
            self.assertAlmostEqual(0.05, when)
            when = yield 0.05
            self.assertAlmostEqual(0.1, when)
            yield 0.05

        loop = self.new_test_loop(gen)

        @asyncio.coroutine
        def sleeper(dt, arg):
            yield From(asyncio.sleep(dt/2, loop=loop))
            res = yield From(asyncio.sleep(dt/2, arg, loop=loop))
            raise Return(res)

        t = asyncio.Task(sleeper(0.1, 'yeah'), loop=loop)
        loop.run_until_complete(t)
        self.assertTrue(t.done())
        self.assertEqual(t.result(), 'yeah')
        self.assertAlmostEqual(0.1, loop.time())

    def test_sleep_cancel(self):

        def gen():
            when = yield
            self.assertAlmostEqual(10.0, when)
            yield 0

        loop = self.new_test_loop(gen)

        t = asyncio.Task(asyncio.sleep(10.0, 'yeah', loop=loop),
                         loop=loop)

        non_local = {'handle': None}
        orig_call_later = loop.call_later

        def call_later(delay, callback, *args):
            non_local['handle'] = orig_call_later(delay, callback, *args)
            return non_local['handle']

        loop.call_later = call_later
        test_utils.run_briefly(loop)

        self.assertFalse(non_local['handle']._cancelled)

        t.cancel()
        test_utils.run_briefly(loop)
        self.assertTrue(non_local['handle']._cancelled)

    def test_task_cancel_sleeping_task(self):

        def gen():
            when = yield
            self.assertAlmostEqual(0.1, when)
            when = yield 0
            self.assertAlmostEqual(5000, when)
            yield 0.1

        loop = self.new_test_loop(gen)

        @asyncio.coroutine
        def sleep(dt):
            yield From(asyncio.sleep(dt, loop=loop))

        @asyncio.coroutine
        def doit():
            sleeper = asyncio.Task(sleep(5000), loop=loop)
            loop.call_later(0.1, sleeper.cancel)
            try:
                yield From(sleeper)
            except asyncio.CancelledError:
                raise Return('cancelled')
            else:
                raise Return('slept in')

        doer = doit()
        self.assertEqual(loop.run_until_complete(doer), 'cancelled')
        self.assertAlmostEqual(0.1, loop.time())

    def test_task_cancel_waiter_future(self):
        fut = asyncio.Future(loop=self.loop)

        @asyncio.coroutine
        def coro():
            yield From(fut)

        task = asyncio.Task(coro(), loop=self.loop)
        test_utils.run_briefly(self.loop)
        self.assertIs(task._fut_waiter, fut)

        task.cancel()
        test_utils.run_briefly(self.loop)
        self.assertRaises(
            asyncio.CancelledError, self.loop.run_until_complete, task)
        self.assertIsNone(task._fut_waiter)
        self.assertTrue(fut.cancelled())

    def test_step_in_completed_task(self):
        @asyncio.coroutine
        def notmuch():
            return 'ko'

        gen = notmuch()
        task = asyncio.Task(gen, loop=self.loop)
        task.set_result('ok')

        self.assertRaises(AssertionError, task._step)
        gen.close()

    def test_step_result(self):
        @asyncio.coroutine
        def notmuch():
            yield From(None)
            yield From(1)
            raise Return('ko')

        self.assertRaises(
            RuntimeError, self.loop.run_until_complete, notmuch())

    def test_step_result_future(self):
        # If coroutine returns future, task waits on this future.

        class Fut(asyncio.Future):
            def __init__(self, *args, **kwds):
                self.cb_added = False
                super(Fut, self).__init__(*args, **kwds)

            def add_done_callback(self, fn):
                self.cb_added = True
                super(Fut, self).add_done_callback(fn)

        fut = Fut(loop=self.loop)
        non_local = {'result': None}

        @asyncio.coroutine
        def wait_for_future():
            non_local['result'] = yield From(fut)

        t = asyncio.Task(wait_for_future(), loop=self.loop)
        test_utils.run_briefly(self.loop)
        self.assertTrue(fut.cb_added)

        res = object()
        fut.set_result(res)
        test_utils.run_briefly(self.loop)
        self.assertIs(res, non_local['result'])
        self.assertTrue(t.done())
        self.assertIsNone(t.result())

    def test_step_with_baseexception(self):
        @asyncio.coroutine
        def notmutch():
            raise BaseException()

        task = asyncio.Task(notmutch(), loop=self.loop)
        self.assertRaises(BaseException, task._step)

        self.assertTrue(task.done())
        self.assertIsInstance(task.exception(), BaseException)

    def test_baseexception_during_cancel(self):

        def gen():
            when = yield
            self.assertAlmostEqual(10.0, when)
            yield 0

        loop = self.new_test_loop(gen)

        @asyncio.coroutine
        def sleeper():
            yield From(asyncio.sleep(10, loop=loop))

        base_exc = BaseException()

        @asyncio.coroutine
        def notmutch():
            try:
                yield From(sleeper())
            except asyncio.CancelledError:
                raise base_exc

        task = asyncio.Task(notmutch(), loop=loop)
        test_utils.run_briefly(loop, 2)

        task.cancel()
        self.assertFalse(task.done())

        self.assertRaises(BaseException, test_utils.run_briefly, loop, 2)

        self.assertTrue(task.done())
        self.assertFalse(task.cancelled())
        self.assertIs(task.exception(), base_exc)

    def test_iscoroutinefunction(self):
        def fn():
            pass

        self.assertFalse(asyncio.iscoroutinefunction(fn))

        def fn1():
            yield
        self.assertFalse(asyncio.iscoroutinefunction(fn1))

        @asyncio.coroutine
        def fn2():
            yield
        self.assertTrue(asyncio.iscoroutinefunction(fn2))

    def test_coroutine_non_gen_function(self):
        @asyncio.coroutine
        def func():
            return 'test'

        self.assertTrue(asyncio.iscoroutinefunction(func))

        coro = func()
        self.assertTrue(asyncio.iscoroutine(coro))

        res = self.loop.run_until_complete(coro)
        self.assertEqual(res, 'test')

    def test_coroutine_non_gen_function_return_future(self):
        fut = asyncio.Future(loop=self.loop)

        @asyncio.coroutine
        def func():
            return fut

        @asyncio.coroutine
        def coro():
            fut.set_result('test')

        t1 = asyncio.Task(func(), loop=self.loop)
        t2 = asyncio.Task(coro(), loop=self.loop)
        res = self.loop.run_until_complete(t1)
        self.assertEqual(res, 'test')
        self.assertIsNone(t2.result())

    def test_current_task(self):
        self.assertIsNone(asyncio.Task.current_task(loop=self.loop))

        @asyncio.coroutine
        def coro(loop):
            self.assertTrue(asyncio.Task.current_task(loop=loop) is task)

        task = asyncio.Task(coro(self.loop), loop=self.loop)
        self.loop.run_until_complete(task)
        self.assertIsNone(asyncio.Task.current_task(loop=self.loop))

    def test_current_task_with_interleaving_tasks(self):
        self.assertIsNone(asyncio.Task.current_task(loop=self.loop))

        fut1 = asyncio.Future(loop=self.loop)
        fut2 = asyncio.Future(loop=self.loop)

        @asyncio.coroutine
        def coro1(loop):
            self.assertTrue(asyncio.Task.current_task(loop=loop) is task1)
            yield From(fut1)
            self.assertTrue(asyncio.Task.current_task(loop=loop) is task1)
            fut2.set_result(True)

        @asyncio.coroutine
        def coro2(loop):
            self.assertTrue(asyncio.Task.current_task(loop=loop) is task2)
            fut1.set_result(True)
            yield From(fut2)
            self.assertTrue(asyncio.Task.current_task(loop=loop) is task2)

        task1 = asyncio.Task(coro1(self.loop), loop=self.loop)
        task2 = asyncio.Task(coro2(self.loop), loop=self.loop)

        self.loop.run_until_complete(asyncio.wait((task1, task2),
                                                  loop=self.loop))
        self.assertIsNone(asyncio.Task.current_task(loop=self.loop))

    # Some thorough tests for cancellation propagation through
    # coroutines, tasks and wait().

    def test_yield_future_passes_cancel(self):
        # Cancelling outer() cancels inner() cancels waiter.
        non_local = {'proof': 0}
        waiter = asyncio.Future(loop=self.loop)

        @asyncio.coroutine
        def inner():
            try:
                yield From(waiter)
            except asyncio.CancelledError:
                non_local['proof'] += 1
                raise
            else:
                self.fail('got past sleep() in inner()')

        @asyncio.coroutine
        def outer():
            try:
                yield From(inner())
            except asyncio.CancelledError:
                non_local['proof'] += 100  # Expect this path.
            else:
                non_local['proof'] += 10

        f = asyncio.async(outer(), loop=self.loop)
        test_utils.run_briefly(self.loop)
        f.cancel()
        self.loop.run_until_complete(f)
        self.assertEqual(non_local['proof'], 101)
        self.assertTrue(waiter.cancelled())

    def test_yield_wait_does_not_shield_cancel(self):
        # Cancelling outer() makes wait() return early, leaves inner()
        # running.
        non_local = {'proof': 0}
        waiter = asyncio.Future(loop=self.loop)

        @asyncio.coroutine
        def inner():
            yield From(waiter)
            non_local['proof'] += 1

        @asyncio.coroutine
        def outer():
            d, p = yield From(asyncio.wait([inner()], loop=self.loop))
            non_local['proof'] += 100

        f = asyncio.async(outer(), loop=self.loop)
        test_utils.run_briefly(self.loop)
        f.cancel()
        self.assertRaises(
            asyncio.CancelledError, self.loop.run_until_complete, f)
        waiter.set_result(None)
        test_utils.run_briefly(self.loop)
        self.assertEqual(non_local['proof'], 1)

    def test_shield_result(self):
        inner = asyncio.Future(loop=self.loop)
        outer = asyncio.shield(inner)
        inner.set_result(42)
        res = self.loop.run_until_complete(outer)
        self.assertEqual(res, 42)

    def test_shield_exception(self):
        inner = asyncio.Future(loop=self.loop)
        outer = asyncio.shield(inner)
        test_utils.run_briefly(self.loop)
        exc = RuntimeError('expected')
        inner.set_exception(exc)
        test_utils.run_briefly(self.loop)
        self.assertIs(outer.exception(), exc)

    def test_shield_cancel(self):
        inner = asyncio.Future(loop=self.loop)
        outer = asyncio.shield(inner)
        test_utils.run_briefly(self.loop)
        inner.cancel()
        test_utils.run_briefly(self.loop)
        self.assertTrue(outer.cancelled())

    def test_shield_shortcut(self):
        fut = asyncio.Future(loop=self.loop)
        fut.set_result(42)
        res = self.loop.run_until_complete(asyncio.shield(fut))
        self.assertEqual(res, 42)

    def test_shield_effect(self):
        # Cancelling outer() does not affect inner().
        non_local = {'proof': 0}
        waiter = asyncio.Future(loop=self.loop)

        @asyncio.coroutine
        def inner():
            yield From(waiter)
            non_local['proof'] += 1

        @asyncio.coroutine
        def outer():
            yield From(asyncio.shield(inner(), loop=self.loop))
            non_local['proof'] += 100

        f = asyncio.async(outer(), loop=self.loop)
        test_utils.run_briefly(self.loop)
        f.cancel()
        with self.assertRaises(asyncio.CancelledError):
            self.loop.run_until_complete(f)
        waiter.set_result(None)
        test_utils.run_briefly(self.loop)
        self.assertEqual(non_local['proof'], 1)

    def test_shield_gather(self):
        child1 = asyncio.Future(loop=self.loop)
        child2 = asyncio.Future(loop=self.loop)
        parent = asyncio.gather(child1, child2, loop=self.loop)
        outer = asyncio.shield(parent, loop=self.loop)
        test_utils.run_briefly(self.loop)
        outer.cancel()
        test_utils.run_briefly(self.loop)
        self.assertTrue(outer.cancelled())
        child1.set_result(1)
        child2.set_result(2)
        test_utils.run_briefly(self.loop)
        self.assertEqual(parent.result(), [1, 2])

    def test_gather_shield(self):
        child1 = asyncio.Future(loop=self.loop)
        child2 = asyncio.Future(loop=self.loop)
        inner1 = asyncio.shield(child1, loop=self.loop)
        inner2 = asyncio.shield(child2, loop=self.loop)
        parent = asyncio.gather(inner1, inner2, loop=self.loop)
        test_utils.run_briefly(self.loop)
        parent.cancel()
        # This should cancel inner1 and inner2 but bot child1 and child2.
        test_utils.run_briefly(self.loop)
        self.assertIsInstance(parent.exception(), asyncio.CancelledError)
        self.assertTrue(inner1.cancelled())
        self.assertTrue(inner2.cancelled())
        child1.set_result(1)
        child2.set_result(2)
        test_utils.run_briefly(self.loop)

    def test_as_completed_invalid_args(self):
        fut = asyncio.Future(loop=self.loop)

        # as_completed() expects a list of futures, not a future instance
        self.assertRaises(TypeError, self.loop.run_until_complete,
            asyncio.as_completed(fut, loop=self.loop))
        coro = coroutine_function()
        self.assertRaises(TypeError, self.loop.run_until_complete,
            asyncio.as_completed(coro, loop=self.loop))
        coro.close()

    def test_wait_invalid_args(self):
        fut = asyncio.Future(loop=self.loop)

        # wait() expects a list of futures, not a future instance
        self.assertRaises(TypeError, self.loop.run_until_complete,
            asyncio.wait(fut, loop=self.loop))
        coro = coroutine_function()
        self.assertRaises(TypeError, self.loop.run_until_complete,
            asyncio.wait(coro, loop=self.loop))
        coro.close()

        # wait() expects at least a future
        self.assertRaises(ValueError, self.loop.run_until_complete,
            asyncio.wait([], loop=self.loop))

    def test_corowrapper_mocks_generator(self):

        def check():
            # A function that asserts various things.
            # Called twice, with different debug flag values.

            @asyncio.coroutine
            def coro():
                # The actual coroutine.
                self.assertTrue(gen.gi_running)
                yield From(fut)

            # A completed Future used to run the coroutine.
            fut = asyncio.Future(loop=self.loop)
            fut.set_result(None)

            # Call the coroutine.
            gen = coro()

            # Check some properties.
            self.assertTrue(asyncio.iscoroutine(gen))
            self.assertIsInstance(gen.gi_frame, types.FrameType)
            self.assertFalse(gen.gi_running)
            self.assertIsInstance(gen.gi_code, types.CodeType)

            # Run it.
            self.loop.run_until_complete(gen)

            # The frame should have changed.
            self.assertIsNone(gen.gi_frame)

        # Save debug flag.
        old_debug = asyncio.coroutines._DEBUG
        try:
            # Test with debug flag cleared.
            asyncio.coroutines._DEBUG = False
            check()

            # Test with debug flag set.
            asyncio.coroutines._DEBUG = True
            check()

        finally:
            # Restore original debug flag.
            asyncio.coroutines._DEBUG = old_debug

    def test_yield_from_corowrapper(self):
        old_debug = asyncio.coroutines._DEBUG
        asyncio.coroutines._DEBUG = True
        try:
            @asyncio.coroutine
            def t1():
                res = yield From(t2())
                raise Return(res)

            @asyncio.coroutine
            def t2():
                f = asyncio.Future(loop=self.loop)
                asyncio.Task(t3(f), loop=self.loop)
                res = yield From(f)
                raise Return(res)

            @asyncio.coroutine
            def t3(f):
                f.set_result((1, 2, 3))

            task = asyncio.Task(t1(), loop=self.loop)
            val = self.loop.run_until_complete(task)
            self.assertEqual(val, (1, 2, 3))
        finally:
            asyncio.coroutines._DEBUG = old_debug

    def test_yield_from_corowrapper_send(self):
        def foo():
            a = yield
            raise Return(a)

        def call(arg):
            cw = asyncio.coroutines.CoroWrapper(foo(), foo)
            cw.send(None)
            try:
                cw.send(arg)
            except StopIteration as ex:
                return ex.value
            else:
                raise AssertionError('StopIteration was expected')

        self.assertEqual(call((1, 2)), (1, 2))
        self.assertEqual(call('spam'), 'spam')

    def test_corowrapper_weakref(self):
        wd = weakref.WeakValueDictionary()
        def foo():
            yield From(None)
        cw = asyncio.coroutines.CoroWrapper(foo(), foo)
        wd['cw'] = cw  # Would fail without __weakref__ slot.
        cw.gen = None  # Suppress warning from __del__.

    @test_utils.skipUnless(PY34,
                           'need python 3.4 or later')
    def test_log_destroyed_pending_task(self):
        @asyncio.coroutine
        def kill_me(loop):
            future = asyncio.Future(loop=loop)
            yield From(future)
            # at this point, the only reference to kill_me() task is
            # the Task._wakeup() method in future._callbacks
            raise Exception("code never reached")

        mock_handler = mock.Mock()
        self.loop.set_debug(True)
        self.loop.set_exception_handler(mock_handler)

        # schedule the task
        coro = kill_me(self.loop)
        task = asyncio.async(coro, loop=self.loop)
        self.assertEqual(asyncio.Task.all_tasks(loop=self.loop), set((task,)))

        # execute the task so it waits for future
        self.loop._run_once()
        self.assertEqual(len(self.loop._ready), 0)

        # remove the future used in kill_me(), and references to the task
        del coro.gi_frame.f_locals['future']
        coro = None
        source_traceback = task._source_traceback
        task = None

        # no more reference to kill_me() task: the task is destroyed by the GC
        support.gc_collect()

        self.assertEqual(asyncio.Task.all_tasks(loop=self.loop), set())

        mock_handler.assert_called_with(self.loop, {
            'message': 'Task was destroyed but it is pending!',
            'task': mock.ANY,
            'source_traceback': source_traceback,
        })
        mock_handler.reset_mock()

    @mock.patch('trollius.coroutines.logger')
    def test_coroutine_never_yielded(self, m_log):
        debug = asyncio.coroutines._DEBUG
        try:
            asyncio.coroutines._DEBUG = True
            @asyncio.coroutine
            def coro_noop():
                pass
        finally:
            asyncio.coroutines._DEBUG = debug

        tb_filename = sys._getframe().f_code.co_filename
        tb_lineno = sys._getframe().f_lineno + 2
        # create a coroutine object but don't use it
        coro_noop()
        support.gc_collect()

        self.assertTrue(m_log.error.called)
        message = m_log.error.call_args[0][0]
        func_filename, func_lineno = test_utils.get_function_source(coro_noop)
        coro_name = getattr(coro_noop, '__qualname__', coro_noop.__name__)
        regex = (r'^<CoroWrapper %s\(\) .* at %s:%s, .*> was never yielded from\n'
                 r'Coroutine object created at \(most recent call last\):\n'
                 r'.*\n'
                 r'  File "%s", line %s, in test_coroutine_never_yielded\n'
                 r'    coro_noop\(\)$'
                 % (re.escape(coro_name),
                    re.escape(func_filename), func_lineno,
                    re.escape(tb_filename), tb_lineno))

        self.assertRegex(message, re.compile(regex, re.DOTALL))

    def test_task_source_traceback(self):
        self.loop.set_debug(True)

        task = asyncio.Task(coroutine_function(), loop=self.loop)
        self.check_soure_traceback(task._source_traceback, -1)
        self.loop.run_until_complete(task)


class GatherTestsBase:

    def setUp(self):
        self.one_loop = self.new_test_loop()
        self.other_loop = self.new_test_loop()
        self.set_event_loop(self.one_loop, cleanup=False)

    def _run_loop(self, loop):
        while loop._ready:
            test_utils.run_briefly(loop)

    def _check_success(self, **kwargs):
        a, b, c = [asyncio.Future(loop=self.one_loop) for i in range(3)]
        fut = asyncio.gather(*self.wrap_futures(a, b, c), **kwargs)
        cb = test_utils.MockCallback()
        fut.add_done_callback(cb)
        b.set_result(1)
        a.set_result(2)
        self._run_loop(self.one_loop)
        self.assertEqual(cb.called, False)
        self.assertFalse(fut.done())
        c.set_result(3)
        self._run_loop(self.one_loop)
        cb.assert_called_once_with(fut)
        self.assertEqual(fut.result(), [2, 1, 3])

    def test_success(self):
        self._check_success()
        self._check_success(return_exceptions=False)

    def test_result_exception_success(self):
        self._check_success(return_exceptions=True)

    def test_one_exception(self):
        a, b, c, d, e = [asyncio.Future(loop=self.one_loop) for i in range(5)]
        fut = asyncio.gather(*self.wrap_futures(a, b, c, d, e))
        cb = test_utils.MockCallback()
        fut.add_done_callback(cb)
        exc = ZeroDivisionError()
        a.set_result(1)
        b.set_exception(exc)
        self._run_loop(self.one_loop)
        self.assertTrue(fut.done())
        cb.assert_called_once_with(fut)
        self.assertIs(fut.exception(), exc)
        # Does nothing
        c.set_result(3)
        d.cancel()
        e.set_exception(RuntimeError())
        e.exception()

    def test_return_exceptions(self):
        a, b, c, d = [asyncio.Future(loop=self.one_loop) for i in range(4)]
        fut = asyncio.gather(*self.wrap_futures(a, b, c, d),
                             return_exceptions=True)
        cb = test_utils.MockCallback()
        fut.add_done_callback(cb)
        exc = ZeroDivisionError()
        exc2 = RuntimeError()
        b.set_result(1)
        c.set_exception(exc)
        a.set_result(3)
        self._run_loop(self.one_loop)
        self.assertFalse(fut.done())
        d.set_exception(exc2)
        self._run_loop(self.one_loop)
        self.assertTrue(fut.done())
        cb.assert_called_once_with(fut)
        self.assertEqual(fut.result(), [3, 1, exc, exc2])

    def test_env_var_debug(self):
        code = '\n'.join((
            'import trollius.coroutines',
            'print(trollius.coroutines._DEBUG)'))

        sts, stdout, stderr = assert_python_ok('-c', code,
                                               TROLLIUSDEBUG='')
        self.assertEqual(stdout.rstrip(), b'False')

        sts, stdout, stderr = assert_python_ok('-c', code,
                                               TROLLIUSDEBUG='1')
        self.assertEqual(stdout.rstrip(), b'True')


class FutureGatherTests(GatherTestsBase, test_utils.TestCase):

    def wrap_futures(self, *futures):
        return futures

    def _check_empty_sequence(self, seq_or_iter):
        asyncio.set_event_loop(self.one_loop)
        self.addCleanup(asyncio.set_event_loop, None)
        fut = asyncio.gather(*seq_or_iter)
        self.assertIsInstance(fut, asyncio.Future)
        self.assertIs(fut._loop, self.one_loop)
        self._run_loop(self.one_loop)
        self.assertTrue(fut.done())
        self.assertEqual(fut.result(), [])
        fut = asyncio.gather(*seq_or_iter, loop=self.other_loop)
        self.assertIs(fut._loop, self.other_loop)

    def test_constructor_empty_sequence(self):
        self._check_empty_sequence([])
        self._check_empty_sequence(())
        self._check_empty_sequence(set())
        self._check_empty_sequence(iter(""))

    def test_constructor_heterogenous_futures(self):
        fut1 = asyncio.Future(loop=self.one_loop)
        fut2 = asyncio.Future(loop=self.other_loop)
        with self.assertRaises(ValueError):
            asyncio.gather(fut1, fut2)
        with self.assertRaises(ValueError):
            asyncio.gather(fut1, loop=self.other_loop)

    def test_constructor_homogenous_futures(self):
        children = [asyncio.Future(loop=self.other_loop) for i in range(3)]
        fut = asyncio.gather(*children)
        self.assertIs(fut._loop, self.other_loop)
        self._run_loop(self.other_loop)
        self.assertFalse(fut.done())
        fut = asyncio.gather(*children, loop=self.other_loop)
        self.assertIs(fut._loop, self.other_loop)
        self._run_loop(self.other_loop)
        self.assertFalse(fut.done())

    def test_one_cancellation(self):
        a, b, c, d, e = [asyncio.Future(loop=self.one_loop) for i in range(5)]
        fut = asyncio.gather(a, b, c, d, e)
        cb = test_utils.MockCallback()
        fut.add_done_callback(cb)
        a.set_result(1)
        b.cancel()
        self._run_loop(self.one_loop)
        self.assertTrue(fut.done())
        cb.assert_called_once_with(fut)
        self.assertFalse(fut.cancelled())
        self.assertIsInstance(fut.exception(), asyncio.CancelledError)
        # Does nothing
        c.set_result(3)
        d.cancel()
        e.set_exception(RuntimeError())
        e.exception()

    def test_result_exception_one_cancellation(self):
        a, b, c, d, e, f = [asyncio.Future(loop=self.one_loop)
                            for i in range(6)]
        fut = asyncio.gather(a, b, c, d, e, f, return_exceptions=True)
        cb = test_utils.MockCallback()
        fut.add_done_callback(cb)
        a.set_result(1)
        zde = ZeroDivisionError()
        b.set_exception(zde)
        c.cancel()
        self._run_loop(self.one_loop)
        self.assertFalse(fut.done())
        d.set_result(3)
        e.cancel()
        rte = RuntimeError()
        f.set_exception(rte)
        res = self.one_loop.run_until_complete(fut)
        self.assertIsInstance(res[2], asyncio.CancelledError)
        self.assertIsInstance(res[4], asyncio.CancelledError)
        res[2] = res[4] = None
        self.assertEqual(res, [1, zde, None, 3, None, rte])
        cb.assert_called_once_with(fut)


class CoroutineGatherTests(GatherTestsBase, test_utils.TestCase):

    def setUp(self):
        super(CoroutineGatherTests, self).setUp()
        asyncio.set_event_loop(self.one_loop)

    def wrap_futures(self, *futures):
        coros = []
        for fut in futures:
            @asyncio.coroutine
            def coro(fut=fut):
                result = (yield From(fut))
                raise Return(result)
            coros.append(coro())
        return coros

    def test_constructor_loop_selection(self):
        @asyncio.coroutine
        def coro():
            return 'abc'
        gen1 = coro()
        gen2 = coro()
        fut = asyncio.gather(gen1, gen2)
        self.assertIs(fut._loop, self.one_loop)
        self.one_loop.run_until_complete(fut)

        self.set_event_loop(self.other_loop, cleanup=False)
        gen3 = coro()
        gen4 = coro()
        fut2 = asyncio.gather(gen3, gen4, loop=self.other_loop)
        self.assertIs(fut2._loop, self.other_loop)
        self.other_loop.run_until_complete(fut2)

    def test_duplicate_coroutines(self):
        @asyncio.coroutine
        def coro(s):
            return s
        c = coro('abc')
        fut = asyncio.gather(c, c, coro('def'), c, loop=self.one_loop)
        self._run_loop(self.one_loop)
        self.assertEqual(fut.result(), ['abc', 'abc', 'def', 'abc'])

    def test_cancellation_broadcast(self):
        # Cancelling outer() cancels all children.
        non_local = {'proof': 0}
        waiter = asyncio.Future(loop=self.one_loop)

        @asyncio.coroutine
        def inner():
            yield From(waiter)
            non_local['proof'] += 1

        child1 = asyncio.async(inner(), loop=self.one_loop)
        child2 = asyncio.async(inner(), loop=self.one_loop)
        non_local['gatherer'] = None

        @asyncio.coroutine
        def outer():
            non_local['gatherer'] = asyncio.gather(child1, child2, loop=self.one_loop)
            yield From(non_local['gatherer'])
            non_local['proof'] += 100

        f = asyncio.async(outer(), loop=self.one_loop)
        test_utils.run_briefly(self.one_loop)
        self.assertTrue(f.cancel())
        with self.assertRaises(asyncio.CancelledError):
            self.one_loop.run_until_complete(f)
        self.assertFalse(non_local['gatherer'].cancel())
        self.assertTrue(waiter.cancelled())
        self.assertTrue(child1.cancelled())
        self.assertTrue(child2.cancelled())
        test_utils.run_briefly(self.one_loop)
        self.assertEqual(non_local['proof'], 0)

    def test_exception_marking(self):
        # Test for the first line marked "Mark exception retrieved."

        @asyncio.coroutine
        def inner(f):
            yield From(f)
            raise RuntimeError('should not be ignored')

        a = asyncio.Future(loop=self.one_loop)
        b = asyncio.Future(loop=self.one_loop)

        @asyncio.coroutine
        def outer():
            yield From(asyncio.gather(inner(a), inner(b), loop=self.one_loop))

        f = asyncio.async(outer(), loop=self.one_loop)
        test_utils.run_briefly(self.one_loop)
        a.set_result(None)
        test_utils.run_briefly(self.one_loop)
        b.set_result(None)
        test_utils.run_briefly(self.one_loop)
        self.assertIsInstance(f.exception(), RuntimeError)


if __name__ == '__main__':
    unittest.main()
