
__all__ = [
    'CloseHandle', 'CreateNamedPipe', 'CreateFile', 'ConnectNamedPipe',
    'NULL',
    'GENERIC_READ', 'GENERIC_WRITE', 'OPEN_EXISTING', 'INFINITE',
    'PIPE_ACCESS_INBOUND',
    'PIPE_ACCESS_DUPLEX', 'PIPE_TYPE_MESSAGE', 'PIPE_READMODE_MESSAGE',
    'PIPE_WAIT', 'PIPE_UNLIMITED_INSTANCES', 'NMPWAIT_WAIT_FOREVER',
    'FILE_FLAG_OVERLAPPED', 'FILE_FLAG_FIRST_PIPE_INSTANCE',
    'WaitForMultipleObjects', 'WaitForSingleObject',
    'WAIT_OBJECT_0', 'ERROR_IO_PENDING',
    ]

try:
    from _winapi import (
        CloseHandle, CreateNamedPipe, CreateFile, ConnectNamedPipe,
        NULL,
        GENERIC_READ, GENERIC_WRITE, OPEN_EXISTING, INFINITE,
        PIPE_ACCESS_INBOUND,
        PIPE_ACCESS_DUPLEX, PIPE_TYPE_MESSAGE, PIPE_READMODE_MESSAGE,
        PIPE_WAIT, PIPE_UNLIMITED_INSTANCES, NMPWAIT_WAIT_FOREVER,
        FILE_FLAG_OVERLAPPED, FILE_FLAG_FIRST_PIPE_INSTANCE,
        WaitForMultipleObjects, WaitForSingleObject,
        WAIT_OBJECT_0, ERROR_IO_PENDING,
    )
except ImportError:
    from _multiprocessing import win32
    import _subprocess

    CloseHandle = win32.CloseHandle
    CreateNamedPipe = win32.CreateNamedPipe
    CreateFile = win32.CreateFile
    NULL = win32.NULL

    GENERIC_READ = win32.GENERIC_READ
    GENERIC_WRITE = win32.GENERIC_WRITE
    OPEN_EXISTING = win32.OPEN_EXISTING
    INFINITE = win32.INFINITE

    PIPE_ACCESS_INBOUND = win32.PIPE_ACCESS_INBOUND
    PIPE_ACCESS_DUPLEX = win32.PIPE_ACCESS_DUPLEX
    PIPE_READMODE_MESSAGE = win32.PIPE_READMODE_MESSAGE
    PIPE_TYPE_MESSAGE = win32.PIPE_TYPE_MESSAGE
    PIPE_WAIT = win32.PIPE_WAIT
    PIPE_UNLIMITED_INSTANCES = win32.PIPE_UNLIMITED_INSTANCES
    NMPWAIT_WAIT_FOREVER = win32.NMPWAIT_WAIT_FOREVER

    FILE_FLAG_OVERLAPPED = 0x40000000
    FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000

    WAIT_OBJECT_0 = _subprocess.WAIT_OBJECT_0
    WaitForSingleObject = _subprocess.WaitForSingleObject

    def ConnectNamedPipe(handle, overlapped):
        # the version in _multiprocessing.win32 is not compatible
        # with IOCP
        raise NotImplementedError()

    def WaitForMultipleObjects(*args, **kwargs):
        raise NotImplementedError()
