"""
Backport of time.monotonic() of Python 3.3 (PEP 418) for Python 2.7.

Export one function: time_monotonic(). This clock may or may not be monotonic
depending on the operating system.

Support Windows, Mac OS X, Linux, FreeBSD, OpenBSD and Solaris, but requires
the ctypes module.
"""
import os
import sys

__all__ = ('time_monotonic',)

# default implementation: system clock (non monotonic!)
from time import time as time_monotonic

if os.name == "nt":
    # Windows: use GetTickCount64() or GetTickCount()
    try:
        import ctypes
        from ctypes import windll
        from ctypes.wintypes import DWORD
    except ImportError:
        pass

    # GetTickCount64() requires Windows Vista, Server 2008 or later
    if hasattr(windll.kernel32, 'GetTickCount64'):
        ULONGLONG = ctypes.c_uint64

        GetTickCount64 = windll.kernel32.GetTickCount64
        GetTickCount64.restype = ULONGLONG
        GetTickCount64.argtypes = ()

        def time_monotonic():
            return GetTickCount64() * 1e-3
    else:
        GetTickCount = windll.kernel32.GetTickCount
        GetTickCount.restype = DWORD
        GetTickCount.argtypes = ()

        # Detect GetTickCount() integer overflow (32 bits, roll-over after 49.7
        # days). It increases an internal epoch (reference time) by 2^32 each
        # time that an overflow is detected. The epoch is stored in the
        # process-local state and so the value of time_monotonic() may be
        # different in two Python processes running for more than 49 days.
        def time_monotonic(use_info):
            ticks = GetTickCount()
            if ticks < time_monotonic.last:
                # Integer overflow detected
                time_monotonic.delta += 2**32
            time_monotonic.last = ticks
            return (ticks + time_monotonic.delta) * 1e-3
        time_monotonic.last = 0
        time_monotonic.delta = 0

elif sys.platform == 'darwin':
    # Mac OS X: use mach_absolute_time() and mach_timebase_info()
    try:
        import ctypes
        import ctypes.util
        libc_name = ctypes.util.find_library('c')
    except ImportError:
        libc_name = None
    if libc_name:
        libc = ctypes.CDLL(libc_name, use_errno=True)

        mach_absolute_time = libc.mach_absolute_time
        mach_absolute_time.argtypes = ()
        mach_absolute_time.restype = ctypes.c_uint64

        class mach_timebase_info_data_t(ctypes.Structure):
            _fields_ = (
                ('numer', ctypes.c_uint32),
                ('denom', ctypes.c_uint32),
            )
        mach_timebase_info_data_p = ctypes.POINTER(mach_timebase_info_data_t)

        mach_timebase_info = libc.mach_timebase_info
        mach_timebase_info.argtypes = (mach_timebase_info_data_p,)
        mach_timebase_info.restype = ctypes.c_int

        def time_monotonic():
            return mach_absolute_time() * time_monotonic.factor

        timebase = mach_timebase_info_data_t()
        mach_timebase_info(ctypes.byref(timebase))
        time_monotonic.factor = float(timebase.numer) / timebase.denom * 1e-9
        del timebase

elif sys.platform.startswith(("linux", "freebsd", "openbsd", "sunos")):
    # Linux, FreeBSD, OpenBSD: use clock_gettime(CLOCK_MONOTONIC)
    # Solaris: use clock_gettime(CLOCK_HIGHRES)

    library = None
    try:
        import ctypes
        import ctypes.util
    except ImportError:
        libraries = ()
    else:
        if sys.platform.startswith(("freebsd", "openbsd")):
            libraries = ('c',)
        elif sys.platform.startswith("linux"):
            # Linux: in glibc 2.17+, clock_gettime() is provided by the libc,
            # on older versions, it is provided by librt
            libraries = ('c', 'rt')
        else:
            # Solaris
            libraries = ('rt',)

    for name in libraries:
        filename = ctypes.util.find_library(name)
        if not filename:
            continue
        library = ctypes.CDLL(filename, use_errno=True)
        if not hasattr(library, 'clock_gettime'):
            library = None

    if library is not None:
        time_t = ctypes.c_long
        clockid_t = ctypes.c_int

        class timespec(ctypes.Structure):
            _fields_ = (
                ('tv_sec', time_t),
                ('tv_nsec', ctypes.c_long),
            )
        timespec_p = ctypes.POINTER(timespec)

        clock_gettime = library.clock_gettime
        clock_gettime.argtypes = (clockid_t, timespec_p)
        clock_gettime.restype = ctypes.c_int

        def time_monotonic():
            ts = timespec()
            err = clock_gettime(time_monotonic.clk_id, ctypes.byref(ts))
            if err:
                errno = ctypes.get_errno()
                message = os.strerror(errno)
                return OSError(errno, message)
            return ts.tv_sec + ts.tv_nsec * 1e-9

        if sys.platform.startswith("linux"):
            time_monotonic.clk_id = 1   # CLOCK_MONOTONIC
        elif sys.platform.startswith("freebsd"):
            time_monotonic.clk_id = 4   # CLOCK_MONOTONIC
        elif sys.platform.startswith("openbsd"):
            time_monotonic.clk_id = 3   # CLOCK_MONOTONIC
        elif sys.platform.startswith("sunos"):
            time_monotonic.clk_id = 4   # CLOCK_HIGHRES

