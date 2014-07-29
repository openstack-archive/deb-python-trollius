++++++++++
Change log
++++++++++

Version 1.0.1 (development version)
===================================

This release supports PyPy and has a better support of asyncio coroutines,
especially in debug mode.

Changes:

* Tulip issue #198: asyncio.Condition now accepts an optional lock object.
* Enhance representation of Future and Future subclasses: add "created at".

Bugfixes:

* Fix Trollius issue #9: @trollius.coroutine now works on callbable objects
  (without ``__name__`` attribute), not only on functions.
* Fix Trollius issue #13: asyncio futures are now accepted in all functions:
  as_completed(), async(), @coroutine, gather(), run_until_complete(),
  wrap_future().
* Fix support of asyncio coroutines in debug mode. If the last instruction
  of the coroutine is "yield from", it's an asyncio coroutine and it does not
  need to use From().
* Fix and enhance _WaitHandleFuture.cancel():

  - Tulip issue #195: Fix a crash on Windows: don't call UnregisterWait() twice
    if a _WaitHandleFuture is cancelled twice.
  - Fix _WaitHandleFuture.cancel(): return the result of the parent cancel()
    method (True or False).
  - _WaitHandleFuture.cancel() now notify IocpProactor through the overlapped
    object that the wait was cancelled.

* Tulip issue #196: _OverlappedFuture now clears its reference to the
  overlapped object. IocpProactor keeps a reference to the overlapped object
  until it is notified of its completion. Log also an error in debug mode if it
  gets unexpected notifications.
* Fix runtest.py to be able to log at level DEBUG.

Other changes:

* BaseSelectorEventLoop._write_to_self() now logs errors in debug mode.
* Fix as_completed(): it's not a coroutine, don't use ``yield From(...)`` but
  ``yield ...``
* Tulip issue #193: Convert StreamWriter.drain() to a classic coroutine.
* Tulip issue #194: Don't use sys.getrefcount() in unit tests: the full test
  suite now pass on PyPy.


2014-07-21: Version 1.0
=======================

Major Changes
-------------

* Event loops have a new ``create_task()`` method, which is now the recommanded
  way to create a task object. This method can be overriden by third-party
  event loops to use their own task class.
* The debug mode has been improved a lot. Set ``TROLLIUSDEBUG`` envrironment
  variable to ``1`` and configure logging to log at level ``logging.DEBUG``
  (ex: ``logging.basicConfig(level=logging.DEBUG)``).  Changes:

  - much better representation of Trollius objects (ex: ``repr(task)``):
    unified ``<Class arg1 arg2 ...>`` format, use qualified name when available
  - show the traceback where objects were created
  - show the current filename and line number for coroutine
  - show the filename and line number where objects were created
  - log most important socket events
  - log most important subprocess events

* ``Handle.cancel()`` now clears references to callback and args
* Log an error if a Task is destroyed while it is still pending, but only on
  Python 3.4 and newer.
* Fix for asyncio coroutines when passing tuple value in debug mode.
  ``CoroWrapper.send()`` now checks if it is called from a "yield from"
  generator to decide if the parameter should be unpacked or not.
* ``Process.communicate()`` now ignores ``BrokenPipeError`` and
  ``ConnectionResetError`` exceptions.
* Rewrite signal handling on Python 3.3 and newer to fix a race condition: use
  the "self-pipe" to get signal numbers.


Other Changes
-------------

* Fix ``ProactorEventLoop()`` in debug mode
* Fix a race condition when setting the result of a Future with
  ``call_soon()``. Add an helper, a private method, to set the result only if
  the future was not cancelled.
* Fix ``asyncio.__all__``: export also ``unix_events`` and ``windows_events``
  symbols. For example, on Windows, it was not possible to get
  ``ProactorEventLoop`` or ``DefaultEventLoopPolicy`` using ``from asyncio
  import *``.
* ``Handle.cancel()`` now clears references to callback and args
* Make Server attributes and methods private, the sockets attribute remains
  public.
* BaseEventLoop.create_datagram_endpoint() now waits until
  protocol.connection_made() has been called. Document also why transport
  constructors use a waiter.
* _UnixSubprocessTransport: fix file mode of stdin: open stdin in write mode,
  not in read mode.


2014-06-23: version 0.4
=======================

Changes between Trollius 0.3 and 0.4:

* Trollius event loop now supports asyncio coroutines:

  - Trollius coroutines can yield asyncio coroutines,
  - asyncio coroutines can yield Trollius coroutines,
  - asyncio.set_event_loop() accepts a Trollius event loop,
  - asyncio.set_event_loop_policy() accepts a Trollius event loop policy.

* The ``PYTHONASYNCIODEBUG`` envrionment variable has been renamed to
  ``TROLLIUSDEBUG``. The environment variable is now used even if the Python
  command line option ``-E`` is used.
* Synchronize with Tulip.
* Support PyPy (fix subproces, fix unit tests).

Tulip changes:

* Tulip issue #171: BaseEventLoop.close() now raises an exception if the event
  loop is running. You must first stop the event loop and then wait until it
  stopped, before closing it.
* Tulip issue #172: only log selector timing in debug mode
* Enable the debug mode of event loops when the ``TROLLIUSDEBUG`` environment
  variable is set
* BaseEventLoop._assert_is_current_event_loop() now only raises an exception if
  the current loop is set.
* Tulip issue #105: in debug mode, log callbacks taking more than 100 ms to be
  executed.
* Python issue 21595: ``BaseSelectorEventLoop._read_from_self()`` reads all
  available bytes from the "self pipe", not only a single byte. This change
  reduces the risk of having the pipe full and so getting the "BlockingIOError:
  [Errno 11] Resource temporarily unavailable" message.
* Python issue 21723: asyncio.Queue: support any type of number (ex: float) for
  the maximum size. Patch written by Vajrasky Kok.
* Issue #173: Enhance repr(Handle) and repr(Task): add the filename and line
  number, when available. For task, the current line number of the coroutine
  is used.
* Add BaseEventLoop.is_closed() method. run_forever() and run_until_complete()
  methods now raises an exception if the event loop was closed.
* Make sure that socketpair() close sockets on error. Close the listening
  socket if sock.bind() raises an exception.
* Fix ResourceWarning: close sockets on errors.
  BaseEventLoop.create_connection(), BaseEventLoop.create_datagram_endpoint()
  and _UnixSelectorEventLoop.create_unix_server() now close the newly created
  socket on error.
* Rephrase and fix docstrings.
* Fix tests on Windows: wait for the subprocess exit. Before, regrtest failed
  to remove the temporary test directory because the process was still running
  in this directory.
* Refactor unit tests.

On Python 3.5, generators now get their name from the function, no more from
the code. So the ``@coroutine`` decorator doesn't loose the original name of
the function anymore.


2014-05-26: version 0.3
=======================

Rename the Python module ``asyncio`` to ``trollius`` to support Python 3.4. On
Python 3.4, there is already a module called ``asyncio`` in the standard
library which conflicted with ``asyncio`` module of Trollius 0.2. To write
asyncio code working on Trollius and Tulip, use ``import trollius as asyncio``.

Changes between Trollius 0.2 and 0.3:

* Synchronize with Tulip 3.4.1.
* Enhance Trollius documentation.
* Trollius issue #7: Fix ``asyncio.time_monotonic`` on Windows older than
  Vista (ex: Windows 2000 and Windows XP).
* Fedora packages have been accepted.

Changes between Tulip 3.4.0 and 3.4.1:

* Pull in Solaris ``devpoll`` support by Giampaolo Rodola
  (``trollius.selectors`` module).
* Add options ``-r`` and ``--randomize`` to runtests.py to randomize test
  order.
* Add a simple echo client/server example.
* Tulip issue #166: Add ``__weakref__`` slots to ``Handle`` and
  ``CoroWrapper``.
* ``EventLoop.create_unix_server()`` now raises a ``ValueError`` if path and
  sock are specified at the same time.
* Ensure ``call_soon()``, ``call_later()`` and ``call_at()`` are invoked on
  current loop in debug mode. Raise a ``RuntimeError`` if the event loop of the
  current thread is different.  The check should help to debug thread-safetly
  issue. Patch written by David Foster.
* Tulip issue #157: Improve test_events.py, avoid ``run_briefly()`` which is
  not reliable.
* Reject add/remove reader/writer when event loop is closed.

Bugfixes of Tulip 3.4.1:

* Tulip issue #168: ``StreamReader.read(-1)`` from pipe may hang if
  data exceeds buffer limit.
* CPython issue #21447: Fix a race condition in
  ``BaseEventLoop._write_to_self()``.
* Different bugfixes in ``CoroWrapper`` of ``trollius.coroutines``, class used
  when running Trollius in debug mode:

  - Fix ``CoroWrapper`` to workaround yield-from bug in CPython 3.4.0. The
    CPython bug is now fixed in CPython 3.4.1 and 3.5.
  - Make sure ``CoroWrapper.send`` proxies one argument correctly.
  - CPython issue #21340: Be careful accessing instance variables in ``__del__``.
  - Tulip issue #163: Add ``gi_{frame,running,code}`` properties to
    ``CoroWrapper``.

* Fix ``ResourceWarning`` warnings
* Tulip issue #159: Fix ``windows_utils.socketpair()``. Use ``"127.0.0.1"``
  (IPv4) or ``"::1"`` (IPv6) host instead of ``"localhost"``, because
  ``"localhost"`` may be a different IP address. Reject also invalid arguments:
  only ``AF_INET`` and ``AF_INET6`` with ``SOCK_STREAM`` (and ``proto=0``) are
  supported.
* Tulip issue #158: ``Task._step()`` now also sets ``self`` to ``None`` if an
  exception is raised. ``self`` is set to ``None`` to break a reference cycle.


2014-03-04: version 0.2
=======================

Trollius now uses ``yield From(...)`` syntax which looks close to Tulip ``yield
from ...`` and allows to port more easily Trollius code to Tulip. The usage of
``From()`` is not mandatory yet, but it may become mandatory in a future
version.  However, if ``yield`` is used without ``From``, an exception is
raised if the event loop is running in debug mode.

Major changes:

* Replace ``yield ...`` syntax with ``yield From(...)``
* On Python 2, Future.set_exception() now only saves the traceback if the debug
  mode of the event loop is enabled for best performances in production mode.
  Use ``loop.set_debug(True)`` to save the traceback.

Bugfixes:

* Fix ``BaseEventLoop.default_exception_handler()`` on Python 2: get the
  traceback from ``sys.exc_info()``
* Fix unit tests on SSL sockets on Python older than 2.6.6. Example:
  Mac OS 10.6 with Python 2.6.1 or OpenIndiana 148 with Python 2.6.4.
* Fix error handling in the asyncio.time_monotonic module
* Fix acquire() method of Lock, Condition and Semaphore: don't return a context
  manager but True, as Tulip. Task._step() now does the trick.

Other changes:

* tox.ini: set PYTHONASYNCIODEBUG to 1 to run tests

2014-02-25: version 0.1.6
=========================

Trollius changes:

* Add a new Sphinx documentation:
  http://trollius.readthedocs.org/
* tox: pass posargs to nosetests. Patch contributed by Ian Wienand.
* Fix support of Python 3.2 and add py32 to tox.ini
* Merge with Tulip 0.4.1

Major changes of Tulip 0.4.1:

* Issue #81: Add support for UNIX Domain Sockets. New APIs:

  - loop.create_unix_connection()
  - loop.create_unix_server()
  - streams.open_unix_connection()
  - streams.start_unix_server()

* Issue #80: Add new event loop exception handling API. New APIs:

  - loop.set_exception_handler()
  - loop.call_exception_handler()
  - loop.default_exception_handler()

* Issue #136: Add get_debug() and set_debug() methods to BaseEventLoopTests.
  Add also a ``PYTHONASYNCIODEBUG`` environment variable to debug coroutines
  since Python startup, to be able to debug coroutines defined directly in the
  asyncio module.

Other changes of Tulip 0.4.1:

* asyncio.subprocess: Fix a race condition in communicate()
* Fix _ProactorWritePipeTransport._pipe_closed()
* Issue #139: Improve error messages on "fatal errors".
* Issue #140: WriteTransport.set_write_buffer_size() to call
  _maybe_pause_protocol()
* Issue #129: BaseEventLoop.sock_connect() now raises an error if the address
  is not resolved (hostname instead of an IP address) for AF_INET and
  AF_INET6 address families.
* Issue #131: as_completed() and wait() now raises a TypeError if the list of
  futures is not a list but a Future, Task or coroutine object
* Python issue #20495: Skip test_read_pty_output() of test_asyncio on FreeBSD
  older than FreeBSD 8
* Issue #130: Add more checks on subprocess_exec/subprocess_shell parameters
* Issue #126: call_soon(), call_soon_threadsafe(), call_later(), call_at()
  and run_in_executor() now raise a TypeError if the callback is a coroutine
  function.
* Python issue #20505: BaseEventLoop uses again the resolution of the clock
  to decide if scheduled tasks should be executed or not.


2014-02-10: version 0.1.5
=========================

- Merge with Tulip 0.3.1:

  * New asyncio.subprocess module
  * _UnixWritePipeTransport now also supports character devices, as
    _UnixReadPipeTransport. Patch written by Jonathan Slenders.
  * StreamReader.readexactly() now raises an IncompleteReadError if the
    end of stream is reached before we received enough bytes, instead of
    returning less bytes than requested.
  * poll and epoll selectors now round the timeout away from zero (instead of
    rounding towards zero) to fix a performance issue
  * asyncio.queue: Empty renamed to QueueEmpty, Full to QueueFull
  * _fatal_error() of _UnixWritePipeTransport and _ProactorBasePipeTransport
    don't log BrokenPipeError nor ConnectionResetError
  * Future.set_exception(exc) now instanciate exc if it is a class
  * streams.StreamReader: Use bytearray instead of deque of bytes for internal
    buffer

- Fix test_wait_for() unit test

2014-01-22: version 0.1.4
=========================

- The project moved to https://bitbucket.org/enovance/trollius
- Fix CoroWrapper (_DEBUG=True): add missing import
- Emit a warning when Return is not raised
- Merge with Tulip to get latest Tulip bugfixes
- Fix dependencies in tox.ini for the different Python versions

2014-01-13: version 0.1.3
=========================

- Workaround bugs in the ssl module of Python older than 2.6.6. For example,
  Mac OS 10.6 (Snow Leopard) uses Python 2.6.1.
- ``return x, y`` is now written ``raise Return(x, y)`` instead of
  ``raise Return((x, y))``
- Support "with (yield lock):" syntax for Lock, Condition and Semaphore
- SSL support is now optional: don't fail if the ssl module is missing
- Add tox.ini, tool to run unit tests. For example, "tox -e py27" creates a
  virtual environment to run tests with Python 2.7.

2014-01-08: version 0.1.2
=========================

- Trollius now supports CPython 2.6-3.4, PyPy and Windows. All unit tests
  pass with CPython 2.7 on Linux.
- Fix Windows support. Fix compilation of the _overlapped module and add a
  asyncio._winapi module (written in pure Python). Patch written by Marc
  Schlaich.
- Support Python 2.6: require an extra dependency,
  ordereddict (and unittest2 for unit tests)
- Support Python 3.2, 3.3 and 3.4
- Support PyPy 2.2
- Don't modify __builtins__ nor the ssl module to inject backported exceptions
  like BlockingIOError or SSLWantReadError. Exceptions are available in the
  asyncio module, ex: asyncio.BlockingIOError.

2014-01-06: version 0.1.1
=========================

- Fix asyncio.time_monotonic on Mac OS X
- Fix create_connection(ssl=True)
- Don't export backported SSLContext in the ssl module anymore to not confuse
  libraries testing hasattr(ssl, "SSLContext")
- Relax dependency on the backported concurrent.futures module: use a
  synchronous executor if the module is missing

2014-01-04: version 0.1
=======================

- First public release

