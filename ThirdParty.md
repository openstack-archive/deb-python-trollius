See also [asyncio.org](http://asyncio.org/) (asyncio resources) and [Trollius](http://trollius.readthedocs.org/) (port of asyncio to Python 2).

# Libraries #

  * [aiofiles](https://github.com/Tinche/aiofiles/): File support for asyncio
  * [aiohttp](https://github.com/KeepSafe/aiohttp): http client and server infrastructure for asyncio
  * [aiodns](https://pypi.python.org/pypi/aiodns): Async DNS resolver
  * [aiorwlock](https://pypi.python.org/pypi/aiorwlock): Read write lock for asyncio.
  * [aioutils](https://pypi.python.org/pypi/aioutils): Python3 Asyncio Utils, Group (like gevent.pool.Group), Pool (like event.poo.Pool), Bag and OrderedBag.
  * [tasklocals](https://github.com/vkryachko/tasklocals): Task-local variables

# Clients #

  * Asterisk: [panoramisk](https://panoramisk.readthedocs.org/), a library based on python’s asyncio to play with asterisk‘s manager
  * ElasticSearch: [aioes](http://aioes.readthedocs.org/), client library
  * IRC: [irc3](https://irc3.readthedocs.org/), plugable irc client library based on python's asyncio
  * IRC: [bottom](https://github.com/numberoverzero/bottom), asyncio-based rfc2812-compliant IRC Client
  * XMPP (Jabber): [slixmpp](http://git.poez.io/slixmpp), SleekXMPP (XMPP Library) fork using asyncio, for poezio

# Databases #

SQL drivers:

  * MySQL: [aiomysql](https://github.com/aio-libs/aiomysql), MySQL driver
  * PostgreSQL: [aiopg](http://aiopg.readthedocs.org/), PostgreSQL client library built on top of psycopg2

NoSQL and key-value store drivers:

  * CouchDB: [aiocouchdb](http://aiocouchdb.readthedocs.org), CouchDB client
  * memcached: [aiomemcache](https://github.com/fafhrd91/aiomemcache), minimal memcached client
  * MongoDB: [asyncio-mongo](https://bitbucket.org/mrdon/asyncio-mongo), MongoDB driver (ported from Twisted)
  * redis: [asyncio-redis](http://asyncio-redis.readthedocs.org/), Redis client
  * redis: [aioredis](http://aioredis.readthedocs.org/), Yet another Redis client

ORM:

  * [peewee](https://peewee.readthedocs.org/): [peewee-async](http://peewee-async.readthedocs.org/en/latest/), library providing asynchronous interface powered by asyncio for peewee ORM.

# Web frameworks #

  * [aiopyramid](https://pypi.python.org/pypi/aiopyramid): Tools for running [pyramid](https://pypi.python.org/pypi/pyramid) using asyncio.
  * [aiowsgi](https://github.com/gawel/aiowsgi): minimalist wsgi server using asyncio
  * [API hour](https://pypi.python.org/pypi/api_hour): Write efficient network daemons (HTTP, SSH, ...) with ease.
  * [AutobahnPython](https://github.com/tavendo/AutobahnPython): WebSocket and WAMP framework
  * [interest](https://pypi.python.org/pypi/interest): event-driven web framework on top of aiohttp/asyncio.
  * [muffin](https://github.com/klen/muffin): A web framework based on Asyncio stack (early alpha)
  * [nacho](https://github.com/avelino/nacho): web framework
  * [Pulsar](http://pythonhosted.org/pulsar/): Event driven concurrent framework for python. With pulsar you can write asynchronous servers performing one or several activities in different threads and/or processes.
  * [rainfall](https://github.com/mind1master/rainfall): another web framework
  * [Vase](https://github.com/vkryachko/Vase): web framework
  * [websockets](https://github.com/aaugustin/websockets): Websockets library
  * [WebSocket-for-Python](https://github.com/Lawouach/WebSocket-for-Python): another websocket library

Looking for WSGI? Read this thread: [WSGI implementation compatible with asyncio?](https://groups.google.com/forum/#!topic/python-tulip/Gs3bZ2AbS9o).

# Integration with other application libraries #

  * [aioamqp](https://github.com/dzen/aioamqp): AMQP implementation using asyncio
  * gunicorn: gunicorn has gaiohttp worker built on top of aiohttp library

# Run asyncio on top of #

  * eventlet: [aiogreen](http://aiogreen.readthedocs.org/), asyncio API implemented on top of eventlet
  * gevent: [aiogevent](https://pypi.python.org/pypi/aiogevent), asyncio API implemented on top of gevent

# Adapters for other event loops #

Some people have already written adapters for integrating asyncio with other async I/O frameworks.

  * [eventlet](http://eventlet.net/): [greenio](https://github.com/1st1/greenio), Greenlets support for asyncio (PEP 3156)
  * [gevent](http://www.gevent.org/): [tulipcore](https://github.com/decentfox/tulipcore), run gevent code on top of asyncio, alternative gevent core loop
  * GLib: [gbulb](https://bitbucket.org/a_ba/gbulb), event loop based on GLib
  * [libuv](https://github.com/libuv/libuv): [aiouv](https://github.com/saghul/aiouv), an event loop implementation for asyncio based on [pyuv](https://pyuv.readthedocs.org/)
  * Qt: [Quamash](https://github.com/harvimt/quamash), implementation of the PEP 3156 Event-Loop with Qt.
  * [Tornado](https://github.com/facebook/tornado) has [experimental asyncio support](https://groups.google.com/forum/#!topic/python-tulip/hg0HzhoPuFE) built right into it.
  * [ZeroMQ](http://zeromq.org/): [aiozmq](http://aiozmq.readthedocs.org/), ZeroMQ integration with asyncio
  * [ZeroMQ](http://zeromq.org/): [Zantedeschia](https://github.com/takluyver/Zantedeschia), experimental alternative integration between asyncio and ZeroMQ sockets.

# Misc #

  * [aiocron](https://github.com/gawel/aiocron/): Crontabs for asyncio
  * [aiomas](http://stefan.sofa-rockers.org/2015/02/13/aiomas/): A library for multi-agent systems and RPC based on asyncio
  * [aiotest](https://bitbucket.org/haypo/aiotest/): test suite to validate an implementation of the asyncio API
  * [aioprocessing](https://github.com/dano/aioprocessing): A Python 3.3+ library that integrates the multiprocessing module with asyncio
  * [blender-asyncio](https://github.com/akloster/blender-asyncio): Asyncio Bridge for Blender Python API
  * [ipython-yf](https://github.com/tecki/ipython-yf):  An ipython extension to make it asyncio compatible
  * [aiogearman](https://github.com/jettify/aiogearman): asyncio [gearman](http://gearman.org/) support. Gearman provides a generic application framework to farm out work to other machines or processes that are better suited to do the work.
  * Serial port using the serial module, see [using serial port in python3 asyncio](https://stackoverflow.com/questions/21666106/using-serial-port-in-python3-asyncio) at Stackoverflow, serial.Serial can be registered with loop.add\_reader().

# Filesystem #

asyncio does **not** support asynchronous operations on the filesystem. Even if files are opened with O\_NONBLOCK, read and write will block.

Read [asynchronous disk I/O](http://blog.libtorrent.org/2012/10/asynchronous-disk-io/) (October 2012 by arvid).

The Linux kernel provides asynchronous operations on the filesystem (aio), but it requires a library and it doesn't scale with many concurrent operations. See [aio](http://lse.sourceforge.net/io/aio.html).

The GNU C library (glibc) implements the POSIX aio interface, but it is implemented with threads. See [aio(7) manual page](http://man7.org/linux/man-pages/man7/aio.7.html).

Recent discussion on the Linux Kernel: [Non-blocking buffered file read operations](http://lwn.net/Articles/612483/) (September 2014).