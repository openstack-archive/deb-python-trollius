from trollius import subprocess
from trollius import test_utils
import trollius as asyncio
import os
import signal
import sys
import unittest
from trollius import From, Return
from trollius import test_support as support
if sys.platform != 'win32':
    from trollius import unix_events
from trollius.py33_exceptions import BrokenPipeError

# Program blocking
PROGRAM_BLOCKED = [sys.executable, '-c', 'import time; time.sleep(3600)']

# Program copying input to output
if sys.version_info >= (3,):
    PROGRAM_CAT = ';'.join(('import sys',
                            'data = sys.stdin.buffer.read()',
                            'sys.stdout.buffer.write(data)'))
else:
    PROGRAM_CAT = ';'.join(('import sys',
                            'data = sys.stdin.read()',
                            'sys.stdout.write(data)'))
PROGRAM_CAT = [sys.executable, '-c', PROGRAM_CAT]

class SubprocessMixin(object):

    def test_stdin_stdout(self):
        args = PROGRAM_CAT

        @asyncio.coroutine
        def run(data):
            proc = yield From(asyncio.create_subprocess_exec(
                                     *args,
                                     stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     loop=self.loop))

            # feed data
            proc.stdin.write(data)
            yield From(proc.stdin.drain())
            proc.stdin.close()

            # get output and exitcode
            data = yield From(proc.stdout.read())
            exitcode = yield From(proc.wait())
            raise Return(exitcode, data)

        task = run(b'some data')
        task = asyncio.wait_for(task, 10.0, loop=self.loop)
        exitcode, stdout = self.loop.run_until_complete(task)
        self.assertEqual(exitcode, 0)
        self.assertEqual(stdout, b'some data')

    def test_communicate(self):
        args = PROGRAM_CAT

        @asyncio.coroutine
        def run(data):
            proc = yield From(asyncio.create_subprocess_exec(
                                          *args,
                                          stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE,
                                          loop=self.loop))
            stdout, stderr = yield From(proc.communicate(data))
            raise Return(proc.returncode, stdout)

        task = run(b'some data')
        task = asyncio.wait_for(task, 10.0, loop=self.loop)
        exitcode, stdout = self.loop.run_until_complete(task)
        self.assertEqual(exitcode, 0)
        self.assertEqual(stdout, b'some data')

    def test_shell(self):
        create = asyncio.create_subprocess_shell('exit 7',
                                                 loop=self.loop)
        proc = self.loop.run_until_complete(create)
        exitcode = self.loop.run_until_complete(proc.wait())
        self.assertEqual(exitcode, 7)

    @test_utils.skipUnless(hasattr(os, 'setsid'), "need os.setsid()")
    def test_start_new_session(self):
        def start_new_session():
            os.setsid()

        # start the new process in a new session
        create = asyncio.create_subprocess_shell('exit 8',
                                                 preexec_fn=start_new_session,
                                                 loop=self.loop)
        proc = self.loop.run_until_complete(create)
        exitcode = self.loop.run_until_complete(proc.wait())
        self.assertEqual(exitcode, 8)

    def test_kill(self):
        args = PROGRAM_BLOCKED
        create = asyncio.create_subprocess_exec(*args, loop=self.loop)
        proc = self.loop.run_until_complete(create)
        proc.kill()
        returncode = self.loop.run_until_complete(proc.wait())
        if sys.platform == 'win32':
            self.assertIsInstance(returncode, int)
            # expect 1 but sometimes get 0
        else:
            self.assertEqual(-signal.SIGKILL, returncode)

    def test_terminate(self):
        args = PROGRAM_BLOCKED
        create = asyncio.create_subprocess_exec(*args, loop=self.loop)
        proc = self.loop.run_until_complete(create)
        proc.terminate()
        returncode = self.loop.run_until_complete(proc.wait())
        if sys.platform == 'win32':
            self.assertIsInstance(returncode, int)
            # expect 1 but sometimes get 0
        else:
            self.assertEqual(-signal.SIGTERM, returncode)

    @test_utils.skipIf(sys.platform == 'win32', "Don't have SIGHUP")
    def test_send_signal(self):
        code = 'import time; print("sleeping", flush=True); time.sleep(3600)'
        args = [sys.executable, '-c', code]
        create = asyncio.create_subprocess_exec(*args, loop=self.loop, stdout=subprocess.PIPE)
        proc = self.loop.run_until_complete(create)

        @asyncio.coroutine
        def send_signal(proc):
            # basic synchronization to wait until the program is sleeping
            line = yield From(proc.stdout.readline())
            self.assertEqual(line, b'sleeping\n')

            proc.send_signal(signal.SIGHUP)
            returncode = yield From(proc.wait())
            raise Return(returncode)

        returncode = self.loop.run_until_complete(send_signal(proc))
        self.assertEqual(-signal.SIGHUP, returncode)

    def prepare_broken_pipe_test(self):
        # buffer large enough to feed the whole pipe buffer
        large_data = b'x' * support.PIPE_MAX_SIZE

        # the program ends before the stdin can be feeded
        create = asyncio.create_subprocess_exec(
                             sys.executable, '-c', 'pass',
                             stdin=subprocess.PIPE,
                             loop=self.loop)
        proc = self.loop.run_until_complete(create)
        return (proc, large_data)

    def test_stdin_broken_pipe(self):
        proc, large_data = self.prepare_broken_pipe_test()

        # drain() must raise BrokenPipeError or ConnectionResetError
        proc.stdin.write(large_data)
        self.assertRaises((BrokenPipeError, ConnectionResetError),
                          self.loop.run_until_complete, proc.stdin.drain())
        self.loop.run_until_complete(proc.wait())

    def test_communicate_ignore_broken_pipe(self):
        proc, large_data = self.prepare_broken_pipe_test()

        # communicate() must ignore BrokenPipeError when feeding stdin
        self.loop.run_until_complete(proc.communicate(large_data))
        self.loop.run_until_complete(proc.wait())


if sys.platform != 'win32':
    # Unix
    class SubprocessWatcherMixin(SubprocessMixin):

        Watcher = None

        def setUp(self):
            policy = asyncio.get_event_loop_policy()
            self.loop = policy.new_event_loop()

            # ensure that the event loop is passed explicitly in asyncio
            policy.set_event_loop(None)

            watcher = self.Watcher()
            watcher.attach_loop(self.loop)
            policy.set_child_watcher(watcher)

        def tearDown(self):
            policy = asyncio.get_event_loop_policy()
            policy.set_child_watcher(None)
            self.loop.close()
            super(SubprocessWatcherMixin, self).tearDown()

    class SubprocessSafeWatcherTests(SubprocessWatcherMixin,
                                     test_utils.TestCase):

        Watcher = unix_events.SafeChildWatcher

    class SubprocessFastWatcherTests(SubprocessWatcherMixin,
                                     test_utils.TestCase):

        Watcher = unix_events.FastChildWatcher

else:
    # Windows
    class SubprocessProactorTests(SubprocessMixin, test_utils.TestCase):

        def setUp(self):
            policy = asyncio.get_event_loop_policy()
            self.loop = asyncio.ProactorEventLoop()

            # ensure that the event loop is passed explicitly in asyncio
            policy.set_event_loop(None)

        def tearDown(self):
            policy = asyncio.get_event_loop_policy()
            self.loop.close()
            policy.set_event_loop(None)
            super(SubprocessProactorTests, self).tearDown()


if __name__ == '__main__':
    unittest.main()
