"""
Compatibility constants and functions for the different Python versions.
"""
import sys

# Python 2.6 or older?
PY26 = (sys.version_info < (2, 7))

# Python 3.0 or newer?
PY3 = (sys.version_info >= (3,))

# Python 3.3 or newer?
PY33 = (sys.version_info >= (3, 3))

# Python 3.4 or newer?
PY34 = sys.version_info >= (3, 4)

if PY3:
    BYTES_TYPES = (bytes, bytearray, memoryview)
elif PY26:
    BYTES_TYPES = (bytes, bytearray, buffer)
else:
    BYTES_TYPES = (bytes, bytearray, memoryview, buffer)

def flatten_bytes(data):
    """
    Convert bytes-like objects (bytes, bytearray, memoryview, buffer) to
    a bytes string.
    """
    if not isinstance(data, BYTES_TYPES):
        raise TypeError('data argument must be byte-ish (%r)',
                        type(data))
    if PY34:
        # In Python 3.4, socket.send() and bytes.join() accept memoryview
        # and bytearray
        return data
    if not data:
        return b''
    if not PY3 and isinstance(data, (buffer, bytearray)):
        return bytes(data)
    elif not PY26 and isinstance(data, memoryview):
        return data.tobytes()
    else:
        return data

