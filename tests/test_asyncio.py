from trollius import test_utils
from trollius import From, Return
import trollius
import unittest

try:
    import asyncio
except ImportError:
    from trollius.test_utils import SkipTest
    raise SkipTest('need asyncio')


# "yield from" syntax cannot be used directly, because Python 2 should be able
# to execute this file (to raise SkipTest)
code = '''
@asyncio.coroutine
def asyncio_noop(value):
    yield from []
    return (value,)

@asyncio.coroutine
def asyncio_coroutine(coro, value):
    res = yield from coro
    return res + (value,)
'''
exec(code)

@trollius.coroutine
def trollius_noop(value):
    yield From(None)
    raise Return((value,))

@trollius.coroutine
def trollius_coroutine(coro, value):
    res = yield trollius.From(coro)
    raise trollius.Return(res + (value,))


class AsyncioTests(test_utils.TestCase):
    def setUp(self):
        policy = trollius.get_event_loop_policy()
        self.loop = policy.new_event_loop()
        self.set_event_loop(self.loop)

        asyncio_policy = asyncio.get_event_loop_policy()
        self.addCleanup(asyncio.set_event_loop_policy, asyncio_policy)
        asyncio.set_event_loop_policy(policy)

    def test_policy(self):
        trollius.set_event_loop(self.loop)
        self.assertIs(asyncio.get_event_loop(), self.loop)

    def test_asyncio(self):
        coro = asyncio_noop("asyncio")
        res = self.loop.run_until_complete(coro)
        self.assertEqual(res, ("asyncio",))

    def test_asyncio_in_trollius(self):
        coro1 = asyncio_noop(1)
        coro2 = asyncio_coroutine(coro1, 2)
        res = self.loop.run_until_complete(trollius_coroutine(coro2, 3))
        self.assertEqual(res, (1, 2, 3))

    def test_trollius_in_asyncio(self):
        coro1 = trollius_noop(4)
        coro2 = trollius_coroutine(coro1, 5)
        res = self.loop.run_until_complete(asyncio_coroutine(coro2, 6))
        self.assertEqual(res, (4, 5, 6))


if __name__ == '__main__':
    unittest.main()
