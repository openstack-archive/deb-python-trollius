import ssl
from asyncio.backport import _wrap_error

__all__ = ["SSLContext"]

# SSL constants copied from /usr/include/openssl/ssl.h of Fedora 19
#define SSL_ERROR_ZERO_RETURN		6
#define SSL_ERROR_WANT_ACCEPT		8

class SSLWantReadError(ssl.SSLError):
    pass

class SSLWantWriteError(ssl.SSLError):
    pass

class SSLEOFError(ssl.SSLError):
    pass

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


# FIXME: Ugly hack to not have to patch various modules
ssl.SSLWantReadError = SSLWantReadError
ssl.SSLWantWriteError = SSLWantWriteError
#ssl.SSLContext = SSLContext

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
