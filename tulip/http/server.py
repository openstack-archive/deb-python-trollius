"""simple http server."""

__all__ = ['ServerHttpProtocol']

import http.server
import inspect
import logging
import traceback

import tulip
from tulip.http import errors


RESPONSES = http.server.BaseHTTPRequestHandler.responses
DEFAULT_ERROR_MESSAGE = """
<html>
  <head>
    <title>{status} {reason}</title>
  </head>
  <body>
    <h1>{status} {reason}</h1>
    {message}
  </body>
</html>"""


class ServerHttpProtocol(tulip.Protocol):
    """Simple http protocol implementation.

    ServerHttpProtocol handles incoming http request. It reads request line,
    request headers and request payload and calls handler_request() method.
    By default it always returns with 404 respose.

    ServerHttpProtocol handles errors in incoming request, like bad
    status line, bad headers or incomplete payload. If any error occurs,
    connection gets closed.

    log: custom logging object
    debug: enable debug mode
    keep_alive: number of seconds before closing keep alive connection
    loop: event loop object
    """
    _request_count = 0
    _request_handler = None
    _keep_alive = False  # keep transport open
    _keep_alive_handle = None  # keep alive timer handle

    def __init__(self, *, log=logging, debug=False,
                 keep_alive=None, loop=None, **kwargs):
        self.__dict__.update(kwargs)
        self.log = log
        self.debug = debug

        self._keep_alive_period = keep_alive  # number of seconds to keep alive

        if keep_alive and loop is None:
            loop = tulip.get_event_loop()
        self._loop = loop

    def connection_made(self, transport):
        self.transport = transport
        self.stream = tulip.StreamBuffer()
        self._request_handler = self.start()

    def data_received(self, data):
        self.stream.feed_data(data)

    def eof_received(self):
        self.stream.feed_eof()

    def connection_lost(self, exc):
        self.stream.feed_eof()

        if self._request_handler is not None:
            self._request_handler.cancel()
            self._request_handler = None
        if self._keep_alive_handle is not None:
            self._keep_alive_handle.cancel()
            self._keep_alive_handle = None

    def keep_alive(self, val):
        self._keep_alive = val

    def log_access(self, status, message, *args, **kw):
        pass

    def log_debug(self, *args, **kw):
        if self.debug:
            self.log.debug(*args, **kw)

    def log_exception(self, *args, **kw):
        self.log.exception(*args, **kw)

    @tulip.task
    def start(self):
        """Start processing of incoming requests.
        It reads request line, request headers and request payload, then
        calls handle_request() method. Subclass has to override
        handle_request(). start() handles various excetions in request
        or response handling. Connection is being closed always unless
        keep_alive(True) specified.
        """

        while True:
            info = None
            message = None
            self._request_count += 1
            self._keep_alive = False

            try:
                httpstream = self.stream.set_parser(
                    tulip.http.http_request_parser())

                message = yield from httpstream.read()

                # cancel keep-alive timer
                if self._keep_alive_handle is not None:
                    self._keep_alive_handle.cancel()
                    self._keep_alive_handle = None

                payload = self.stream.set_parser(
                    tulip.http.http_payload_parser(message))

                handler = self.handle_request(message, payload)
                if (inspect.isgenerator(handler) or
                        isinstance(handler, tulip.Future)):
                    yield from handler

            except tulip.CancelledError:
                self.log_debug('Ignored premature client disconnection.')
                break
            except errors.HttpException as exc:
                self.handle_error(exc.code, info, message, exc, exc.headers)
            except Exception as exc:
                self.handle_error(500, info, message, exc)
            finally:
                if self._request_handler:
                    if self._keep_alive and self._keep_alive_period:
                        self._keep_alive_handle = self._loop.call_later(
                            self._keep_alive_period, self.transport.close)
                    else:
                        self.transport.close()
                        self._request_handler = None
                        break
                else:
                    break

    def handle_error(self, status=500,
                     message=None, payload=None, exc=None, headers=None):
        """Handle errors.

        Returns http response with specific status code. Logs additional
        information. It always closes current connection."""
        try:
            if self._request_handler is None:
                # client has been disconnected during writing.
                return

            if status == 500:
                self.log_exception("Error handling request")

            try:
                reason, msg = RESPONSES[status]
            except KeyError:
                status = 500
                reason, msg = '???', ''

            if self.debug and exc is not None:
                try:
                    tb = traceback.format_exc()
                    msg += '<br><h2>Traceback:</h2>\n<pre>{}</pre>'.format(tb)
                except:
                    pass

            self.log_access(status, message)

            html = DEFAULT_ERROR_MESSAGE.format(
                status=status, reason=reason, message=msg)

            response = tulip.http.Response(self.transport, status, close=True)
            response.add_headers(
                ('Content-Type', 'text/html'),
                ('Content-Length', str(len(html))))
            if headers is not None:
                response.add_headers(*headers)
            response.send_headers()

            response.write(html.encode('ascii'))
            response.write_eof()
        finally:
            self.keep_alive(False)

    def handle_request(self, message, payload):
        """Handle a single http request.

        Subclass should override this method. By default it always
        returns 404 response.

        info: tulip.http.RequestLine instance
        message: tulip.http.RawHttpMessage instance
        """
        response = tulip.http.Response(
            self.transport, 404, http_version=message.version, close=True)

        body = b'Page Not Found!'

        response.add_headers(
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(len(body))))
        response.send_headers()
        response.write(body)
        response.write_eof()

        self.keep_alive(False)
        self.log_access(404, message)
