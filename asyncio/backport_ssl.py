import ssl
from asyncio.backport import _wrap_error

__all__ = ["SSLContext", "BACKPORT_SSL_ERRORS", "BACKPORT_SSL_CONTEXT"]

try:
    # Available since Python 3.3
    SSLWantWriteError = ssl.SSLWantWriteError
    SSLWantWriteError = ssl.SSLWantWriteError
    SSLEOFError = ssl.SSLEOFError
    BACKPORT_SSL_ERRORS = False
except AttributeError:
    BACKPORT_SSL_ERRORS = True

    class SSLWantReadError(ssl.SSLError):
        pass

    class SSLWantWriteError(ssl.SSLError):
        pass

    class SSLEOFError(ssl.SSLError):
        pass

    # FIXME: Ugly hack to not have to patch various modules
    ssl.SSLWantReadError = SSLWantReadError
    ssl.SSLWantWriteError = SSLWantWriteError


try:
    # Available since Python 3.2
    SSLContext = ssl.SSLContext
    BACKPORT_SSL_CONTEXT = False
except AttributeError:
    BACKPORT_SSL_CONTEXT = True
    class SSLContext(object):
        def __init__(self, protocol=ssl.PROTOCOL_SSLv23):
            self.protocol = protocol
            self.certfile = None
            self.keyfile = None

        def load_cert_chain(self, certfile, keyfile):
            self.certfile = certfile
            self.keyfile = keyfile

        def wrap_socket(self, sock, **kw):
            return ssl.wrap_socket(sock,
                                   ssl_version=self.protocol,
                                   certfile=self.certfile,
                                   keyfile=self.keyfile,
                                   **kw)

        @property
        def verify_mode(self):
            return ssl.CERT_NONE


if BACKPORT_SSL_ERRORS:
    _MAP_ERRORS = {
        ssl.SSL_ERROR_WANT_READ: SSLWantReadError,
        ssl.SSL_ERROR_WANT_WRITE: SSLWantWriteError,
        ssl.SSL_ERROR_EOF: SSLEOFError,
    }

    def wrap_ssl_error(func, *args, **kw):
        try:
            return func(*args, **kw)
        except ssl.SSLError as err:
            if err.args:
                _wrap_error(_MAP_ERRORS, err.args[0], err.args)
            raise
else:
    def wrap_ssl_error(func, *args, **kw):
        return func(*args, **kw)
