
__all__ = ['CloseHandle']

try:
    from _winapi import CloseHandle
except ImportError:
    from _multiprocessing import win32
    CloseHandle = win32.CloseHandle
