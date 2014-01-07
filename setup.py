# Release procedure:
#  - run unit tests without concurrent.futures
#  - run unit tests with concurrent.futures
#  - test examples
#  - update version in setup.py
#  - set _DEBUG to False in asyncio/coroutine.py
#  - set release date in the change log (README file)
#  - hg ci
#  - hg tag trollius-VERSION
#  - hg push
#  - python setup.py register sdist bdist_wheel upload

import os
import sys
try:
    from setuptools import setup, Extension
    SETUPTOOLS = True
except ImportError:
    SETUPTOOLS = False
    # Use distutils.core as a fallback.
    # We won't be able to build the Wheel file on Windows.
    from distutils.core import setup, Extension

with open("README") as fp:
    long_description = fp.read()

extensions = []
if os.name == 'nt':
    ext = Extension(
        'asyncio._overlapped', ['overlapped.c'], libraries=['ws2_32'],
    )
    extensions.append(ext)

requirements = []
if sys.version < (2, 7):
    requirements.append('ordereddict')
if sys.version < (3,):
    requirements.append('futures')

install_options = {
    "name": "trollius",
    "version": "0.1.1",

    "description": "Experimental port of the Tulip project (asyncio module, PEP 3156) on Python 2.7",
    "long_description": long_description,
    "url": "https://bitbucket.org/haypo/trollius/",

    "classifiers": [
        "Programming Language :: Python",
        "License :: OSI Approved :: Apache Software License",
    ],

    "packages": ["asyncio"],

    "ext_modules": extensions,
}
if SETUPTOOLS:
    install_options['install_requires'] = requirements

setup(**install_options)
