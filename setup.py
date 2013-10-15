import os
from distutils.core import setup, Extension

extensions = []
if os.name == 'nt':
    ext = Extension('_overlapped', ['overlapped.c'], libraries=['ws2_32'])
    extensions.append(ext)

setup(name='asyncio',
      description="reference implementation of PEP 3156",
      url='http://www.python.org/dev/peps/pep-3156/',
      packages=['asyncio'],
      ext_modules=extensions
     )
