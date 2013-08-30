"""HTTP Client for Tulip.

Most basic usage:

  response = yield from tulip.http.request('GET', url)
  response['Content-Type'] == 'application/json'
  response.status == 200

  content = yield from response.content.read()
"""

__all__ = ['request']

import base64
import email.message
import functools
import http.client
import http.cookies
import json
import io
import itertools
import mimetypes
import os
import uuid
import urllib.parse

import tulip
import tulip.http


@tulip.coroutine
def request(method, url, *,
            params=None,
            data=None,
            headers=None,
            cookies=None,
            files=None,
            auth=None,
            allow_redirects=True,
            max_redirects=10,
            encoding='utf-8',
            version=(1, 1),
            timeout=None,
            compress=None,
            chunked=None,
            session=None,
            loop=None):
    """Constructs and sends a request. Returns response object.

    method: http method
    url: request url
    params: (optional) Dictionary or bytes to be sent in the query string
      of the new request
    data: (optional) Dictionary, bytes, or file-like object to
      send in the body of the request
    headers: (optional) Dictionary of HTTP Headers to send with the request
    cookies: (optional) Dict object to send with the request
    files: (optional) Dictionary of 'name': file-like-objects
       for multipart encoding upload
    auth: (optional) Auth tuple to enable Basic HTTP Auth
    timeout: (optional) Float describing the timeout of the request
    allow_redirects: (optional) Boolean. Set to True if POST/PUT/DELETE
       redirect following is allowed.
    compress: Boolean. Set to True if request has to be compressed
       with deflate encoding.
    chunked: Boolean or Integer. Set to chunk size for chunked
       transfer encoding.
    session: tulip.http.Session instance to support connection pooling and
       session cookies.
    loop: Optional event loop.

    Usage:

      import tulip.http
      >> resp = yield from tulip.http.request('GET', 'http://python.org/')
      >> resp
      <HttpResponse(python.org/) [200]>

      >> data = yield from resp.content.read()

    """
    redirects = 0
    if loop is None:
        loop = tulip.get_event_loop()

    while True:
        req = HttpRequest(
            method, url, params=params, headers=headers, data=data,
            cookies=cookies, files=files, auth=auth, encoding=encoding,
            version=version, compress=compress, chunked=chunked)

        if session is None:
            conn = start(req, loop)
        else:
            conn = session.start(req, loop)

        # connection timeout
        t = tulip.Task(conn, loop=loop)
        th = None
        if timeout is not None:
            th = loop.call_later(timeout, t.cancel)
        try:
            resp = yield from t
        except tulip.CancelledError:
            raise tulip.TimeoutError from None
        finally:
            if th is not None:
                th.cancel()

        # redirects
        if resp.status in (301, 302) and allow_redirects:
            redirects += 1
            if max_redirects and redirects >= max_redirects:
                resp.close()
                break

            r_url = resp.get('location') or resp.get('uri')

            scheme = urllib.parse.urlsplit(r_url)[0]
            if scheme not in ('http', 'https', ''):
                raise ValueError('Can redirect only to http or https')
            elif not scheme:
                r_url = urllib.parse.urljoin(url, r_url)

            url = urllib.parse.urldefrag(r_url)[0]
            if url:
                resp.close()
                continue

        break

    return resp


@tulip.coroutine
def start(req, loop):
    transport, p = yield from loop.create_connection(
        functools.partial(tulip.StreamProtocol, loop=loop),
        req.host, req.port, ssl=req.ssl)

    try:
        resp = req.send(transport)
        yield from resp.start(p, transport)
    except:
        transport.close()
        raise

    return resp


class HttpRequest:

    GET_METHODS = {'DELETE', 'GET', 'HEAD', 'OPTIONS'}
    POST_METHODS = {'PATCH', 'POST', 'PUT', 'TRACE'}
    ALL_METHODS = GET_METHODS.union(POST_METHODS)

    DEFAULT_HEADERS = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
    }

    body = b''

    def __init__(self, method, url, *,
                 params=None,
                 headers=None,
                 data=None,
                 cookies=None,
                 files=None,
                 auth=None,
                 encoding='utf-8',
                 version=(1, 1),
                 compress=None,
                 chunked=None):
        self.method = method.upper()
        self.encoding = encoding

        # parser http version '1.1' => (1, 1)
        if isinstance(version, str):
            v = [l.strip() for l in version.split('.', 1)]
            try:
                version = int(v[0]), int(v[1])
            except ValueError:
                raise ValueError(
                    'Can not parse http version number: {}'
                    .format(version)) from None
        self.version = version

        # path
        scheme, netloc, path, query, fragment = urllib.parse.urlsplit(url)
        if not netloc:
            raise ValueError('Host could not be detected.')

        if not path:
            path = '/'
        else:
            path = urllib.parse.unquote(path)

        # check domain idna encoding
        try:
            netloc = netloc.encode('idna').decode('utf-8')
        except UnicodeError:
            raise ValueError('URL has an invalid label.')

        # basic auth info
        if '@' in netloc:
            authinfo, netloc = netloc.split('@', 1)
            if not auth:
                auth = authinfo.split(':', 1)
                if len(auth) == 1:
                    auth.append('')

        # extract host and port
        ssl = scheme == 'https'

        if ':' in netloc:
            netloc, port_s = netloc.split(':', 1)
            try:
                port = int(port_s)
            except ValueError:
                raise ValueError(
                    'Port number could not be converted.') from None
        else:
            if ssl:
                port = http.client.HTTPS_PORT
            else:
                port = http.client.HTTP_PORT

        self.host = netloc
        self.port = port
        self.ssl = ssl

        # build url query
        if isinstance(params, dict):
            params = list(params.items())

        if data and self.method in self.GET_METHODS:
            # include data to query
            if isinstance(data, dict):
                data = data.items()
            params = list(itertools.chain(params or (), data))
            data = None

        if params:
            params = urllib.parse.urlencode(params)
            if query:
                query = '%s&%s' % (query, params)
            else:
                query = params

        # build path
        path = urllib.parse.quote(path)
        self.path = urllib.parse.urlunsplit(('', '', path, query, fragment))

        # headers
        self.headers = email.message.Message()
        if headers:
            if isinstance(headers, dict):
                headers = list(headers.items())

            for key, value in headers:
                self.headers.add_header(key, value)

        for hdr, val in self.DEFAULT_HEADERS.items():
            if hdr not in self.headers:
                self.headers[hdr] = val

        # host
        if 'host' not in self.headers:
            self.headers['Host'] = self.host

        # cookies
        if cookies:
            self.update_cookies(cookies)

        # auth
        if auth:
            if isinstance(auth, (tuple, list)) and len(auth) == 2:
                # basic auth
                self.headers['Authorization'] = 'Basic %s' % (
                    base64.b64encode(
                        ('%s:%s' % (auth[0], auth[1])).encode('latin1'))
                    .strip().decode('latin1'))
            else:
                raise ValueError("Only basic auth is supported")

        # Content-encoding
        enc = self.headers.get('Content-Encoding', '').lower()
        if enc:
            chunked = True  # enable chunked, no need to deal with length
            compress = enc
        elif compress:
            chunked = True  # enable chunked, no need to deal with length
            compress = compress if isinstance(compress, str) else 'deflate'
            self.headers['Content-Encoding'] = compress

        # form data (x-www-form-urlencoded)
        if isinstance(data, dict):
            data = list(data.items())

        if data and not files:
            if not isinstance(data, str):
                data = urllib.parse.urlencode(data, doseq=True)

            self.body = data.encode(encoding)
            if 'content-type' not in self.headers:
                self.headers['content-type'] = (
                    'application/x-www-form-urlencoded')
            if 'content-length' not in self.headers and not chunked:
                self.headers['content-length'] = str(len(self.body))

        # files (multipart/form-data)
        elif files:
            fields = []

            if data:
                for field, val in data:
                    fields.append((field, str_to_bytes(val)))

            if isinstance(files, dict):
                files = list(files.items())

            for rec in files:
                if not isinstance(rec, (tuple, list)):
                    rec = (rec,)

                ft = None
                if len(rec) == 1:
                    k = guess_filename(rec[0], 'unknown')
                    fields.append((k, k, rec[0]))

                elif len(rec) == 2:
                    k, fp = rec
                    fn = guess_filename(fp, k)
                    fields.append((k, fn, fp))

                else:
                    k, fp, ft = rec
                    fn = guess_filename(fp, k)
                    fields.append((k, fn, fp, ft))

            chunked = chunked or 8192
            boundary = uuid.uuid4().hex

            self.body = encode_multipart_data(
                fields, bytes(boundary, 'latin1'))

            self.headers['content-type'] = (
                'multipart/form-data; boundary=%s' % boundary)

        # chunked
        te = self.headers.get('transfer-encoding', '').lower()

        if chunked:
            if 'content-length' in self.headers:
                del self.headers['content-length']
            if 'chunked' not in te:
                self.headers['transfer-encoding'] = 'chunked'

            chunked = chunked if type(chunked) is int else 8196
        else:
            if 'chunked' in te:
                chunked = 8196
            else:
                chunked = None
                self.headers['content-length'] = str(len(self.body))

        self._chunked = chunked
        self._compress = compress

    def update_cookies(self, cookies):
        """Update request cookies header."""
        c = http.cookies.SimpleCookie()
        if 'cookie' in self.headers:
            c.load(self.headers.get('cookie', ''))
            del self.headers['cookie']

        if isinstance(cookies, dict):
            cookies = cookies.items()

        for name, value in cookies:
            if isinstance(value, http.cookies.Morsel):
                # use dict method because SimpleCookie class modifies value
                dict.__setitem__(c, name, value)
            else:
                c[name] = value

        self.headers['cookie'] = c.output(header='', sep=';').strip()

    def send(self, transport):
        request = tulip.http.Request(
            transport, self.method, self.path, self.version)

        if self._compress:
            request.add_compression_filter(self._compress)

        if self._chunked is not None:
            request.add_chunking_filter(self._chunked)

        request.add_headers(*self.headers.items())
        request.send_headers()

        if isinstance(self.body, bytes):
            self.body = (self.body,)

        for chunk in self.body:
            request.write(chunk)

        request.write_eof()

        return HttpResponse(self.method, self.path, self.host)


class HttpResponse(http.client.HTTPMessage):

    message = None  # RawResponseMessage object

    # from the Status-Line of the response
    version = None  # HTTP-Version
    status = None   # Status-Code
    reason = None   # Reason-Phrase

    cookies = None  # Response cookies (Set-Cookie)

    content = None  # payload stream
    stream = None   # input stream
    transport = None  # current transport

    def __init__(self, method, url, host=''):
        super().__init__()

        self.method = method
        self.url = url
        self.host = host
        self._content = None

    def __del__(self):
        self.close()

    def __repr__(self):
        out = io.StringIO()
        print('<HttpResponse({}{}) [{} {}]>'.format(
            self.host, self.url, self.status, self.reason), file=out)
        print(super().__str__(), file=out)
        return out.getvalue()

    def start(self, stream, transport):
        """Start response processing."""
        self.stream = stream
        self.transport = transport

        httpstream = stream.set_parser(tulip.http.http_response_parser())

        # read response
        self.message = yield from httpstream.read()

        # response status
        self.version = self.message.version
        self.status = self.message.code
        self.reason = self.message.reason

        # headers
        for hdr, val in self.message.headers:
            self.add_header(hdr, val)

        # payload
        self.content = stream.set_parser(
            tulip.http.http_payload_parser(self.message))

        # cookies
        self.cookies = http.cookies.SimpleCookie()
        if 'Set-Cookie' in self:
            for hdr in self.get_all('Set-Cookie'):
                self.cookies.load(hdr)

        return self

    def close(self):
        if self.transport is not None:
            self.transport.close()
            self.transport = None

    @tulip.coroutine
    def read(self, decode=False):
        """Read response payload. Decode known types of content."""
        if self._content is None:
            buf = []
            total = 0
            chunk = yield from self.content.read()
            while chunk:
                size = len(chunk)
                buf.append((chunk, size))
                total += size
                chunk = yield from self.content.read()

            self._content = bytearray(total)

            idx = 0
            content = memoryview(self._content)
            for chunk, size in buf:
                content[idx:idx+size] = chunk
                idx += size

        data = self._content

        if decode:
            ct = self.get('content-type', '').lower()
            if ct == 'application/json':
                data = json.loads(data.decode('utf-8'))

        return data


def str_to_bytes(s, encoding='utf-8'):
    if isinstance(s, str):
        return s.encode(encoding)
    return s


def guess_filename(obj, default=None):
    name = getattr(obj, 'name', None)
    if name and name[0] != '<' and name[-1] != '>':
        return os.path.split(name)[-1]
    return default


def encode_multipart_data(fields, boundary, encoding='utf-8', chunk_size=8196):
    """
    Encode a list of fields using the multipart/form-data MIME format.

    fields:
        List of (name, value) or (name, filename, io) or
        (name, filename, io, MIME type) field tuples.
    """
    for rec in fields:
        yield b'--' + boundary + b'\r\n'

        field, *rec = rec

        if len(rec) == 1:
            data = rec[0]
            yield (('Content-Disposition: form-data; name="%s"\r\n\r\n' %
                    (field,)).encode(encoding))
            yield data + b'\r\n'

        else:
            if len(rec) == 3:
                fn, fp, ct = rec
            else:
                fn, fp = rec
                ct = (mimetypes.guess_type(fn)[0] or
                      'application/octet-stream')

            yield ('Content-Disposition: form-data; name="%s"; '
                   'filename="%s"\r\n' % (field, fn)).encode(encoding)
            yield ('Content-Type: %s\r\n\r\n' % (ct,)).encode(encoding)

            if isinstance(fp, str):
                fp = fp.encode(encoding)

            if isinstance(fp, bytes):
                fp = io.BytesIO(fp)

            while True:
                chunk = fp.read(chunk_size)
                if not chunk:
                    break
                yield str_to_bytes(chunk)

            yield b'\r\n'

    yield b'--' + boundary + b'--\r\n'
