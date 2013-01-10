"""Tests for tasks.py."""

import time
import unittest

from . import events
from . import futures
from . import tasks


class TaskTests(unittest.TestCase):

    def setUp(self):
        self.event_loop = events.new_event_loop()
        events.set_event_loop(self.event_loop)

    def tearDown(self):
        self.event_loop.close()

    def testTaskClass(self):
        @tasks.coroutine
        def notmuch():
            yield from []
            return 'ok'
        t = tasks.Task(notmuch())
        self.event_loop.run()
        self.assertTrue(t.done())
        self.assertEqual(t.result(), 'ok')

    def testTaskDecorator(self):
        @tasks.task
        def notmuch():
            yield from []
            return 'ko'
        t = notmuch()
        self.event_loop.run()
        self.assertTrue(t.done())
        self.assertEqual(t.result(), 'ko')

    def testWait(self):
        a = tasks.sleep(0.1)
        b = tasks.sleep(0.15)
        @tasks.coroutine
        def foo():
            done, pending = yield from tasks.wait([b, a])
            self.assertEqual(done, set([a, b]))
            self.assertEqual(pending, set())
            return 42
        t0 = time.monotonic()
        res = self.event_loop.run_until_complete(tasks.Task(foo()))
        t1 = time.monotonic()
        self.assertTrue(t1-t0 >= 0.14)
        self.assertEqual(res, 42)
        # Doing it again should take no time and exercise a different path.
        t0 = time.monotonic()
        res = self.event_loop.run_until_complete(tasks.Task(foo()))
        t1 = time.monotonic()
        self.assertTrue(t1-t0, 0.01)
        # TODO: Test different return_when values.

    def testWaitWithException(self):
        a = tasks.sleep(0.1)
        @tasks.coroutine
        def sleeper():
            yield from tasks.sleep(0.15)
            raise ZeroDivisionError('really')
        b = tasks.Task(sleeper())
        def foo():
            done, pending = yield from tasks.wait([b, a])
            self.assertEqual(len(done), 2)
            self.assertEqual(pending, set())
            errors = set(f for f in done if f.exception() is not None)
            self.assertEqual(len(errors), 1)
        t0 = time.monotonic()
        res = self.event_loop.run_until_complete(tasks.Task(foo()))
        t1 = time.monotonic()
        self.assertTrue(t1-t0 >= 0.14)
        t0 = time.monotonic()
        res = self.event_loop.run_until_complete(tasks.Task(foo()))
        t1 = time.monotonic()
        self.assertTrue(t1-t0 <= 0.01)

    def testWaitWithTimeout(self):
        a = tasks.sleep(0.1)
        b = tasks.sleep(0.15)
        def foo():
            done, pending = yield from tasks.wait([b, a], timeout=0.11)
            self.assertEqual(done, set([a]))
            self.assertEqual(pending, set([b]))
        t0 = time.monotonic()
        res = self.event_loop.run_until_complete(tasks.Task(foo()))
        t1 = time.monotonic()
        self.assertTrue(t1-t0 >= 0.1)
        self.assertTrue(t1-t0 <= 0.12)

    def testAsCompleted(self):
        @tasks.coroutine
        def sleeper(dt, x):
            yield from tasks.sleep(dt)
            return x
        a = sleeper(0.1, 'a')
        b = sleeper(0.1, 'b')
        c = sleeper(0.15, 'c')
        def foo():
            values = []
            for f in tasks.as_completed([b, c, a]):
                values.append((yield from f))
            return values
        t0 = time.monotonic()
        res = self.event_loop.run_until_complete(tasks.Task(foo()))
        t1 = time.monotonic()
        self.assertTrue(t1-t0 >= 0.14)
        self.assertTrue('a' in res[:2])
        self.assertTrue('b' in res[:2])
        self.assertEqual(res[2], 'c')
        # Doing it again should take no time and exercise a different path.
        t0 = time.monotonic()
        res = self.event_loop.run_until_complete(tasks.Task(foo()))
        t1 = time.monotonic()
        self.assertTrue(t1-t0, 0.01)
        # TODO: Test with timeout.

    def testSleep(self):
        @tasks.coroutine
        def sleeper(dt, arg):
            yield from tasks.sleep(dt/2)
            res = yield from tasks.sleep(dt/2, arg)
            return res
        t = tasks.Task(sleeper(0.1, 'yeah'))
        t0 = time.monotonic()
        self.event_loop.run()
        t1 = time.monotonic()
        self.assertTrue(t1-t0 >= 0.09)
        self.assertTrue(t.done())
        self.assertEqual(t.result(), 'yeah')


if __name__ == '__main__':
    unittest.main()
