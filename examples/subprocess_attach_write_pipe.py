#!/usr/bin/env python3
"""Example showing how to attach a write pipe to a subprocess."""
import asyncio
import os, sys
from asyncio import subprocess

code = """
import os, sys
fd = int(sys.argv[1])
data = os.read(fd, 1024)
if sys.version_info >= (3,):
    stdout = sys.stdout.buffer
else:
    stdout = sys.stdout
stdout.write(data)
"""

loop = asyncio.get_event_loop()

@asyncio.coroutine
def task():
    rfd, wfd = os.pipe()
    args = [sys.executable, '-c', code, str(rfd)]
    kwargs = {'stdout': subprocess.PIPE}
    if sys.version_info >= (3, 2):
        kwargs['pass_fds'] = (rfd,)
    proc = yield asyncio.create_subprocess_exec(*args, **kwargs)

    pipe = open(wfd, 'wb', 0)
    transport, _ = yield loop.connect_write_pipe(asyncio.Protocol,
                                                      pipe)
    transport.write(b'data')

    stdout, stderr = yield proc.communicate()
    print("stdout = %r" % stdout.decode())

loop.run_until_complete(task())
