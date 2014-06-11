Trollius
========

.. image:: trollius.jpg
   :alt: Trollius altaicus from Khangai Mountains (Mongòlia)
   :align: right
   :target: http://commons.wikimedia.org/wiki/File:Trollius_altaicus.jpg

Trollius provides infrastructure for writing single-threaded concurrent
code using coroutines, multiplexing I/O access over sockets and other
resources, running network clients and servers, and other related primitives.
Here is a more detailed list of the package contents:

* a pluggable event loop with various system-specific implementations;

* transport and protocol abstractions (similar to those in `Twisted
  <http://twistedmatrix.com/>`_);

* concrete support for TCP, UDP, SSL, subprocess pipes, delayed calls, and
  others (some may be system-dependent);

* a ``Future`` class that mimics the one in the ``concurrent.futures`` module,
  but adapted for use with the event loop;

* coroutines and tasks based on generators (``yield``), to help write
  concurrent code in a sequential fashion;

* cancellation support for ``Future``\s and coroutines;

* synchronization primitives for use between coroutines in a single thread,
  mimicking those in the ``threading`` module;

* an interface for passing work off to a threadpool, for times when you
  absolutely, positively have to use a library that makes blocking I/O calls.

Trollius is a portage of the Tulip project (``asyncio`` module, `PEP 3156
<http://legacy.python.org/dev/peps/pep-3156/>`_) on Python 2. Trollius works on
Python 2.6-3.4. It has been tested on Windows, Linux, Mac OS X, FreeBSD and
OpenIndiana.

* `Asyncio documentation <http://docs.python.org/dev/library/asyncio.html>`_
* `Trollius documentation <http://trollius.readthedocs.org/>`_ (this document)
* `Trollius project in the Python Cheeseshop (PyPI)
  <https://pypi.python.org/pypi/trollius>`_
* `Trollius project at Bitbucket <https://bitbucket.org/enovance/trollius>`_
* Copyright/license: Open source, Apache 2.0. Enjoy!

See also the `Tulip project <http://code.google.com/p/tulip/>`_.


Documentation of the asyncio module
===================================

The documentation of the asyncio is part of the Python project. It can be read
online: `asyncio - Asynchronous I/O, event loop, coroutines and tasks
<http://docs.python.org/dev/library/asyncio.html>`_.

To adapt asyncio examples for Trollius, "just":

* replace ``asyncio`` with ``trollius``
  (or use ``import trollius as asyncio``)
* replace ``yield from ...`` with ``yield From(...)``
* in coroutines, replace ``return res`` with ``raise Return(res)``


Trollius Hello World
====================

Print ``Hello World`` every two seconds, using a coroutine::

    import trollius
    from trollius import From

    @trollius.coroutine
    def greet_every_two_seconds():
        while True:
            print('Hello World')
            yield From(trollius.sleep(2))

    loop = trollius.get_event_loop()
    loop.run_until_complete(greet_every_two_seconds())


Install Trollius
================

Packages for Linux
------------------

* `Debian package
  <https://packages.debian.org/fr/sid/python-trollius>`_
* `ArchLinux package
  <https://aur.archlinux.org/packages/python2-trollius/>`_
* `Fedora and CentOS package: python-trollius
  <http://pkgs.org/download/python-trollius>`_


Install Trollius on Windows using pip
-------------------------------------

Since Trollius 0.2, `precompiled wheel packages <http://pythonwheels.com/>`_
are now distributed on the Python Cheeseshop (PyPI). Procedure to install
Trollius on Windows:

* `Install pip
  <http://www.pip-installer.org/en/latest/installing.html>`_, download
  ``get-pip.py`` and type::

  \Python27\python.exe get-pip.py

* If you already have pip, ensure that you have at least pip 1.4. If you need
  to upgrade::

  \Python27\python.exe -m pip install -U pip

* Install Trollius::

  \Python27\python.exe -m pip install trollius

* pip also installs the ``futures`` dependency

.. note::

   Only wheel packages for Python 2.7 are currently distributed on the
   Cheeseshop (PyPI). If you need wheel packages for other Python versions,
   please ask.

Download source code
--------------------

Command to download the development version of the source code (``trollius``
branch)::

    hg clone 'https://bitbucket.org/enovance/trollius#trollius'

The actual code lives in the ``trollius`` subdirectory. Tests are in the
``tests`` subdirectory.

See the `trollius project at Bitbucket
<https://bitbucket.org/enovance/trollius>`_.

The source code of the Trollius project is in the ``trollius`` branch of the
Mercurial repository, not in the default branch. The default branch is the
Tulip project, Trollius repository is a fork of the Tulip repository.


Dependencies
------------

On Python older than 3.2, the `futures <https://pypi.python.org/pypi/futures>`_
project is needed to get a backport of ``concurrent.futures``.

Python 2.6 requires also `ordereddict
<https://pypi.python.org/pypi/ordereddict>`_.


Build manually Trollius on Windows
----------------------------------

On Windows, if you cannot use precompiled wheel packages, an extension module
must be compiled: the ``_overlapped`` module (source code: ``overlapped.c``).
Read `Compile Python extensions on Windows
<http://haypo-notes.readthedocs.org/python.html#compile-python-extensions-on-windows>`_
to prepare your environment to build the Python extension. Then build the
extension using::

    C:\Python27\python.exe setup.py build_ext


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


Differences between Trollius and Tulip
======================================

Syntax of coroutines
--------------------

The major difference between Trollius and Tulip is the syntax of coroutines:

==================  ======================
Tulip               Trollius
==================  ======================
``yield from ...``  ``yield From(...)``
``return x``        ``raise Return(x)``
``return x, y``     ``raise Return(x, y)``
==================  ======================

Because of this major difference, it was decided to call the module
``trollius`` instead of ``asyncio``. This choice also allows to use Trollius
on Python 3.4 and later.


Other differences
-----------------

* On Python 2.7, ``asyncio.SSLContext`` has less features than the
  ``ssl.SSLContext`` of Python 3.3: no options, verify_mode is set to
  ``CERT_NONE`` and cannot be modified, no set_default_verify_paths() method,
  no SNI, etc. The SSL transport does not have the ``compression`` extra info.
* Python 2 does not support keyword-only parameters.
* If the ``concurrent.futures`` module is missing,
  ``BaseEventLoop.run_in_executor()`` uses a synchronous executor instead of a
  pool of threads. It blocks until the function returns. For example, DNS
  resolutions are blocking in this case.
* ``asyncio.subprocess`` has no ``DEVNULL`` constant

Symbols
-------

Trollius has more symbols than Tulip in the main asyncio module for
compatibility with Python older than 3.3:

* Specific to Trollius:

  - ``From``: part of ``yield From(...)`` syntax
  - ``Return``: part of ``raise Return(...)`` syntax

* SSL:

  - ``SSLContext``
  - Exceptions: ``SSLEOFError``, ``SSLWantReadError``, ``SSLWantWriteError``
  - Flags (bool): ``BACKPORT_SSL_ERRORS``, ``BACKPORT_SSL_CONTEXT``

* OS exceptions:

  - ``BlockingIOError``
  - ``BrokenPipeError``
  - ``ChildProcessError``
  - ``ConnectionAbortedError``
  - ``ConnectionRefusedError``
  - ``ConnectionResetError``
  - ``FileNotFoundError``
  - ``InterruptedError``
  - ``PermissionError``


Write code working on Trollius and Tulip
========================================

Trollius and Tulip are different, especially for coroutines (``yield
From(...)`` vs ``yield from ...``).

To use asyncio or Trollius on Python 2 and Python 3, add the following code at
the top of your file::

    try:
        # Use builtin asyncio on Python 3.4+, or Tulip on Python 3.3
        import asyncio
    except ImportError:
        # Use Trollius on Python <= 3.2
        import trollius as asyncio

It is possible to write code working on both projects using only callbacks.
This option is used by the following projects which work on Trollius and Tulip:

* `AutobahnPython <https://github.com/tavendo/AutobahnPython>`_: WebSocket &
  WAMP for Python, it works on Trollius (Python 2.6 and 2.7), Tulip (Python
  3.3) and Python 3.4 (asyncio), and also on Twisted.
* `Pulsar <http://pythonhosted.org/pulsar/>`_: Event driven concurrent
  framework for Python. With pulsar you can write asynchronous servers
  performing one or several activities in different threads and/or processes.
  Trollius 0.3 requires Pulsar 0.8.2 or later. Pulsar uses the ``asyncio``
  module if available, or import ``trollius``.
* It looks like `Tornado <http://www.tornadoweb.org/>`_ supports Tulip and
  Trollius.

Another option is to provide functions returning ``Future`` objects, so the
caller can decide to use callback using ``fut.add_done_callback(callback)`` or
to use coroutines (``yield From(fut)`` for Trollius, or ``yield from fut`` for
Tulip). This option is used by the `aiodns <https://github.com/saghul/aiodns>`_
project for example.

It is possible to write an application working on Trollius or asyncio with the
same code base. It is not possible yet to run an application using Tulip
with a module using Trollius (or the opposite). Applications and modules
should both use Tulip or both use Trollius. Be careful of imports.

.. note::

   The Trollius module was called ``asyncio`` in Trollius version 0.2. The
   module name changed to ``trollius`` to support Python 3.4.


Run tests
=========

Run tests with tox
------------------

The `tox project <https://testrun.org/tox/latest/>`_ can be used to build a
virtual environment with all runtime and test dependencies and run tests
against different Python versions (2.6, 2.7, 3.2, 3.3).

For example, to run tests with Python 2.7, just type::

    tox -e py27

To run tests against other Python versions:

* ``py26``: Python 2.6
* ``py27``: Python 2.7
* ``py32``: Python 3.2
* ``py33``: Python 3.3


Test Dependencies
-----------------

On Python older than 3.3, unit tests require the `mock
<https://pypi.python.org/pypi/mock>`_ module. Python 2.6 requires also
`unittest2 <https://pypi.python.org/pypi/unittest2>`_.


Run tests on UNIX
-----------------

Run the following commands from the directory of the Trollius project.

To run tests::

    make test

To run coverage (``coverage`` package is required)::

    make coverage


Run tests on Windows
--------------------

Run the following commands from the directory of the Trollius project.

You can run the tests as follows::

    C:\Python27\python.exe runtests.py

And coverage as follows::

    C:\Python27\python.exe runtests.py --coverage


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

Version 0.3.1
-------------

Synchronize with Tulip.

2014-05-26: version 0.3
-----------------------

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
-----------------------

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

