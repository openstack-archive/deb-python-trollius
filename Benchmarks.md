# asyncio benchmarks #

  * [Macro-benchmark with Django, Flask and AsyncIO (aiohttp.web+API-Hour)](http://blog.gmludo.eu/2015/02/macro-benchmark-with-django-flask-and-asyncio.html): Ludovic Gasc, 25 February 2015
  * [bigdata](https://bitbucket.org/zzzeek/bigdata/) (created: 2015-02-16): INSERT queries to a PostgreSQL server, asyncio vs gevent vs threads; article: [Asynchronous Python and Databases](http://techspot.zzzeek.org/2015/02/15/asynchronous-python-and-databases/) (Mike Bayer, 2015-02-15)
  * [API Hour](https://github.com/Eyepea/API-Hour/): Flask, PostgreSQL (aiopg), asyncio, JSON
  * [asyncio-redis/examples/benchmarks/ directory](https://github.com/jonathanslenders/asyncio-redis/blob/master/examples/benchmarks/); see [redis: benchmark gevent vs asyncio on python3.4](https://gist.github.com/yihuang/eb0a670c9fab188c6e3e)
  * [aiohttp: benchmark/async.py](https://github.com/KeepSafe/aiohttp/blob/master/benchmark/async.py)
  * [irc3: examples/benches.py](https://github.com/gawel/irc3/blob/master/examples/benches.py)

Trollius:

  * [Tobias Oberstein tweeted](https://twitter.com/oberstet/status/550741713762136064): "unbelievable: #PyPy doing 90k reqs/sec on netperf TCP\_RR at 50% CPU on _one_ core over 10GbE! https://github.com/oberstet/scratchbox/blob/master/python/asyncio/tcp_echo_server.py" (Trollius works on PyPy, but asyncio doesn't work on PyPy yet)