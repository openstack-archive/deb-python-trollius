"""Tests for streams.py."""

import unittest

from tulip import events
from tulip import streams
from tulip import tasks
from tulip import test_utils


class StreamReaderTests(test_utils.LogTrackingTestCase):

    DATA = b'line1\nline2\nline3\n'

    def setUp(self):
        super().setUp()
        self.event_loop = events.new_event_loop()
        events.set_event_loop(self.event_loop)

    def tearDown(self):
        super().tearDown()
        self.event_loop.close()

    def test_feed_empty_data(self):
        stream = streams.StreamReader()

        stream.feed_data(b'')
        self.assertEqual(0, stream.line_count)
        self.assertEqual(0, stream.byte_count)

    def test_feed_data_line_byte_count(self):
        stream = streams.StreamReader()

        stream.feed_data(self.DATA)
        self.assertEqual(self.DATA.count(b'\n'), stream.line_count)
        self.assertEqual(len(self.DATA), stream.byte_count)

    def test_read_zero(self):
        """Read zero bytes."""
        stream = streams.StreamReader()
        stream.feed_data(self.DATA)

        read_task = tasks.Task(stream.read(0))
        data = self.event_loop.run_until_complete(read_task)
        self.assertEqual(b'', data)
        self.assertEqual(len(self.DATA), stream.byte_count)
        self.assertEqual(self.DATA.count(b'\n'), stream.line_count)

    def test_read(self):
        """Read bytes."""
        stream = streams.StreamReader()
        read_task = tasks.Task(stream.read(30))

        def cb():
            stream.feed_data(self.DATA)
        self.event_loop.call_soon(cb)

        data = self.event_loop.run_until_complete(read_task)
        self.assertEqual(self.DATA, data)
        self.assertFalse(stream.byte_count)
        self.assertFalse(stream.line_count)

    def test_read_line_breaks(self):
        """Read bytes without line breaks."""
        stream = streams.StreamReader()
        stream.feed_data(b'line1')
        stream.feed_data(b'line2')

        read_task = tasks.Task(stream.read(5))
        data = self.event_loop.run_until_complete(read_task)

        self.assertEqual(b'line1', data)
        self.assertEqual(5, stream.byte_count)
        self.assertFalse(stream.line_count)

    def test_read_eof(self):
        """Read bytes, stop at eof."""
        stream = streams.StreamReader()
        read_task = tasks.Task(stream.read(1024))

        def cb():
            stream.feed_eof()
        self.event_loop.call_soon(cb)

        data = self.event_loop.run_until_complete(read_task)
        self.assertEqual(b'', data)
        self.assertFalse(stream.byte_count)
        self.assertFalse(stream.line_count)

    def test_read_until_eof(self):
        """Read all bytes until eof."""
        stream = streams.StreamReader()
        read_task = tasks.Task(stream.read(-1))

        def cb():
            stream.feed_data(b'chunk1\n')
            stream.feed_data(b'chunk2')
            stream.feed_eof()
        self.event_loop.call_soon(cb)

        data = self.event_loop.run_until_complete(read_task)

        self.assertEqual(b'chunk1\nchunk2', data)
        self.assertFalse(stream.byte_count)
        self.assertFalse(stream.line_count)

    def test_readline(self):
        """Read one line."""
        stream = streams.StreamReader()
        stream.feed_data(b'chunk1 ')
        read_task = tasks.Task(stream.readline())

        def cb():
            stream.feed_data(b'chunk2 ')
            stream.feed_data(b'chunk3 ')
            stream.feed_data(b'\n chunk4')
        self.event_loop.call_soon(cb)

        line = self.event_loop.run_until_complete(read_task)
        self.assertEqual(b'chunk1 chunk2 chunk3 \n', line)
        self.assertFalse(stream.line_count)
        self.assertEqual(len(b'\n chunk4')-1, stream.byte_count)

    def test_readline_limit_with_existing_data(self):
        self.suppress_log_errors()

        stream = streams.StreamReader(3)
        stream.feed_data(b'li')
        stream.feed_data(b'ne1\nline2\n')

        read_task = tasks.Task(stream.readline())
        self.assertRaises(
            ValueError, self.event_loop.run_until_complete, read_task)
        self.assertEqual([b'line2\n'], list(stream.buffer))

        stream = streams.StreamReader(3)
        stream.feed_data(b'li')
        stream.feed_data(b'ne1')
        stream.feed_data(b'li')

        read_task = tasks.Task(stream.readline())
        self.assertRaises(
            ValueError, self.event_loop.run_until_complete, read_task)
        self.assertEqual([b'li'], list(stream.buffer))
        self.assertEqual(2, stream.byte_count)

    def test_readline_limit(self):
        self.suppress_log_errors()

        stream = streams.StreamReader(7)

        def cb():
            stream.feed_data(b'chunk1')
            stream.feed_data(b'chunk2')
            stream.feed_data(b'chunk3\n')
            stream.feed_eof()
        self.event_loop.call_soon(cb)

        read_task = tasks.Task(stream.readline())
        self.assertRaises(
            ValueError, self.event_loop.run_until_complete, read_task)
        self.assertEqual([b'chunk3\n'], list(stream.buffer))
        self.assertEqual(7, stream.byte_count)

    def test_readline_line_byte_count(self):
        stream = streams.StreamReader()
        stream.feed_data(self.DATA[:6])
        stream.feed_data(self.DATA[6:])

        read_task = tasks.Task(stream.readline())
        line = self.event_loop.run_until_complete(read_task)

        self.assertEqual(b'line1\n', line)
        self.assertEqual(self.DATA.count(b'\n')-1, stream.line_count)
        self.assertEqual(len(self.DATA) - len(b'line1\n'), stream.byte_count)

    def test_readline_eof(self):
        stream = streams.StreamReader()
        stream.feed_data(b'some data')
        stream.feed_eof()

        read_task = tasks.Task(stream.readline())
        line = self.event_loop.run_until_complete(read_task)

        self.assertEqual(b'some data', line)

    def test_readline_empty_eof(self):
        stream = streams.StreamReader()
        stream.feed_eof()

        read_task = tasks.Task(stream.readline())
        line = self.event_loop.run_until_complete(read_task)

        self.assertEqual(b'', line)

    def test_readline_read_byte_count(self):
        stream = streams.StreamReader()
        stream.feed_data(self.DATA)

        read_task = tasks.Task(stream.readline())
        line = self.event_loop.run_until_complete(read_task)

        read_task = tasks.Task(stream.read(7))
        data = self.event_loop.run_until_complete(read_task)

        self.assertEqual(b'line2\nl', data)
        self.assertEqual(
            1, stream.line_count)
        self.assertEqual(
            len(self.DATA) - len(b'line1\n') - len(b'line2\nl'),
            stream.byte_count)

    def test_readexactly_zero_or_less(self):
        """Read exact number of bytes (zero or less)."""
        stream = streams.StreamReader()
        stream.feed_data(self.DATA)

        read_task = tasks.Task(stream.readexactly(0))
        data = self.event_loop.run_until_complete(read_task)
        self.assertEqual(b'', data)
        self.assertEqual(len(self.DATA), stream.byte_count)
        self.assertEqual(self.DATA.count(b'\n'), stream.line_count)

        read_task = tasks.Task(stream.readexactly(-1))
        data = self.event_loop.run_until_complete(read_task)
        self.assertEqual(b'', data)
        self.assertEqual(len(self.DATA), stream.byte_count)
        self.assertEqual(self.DATA.count(b'\n'), stream.line_count)

    def test_readexactly(self):
        """Read exact number of bytes."""
        stream = streams.StreamReader()

        n = 2 * len(self.DATA)
        read_task = tasks.Task(stream.readexactly(n))

        def cb():
            stream.feed_data(self.DATA)
            stream.feed_data(self.DATA)
            stream.feed_data(self.DATA)
        self.event_loop.call_soon(cb)

        data = self.event_loop.run_until_complete(read_task)
        self.assertEqual(self.DATA + self.DATA, data)
        self.assertEqual(len(self.DATA), stream.byte_count)
        self.assertEqual(self.DATA.count(b'\n'), stream.line_count)

    def test_readexactly_eof(self):
        """Read exact number of bytes (eof)."""
        stream = streams.StreamReader()
        n = 2 * len(self.DATA)
        read_task = tasks.Task(stream.readexactly(n))

        def cb():
            stream.feed_data(self.DATA)
            stream.feed_eof()
        self.event_loop.call_soon(cb)

        data = self.event_loop.run_until_complete(read_task)
        self.assertEqual(self.DATA, data)
        self.assertFalse(stream.byte_count)
        self.assertFalse(stream.line_count)


if __name__ == '__main__':
    unittest.main()
