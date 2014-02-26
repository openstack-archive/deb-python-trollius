Trollius
========

Trollius is a portage of the Tulip project (asyncio module, PEP 3156) on Python
2. Trollius works on Python 2.6-3.4. It has been tested on Windows, Linux,
Mac OS X, FreeBSD and OpenIndiana.

* Website: https://bitbucket.org/enovance/trollius
* Documentation: http://trollius.readthedocs.org/
* Tulip project: http://code.google.com/p/tulip/
* `Trollius project in the Python Cheeseshop (PyPI)
  <https://pypi.python.org/pypi/trollius>`_
* Copyright/license: Open source, Apache 2.0. Enjoy.

The source code of the Trollius project is in the ``trollius`` branch of the
Mercurial repository, not in the default branch. The default branch is the
Tulip project, Trollius repository is a fork of the Tulip repository.

Command to download the development version of the source code (trollius
branch)::

    hg clone 'https://bitbucket.org/enovance/trollius#trollius'


Documentation of the asyncio module
===================================

The documentation of the asyncio is part of the Python project. It can be read
online: `asyncio - Asynchronous I/O, event loop, coroutines and tasks
<http://docs.python.org/dev/library/asyncio.html>`_.


Differences between Trollius and Tulip
======================================

The major difference between Trollius and Tulip is the syntax of coroutines:

==================  ======================
Tulip               Trollius
==================  ======================
``yield from ...``  ``yield From(...)``
``return x``        ``raise Return(x)``
``return x, y``     ``raise Return(x, y)``
==================  ======================

Other differences:

* On Python 2.7, ``asyncio.SSLContext`` has less features than the
  ``ssl.SSLContext`` of Python 3.3: no options, verify_mode cannot be modified
  (fixed to ``CERT_NONE``), no set_default_verify_paths() method, no SNI, etc.
  The SSL transport does not have the ``compression`` extra info in Python 2.
* Python 2 does not support keyword-only parameters.
* If the ``concurrent.futures`` module is missing,
  ``BaseEventLoop.run_in_executor()`` uses a synchronous executor instead of a
  pool of threads. It blocks until the function returns, and so DNS resolutions
  are blocking.
* ``asyncio.subprocess`` has no ``DEVNULL`` constant

.. note::

   Trollius 0.1 used ``yield ...`` syntax in coroutines.


Write code working on Trollius and Tulip
========================================

Trollius and Tulip are different, especially for coroutines (``yield
From(...)`` vs ``yield from``). It is possible to write code working on both
projects if coroutines are not used but only callbacks.

Projects working on Trollius and Tulip:

* `AutobahnPython <https://github.com/tavendo/AutobahnPython>`_: WebSocket &
  WAMP for Python, it works on Trollius (Python 2.6 and 2.7), Tulip (Python
  3.3) and Python 3.4 (asyncio), but also on Twisted.


Install Trollius
================

Packages for Linux
------------------

* `Debian package (0.1.4 available in Sid)
  <https://packages.debian.org/fr/sid/python-trollius>`_
* `Proposition of package for Fedora/RHEL
  <https://bugzilla.redhat.com/show_bug.cgi?id=1066238>`_

Runtime Dependencies
--------------------

On Python older than 3.2, the ``futures`` project is needed to get a backport
of ``concurrent.futures``: https://pypi.python.org/pypi/futures

Python 2.6 requires also ``ordereddict``:
https://pypi.python.org/pypi/ordereddict


Test Dependencies
-----------------

On Python older than 3.3, unit tests require the ``mock`` module:
https://pypi.python.org/pypi/mock

Python 2.6 requires also ``unittest2``:
https://pypi.python.org/pypi/unittest2


Usage
-----

The actual code lives in the ``asyncio`` subdirectory.
Tests are in the ``tests`` subdirectory.

To run tests::

    make test

To run coverage (``coverage`` package is required)::

    make coverage

On Windows, things are a little more complicated.  Assume ``P`` is your Python
binary (for example ``C:\Python33\python.exe``).

You must first build the ``_overlapped.pyd`` extension (it will be placed in
the ``asyncio`` directory)::

    C> P setup.py build_ext

Then you can run the tests as follows::

    C> P runtests.py

And coverage as follows::

    C> P runtests.py --coverage

--Guido van Rossum <guido@python.org>


Backports
---------

To support Python 2.6-3.4, many Python modules of the standard library have
been backported:

========================  =========  =======================
Name                      Python     Backport
========================  =========  =======================
OSError                        3.3   asyncio.py33_exceptions
_overlapped                    3.4   asyncio._overlapped
_winapi                        3.3   asyncio.py33_winapi
collections.OrderedDict   2.7, 3.1   ordereddict (PyPI)
concurrent.futures             3.2   futures (PyPI)
selectors                      3.4   asyncio.selectors
ssl                       3.2, 3.3   asyncio.py3_ssl
time.monotonic                 3.3   asyncio.time_monotonic
unittest                  2.7, 3.1   unittest2 (PyPI)
unittest.mock                  3.3   mock (PyPI)
weakref.WeakSet           2.7, 3.0   asyncio.py27_weakrefset
========================  =========  =======================


Trollius name
=============

Extract of `Trollius Wikipedia article
<http://en.wikipedia.org/wiki/Trollius>`_:

Trollius is a genus of about 30 species of plants in the family Ranunculaceae,
closely related to Ranunculus. The common name of some species is globeflower
or globe flower. Native to the cool temperate regions of the Northern
Hemisphere, with the greatest diversity of species in Asia, trollius usually
grow in heavy, wet clay soils.


Change log
==========

Development version (will be the version 0.2)
---------------------------------------------

* Replace ``yield ...`` with ``yield From(...)``
* On Python 2, Future.set_exception() now only logs the traceback if the debug
  mode of the event loop is enabled. Use: ``loop.set_debug(True)``.
* Fix BaseEventLoop.default_exception_handler(): get the traceback from
  sys.exc_info()
* Fix unit tests on SSL sockets on Python older than 2.6.6. Example:Mac OS 10.6
  with Python 2.6.1 or OpenIndiana 148 with Python 2.6.4.
* Fix error handling in asyncio.time_monotonic

2014-02-25: version 0.1.6
-------------------------

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
-------------------------

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
-------------------------

- The project moved to https://bitbucket.org/enovance/trollius
- Fix CoroWrapper (_DEBUG=True): add missing import
- Emit a warning when Return is not raised
- Merge with Tulip to get latest Tulip bugfixes
- Fix dependencies in tox.ini for the different Python versions

2014-01-13: version 0.1.3
-------------------------

- Workaround bugs in the ssl module of Python older than 2.6.6. For example,
  Mac OS 10.6 (Snow Leopard) uses Python 2.6.1.
- ``return x, y`` is now written ``raise Return(x, y)`` instead of
  ``raise Return((x, y))``
- Support "with (yield lock):" syntax for Lock, Condition and Semaphore
- SSL support is now optional: don't fail if the ssl module is missing
- Add tox.ini, tool to run unit tests. For example, "tox -e py27" creates a
  virtual environment to run tests with Python 2.7.

2014-01-08: version 0.1.2
-------------------------

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
-------------------------

- Fix asyncio.time_monotonic on Mac OS X
- Fix create_connection(ssl=True)
- Don't export backported SSLContext in the ssl module anymore to not confuse
  libraries testing hasattr(ssl, "SSLContext")
- Relax dependency on the backported concurrent.futures module: use a
  synchronous executor if the module is missing

2014-01-04: version 0.1
-------------------------

- First public release

