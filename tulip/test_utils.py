"""Utilities shared by tests."""

import functools
import logging
import unittest

from . import events

def sync(gen):
    @functools.wraps(gen)
    def wrapper(*args, **kw):
        return events.get_event_loop().run_until_complete(
            tasks.Task(gen(*args, **kw)))

    return wrapper


class LogTrackingTestCase(unittest.TestCase):

    def setUp(self):
        self._logger = logging.getLogger()
        self._log_level = self._logger.getEffectiveLevel()

    def tearDown(self):
        self._logger.setLevel(self._log_level)

    def suppress_log_errors(self):
        if self._log_level >= logging.WARNING:
            self._logger.setLevel(logging.CRITICAL)

    def suppress_log_warnings(self):
        if self._log_level >= logging.WARNING:
            self._logger.setLevel(logging.ERROR)
