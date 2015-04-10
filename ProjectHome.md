The Tulip project is the [asyncio module](https://docs.python.org/dev/library/asyncio.html) for Python 3.3. Since Python 3.4, asyncio is now part of the standard library.

Help:

  * [asyncio documentation](https://docs.python.org/dev/library/asyncio.html)
  * [asyncio examples](https://code.google.com/p/tulip/source/browse/#hg%2Fexamples)
  * Mailing list: [python-tulip Google Group](https://groups.google.com/forum/?fromgroups#!forum/python-tulip)
  * IRC: `#asyncio` channel on the [Freenode network](https://freenode.net/)

Pages:

  * [Contributing](Contributing.md): To contribute.
  * [ThirdParty](ThirdParty.md): A list of 3rd party integrations with asyncio.
  * [Benchmarks](Benchmarks.md): asyncio benchmarks

The asyncio module provides infrastructure for writing single-threaded concurrent code using coroutines, multiplexing I/O access over sockets and other resources, running network clients and servers, and other related primitives. Here is a more detailed list of the package contents:

  * a pluggable event loop with various system-specific implementations;
  * transport and protocol abstractions (similar to those in [Twisted](https://twistedmatrix.com/trac/));
  * concrete support for TCP, UDP, SSL, subprocess pipes, delayed calls, and others (some may be system-dependent);
  * a Future class that mimics the one in the concurrent.futures module, but adapted for use with the event loop;
  * coroutines and tasks based on ```yield from``` (PEP 380), to help write concurrent code in a sequential fashion;
  * cancellation support for Futures and coroutines;
  * synchronization primitives for use between coroutines in a single thread, mimicking those in the threading module;
  * an interface for passing work off to a threadpool, for times when you absolutely, positively have to use a library that makes blocking I/O calls.

Hello World using an asyncio coroutine:

```
import asyncio

@asyncio.coroutine
def hello_world():
    print("Hello World!")

loop = asyncio.get_event_loop()
loop.run_until_complete(hello_world())
loop.close()
```

For asyncion on Python 2, see the [trollius project](http://trollius.readthedocs.org/).