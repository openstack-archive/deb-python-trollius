# Release procedure:
#  - run unit tests
#  - test examples
#  - update version in setup.py
#  - set _DEBUG to True in asyncio/coroutine.py
#  - set release date in the change log (README file)
#  - hg ci
#  - hg tag trollius-VERSION
#  - hg push
#  - python setup.py register sdist bdist_wheel upload

import os
try:
    from setuptools import setup, Extension
except ImportError:
    # Use distutils.core as a fallback.
    # We won't be able to build the Wheel file on Windows.
    from distutils.core import setup, Extension

extensions = []
if os.name == 'nt':
    ext = Extension(
        'asyncio._overlapped', ['overlapped.c'], libraries=['ws2_32'],
    )
    extensions.append(ext)

setup(
    name="trollius",
    version="0.1",

    description="Experimental port (asyncio module, PEP 3156) of the Tulip project on Python 2.7",
    long_description=open("README").read(),
    url="https://bitbucket.org/haypo/trollius/",

    classifiers=[
        "Programming Language :: Python",
    ],

    packages=["asyncio"],

    ext_modules=extensions,
)
