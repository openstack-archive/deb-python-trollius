++++++++++++++
Using Trollius
++++++++++++++

Documentation of the asyncio module
===================================

The documentation of the asyncio is part of the Python project. It can be read
online: `asyncio - Asynchronous I/O, event loop, coroutines and tasks
<http://docs.python.org/dev/library/asyncio.html>`_.

To adapt asyncio examples for Trollius, "just":

* replace ``asyncio`` with ``trollius``
  (or use ``import trollius as asyncio``)
* replace ``yield from ...`` with ``yield From(...)``
* replace ``yield from []`` with ``yield From(None)``
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

