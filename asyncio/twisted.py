'''
Experimental Twisted event loop for Trollius.

To test it:

    import asyncio
    from asyncio.twisted import TwistedEventLoop
    asyncio.set_event_loop(TwistedEventLoop())

FIXME: handle errors :-)
FIXME: implement sockets
FIXME: implement subprocess and pipes
FIXME: add deferToThread() executor?
FIXME: etc.
'''
from __future__ import absolute_import
import asyncio
import asyncio.events
import asyncio.base_events
import signal
from twisted.internet import reactor
from twisted.internet.defer import Deferred, succeed

def _defer_wrapper(result, callback, args):
    callback(*args)

def _reactor_stop(future):
    reactor.stop()

class TwistedEventLoop(asyncio.AbstractEventLoop):
    def _call_later(self, delay, callback, args, threadsafe):
        defer = Deferred()
        defer.addCallback(_defer_wrapper, callback, args)
        if threadsafe:
            reactor.callFromThread(reactor.callLater,
                                   delay, defer.callback, None)
        else:
            reactor.callLater(delay, defer.callback, None)

        # FIXME: link to the real callback
        handle = asyncio.events.make_handle(str, 1)
        return handle

    def call_later(self, delay, callback, *args):
        return self._call_later(delay, callback, args, False)

    def call_soon_threadsafe(self, callback, *args):
        return self._call_later(0, callback, args, True)

    def add_signal_handler(self, signum, callback, *args):
        def signal_wrapper(signum, frame):
            reactor.callFromThread(callback, *args)
            signal.signal(signum, old)
        old = signal.getsignal(signum)
        signal.signal(signum, signal_wrapper)
        # FIXME: signal.siginterrupt(signum, False)?

    def run_until_complete(self, future):
        """Run until the Future is done.

        If the argument is a coroutine, it is wrapped in a Task.

        XXX TBD: It would be disastrous to call run_until_complete()
        with the same coroutine twice -- it would wrap it in two
        different Tasks and that can't be good.

        Return the Future's result, or raise its exception.
        """
        future = asyncio.async(future, loop=self)
        future.add_done_callback(_reactor_stop)
        self.run_forever()
        future.remove_done_callback(_reactor_stop)
        if not future.done():
            raise RuntimeError('Event loop stopped before Future completed.')

        return future.result()

    def run_forever(self):
        # FIXME: install default handler for CTRL+c ?
        #reactor.run(installSignalHandlers=0)
        reactor.run()

    def stop(self):
        reactor.stop()

