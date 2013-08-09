"""Http client functional tests."""

import gc
import io
import os.path
import http.cookies
import unittest

import tulip
import tulip.http
from tulip import test_utils
from tulip.http import client


class HttpClientFunctionalTests(unittest.TestCase):

    def setUp(self):
        self.loop = tulip.new_event_loop()
        tulip.set_event_loop(self.loop)

    def tearDown(self):
        # just in case if we have transport close callbacks
        test_utils.run_briefly(self.loop)

        tulip.set_event_loop(None)
        self.loop.close()
        gc.collect()

    def test_HTTP_200_OK_METHOD(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            for meth in ('get', 'post', 'put', 'delete', 'head'):
                r = self.loop.run_until_complete(
                    client.request(meth, httpd.url('method', meth),
                                   loop=self.loop))
                content1 = self.loop.run_until_complete(r.read())
                content2 = self.loop.run_until_complete(r.read())
                content = content1.decode()

                self.assertEqual(r.status, 200)
                self.assertIn('"method": "%s"' % meth.upper(), content)
                self.assertEqual(content1, content2)
                r.close()

    def test_HTTP_302_REDIRECT_GET(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            r = self.loop.run_until_complete(
                client.request('get', httpd.url('redirect', 2),
                               loop=self.loop))

            self.assertEqual(r.status, 200)
            self.assertEqual(2, httpd['redirects'])

    def test_HTTP_302_REDIRECT_NON_HTTP(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            self.assertRaises(
                ValueError,
                self.loop.run_until_complete,
                client.request('get', httpd.url('redirect_err'),
                               loop=self.loop))

    def test_HTTP_302_REDIRECT_POST(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            r = self.loop.run_until_complete(
                client.request('post', httpd.url('redirect', 2),
                               data={'some': 'data'}, loop=self.loop))
            content = self.loop.run_until_complete(r.content.read())
            content = content.decode()

            self.assertEqual(r.status, 200)
            self.assertIn('"method": "POST"', content)
            self.assertEqual(2, httpd['redirects'])

    def test_HTTP_302_max_redirects(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            r = self.loop.run_until_complete(
                client.request('get', httpd.url('redirect', 5),
                               max_redirects=2, loop=self.loop))

            self.assertEqual(r.status, 302)
            self.assertEqual(2, httpd['redirects'])

    def test_HTTP_200_GET_WITH_PARAMS(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            r = self.loop.run_until_complete(
                client.request('get', httpd.url('method', 'get'),
                               params={'q': 'test'}, loop=self.loop))
            content = self.loop.run_until_complete(r.content.read())
            content = content.decode()

            self.assertIn('"query": "q=test"', content)
            self.assertEqual(r.status, 200)

    def test_HTTP_200_GET_WITH_MIXED_PARAMS(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            r = self.loop.run_until_complete(
                client.request(
                    'get', httpd.url('method', 'get') + '?test=true',
                    params={'q': 'test'}, loop=self.loop))
            content = self.loop.run_until_complete(r.content.read())
            content = content.decode()

            self.assertIn('"query": "test=true&q=test"', content)
            self.assertEqual(r.status, 200)

    def test_POST_DATA(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            url = httpd.url('method', 'post')
            r = self.loop.run_until_complete(
                client.request('post', url, data={'some': 'data'},
                               loop=self.loop))
            self.assertEqual(r.status, 200)

            content = self.loop.run_until_complete(r.read(True))
            self.assertEqual({'some': ['data']}, content['form'])
            self.assertEqual(r.status, 200)

    def test_POST_DATA_DEFLATE(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            url = httpd.url('method', 'post')
            r = self.loop.run_until_complete(
                client.request('post', url,
                               data={'some': 'data'}, compress=True,
                               loop=self.loop))
            self.assertEqual(r.status, 200)

            content = self.loop.run_until_complete(r.read(True))
            self.assertEqual('deflate', content['compression'])
            self.assertEqual({'some': ['data']}, content['form'])
            self.assertEqual(r.status, 200)

    def test_POST_FILES(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            url = httpd.url('method', 'post')

            with open(__file__) as f:
                r = self.loop.run_until_complete(
                    client.request(
                        'post', url, files={'some': f}, chunked=1024,
                        headers={'Transfer-Encoding': 'chunked'},
                        loop=self.loop))
                content = self.loop.run_until_complete(r.read(True))

                f.seek(0)
                filename = os.path.split(f.name)[-1]

                self.assertEqual(1, len(content['multipart-data']))
                self.assertEqual(
                    'some', content['multipart-data'][0]['name'])
                self.assertEqual(
                    filename, content['multipart-data'][0]['filename'])
                self.assertEqual(
                    f.read(), content['multipart-data'][0]['data'])
                self.assertEqual(r.status, 200)

    def test_POST_FILES_DEFLATE(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            url = httpd.url('method', 'post')

            with open(__file__) as f:
                r = self.loop.run_until_complete(
                    client.request('post', url, files={'some': f},
                                   chunked=1024, compress='deflate',
                                   loop=self.loop))

                content = self.loop.run_until_complete(r.read(True))

                f.seek(0)
                filename = os.path.split(f.name)[-1]

                self.assertEqual('deflate', content['compression'])
                self.assertEqual(1, len(content['multipart-data']))
                self.assertEqual(
                    'some', content['multipart-data'][0]['name'])
                self.assertEqual(
                    filename, content['multipart-data'][0]['filename'])
                self.assertEqual(
                    f.read(), content['multipart-data'][0]['data'])
                self.assertEqual(r.status, 200)

    def test_POST_FILES_STR(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            url = httpd.url('method', 'post')

            with open(__file__) as f:
                r = self.loop.run_until_complete(
                    client.request('post', url, files=[('some', f.read())],
                                   loop=self.loop))

                content = self.loop.run_until_complete(r.read(True))

                f.seek(0)
                self.assertEqual(1, len(content['multipart-data']))
                self.assertEqual(
                    'some', content['multipart-data'][0]['name'])
                self.assertEqual(
                    'some', content['multipart-data'][0]['filename'])
                self.assertEqual(
                    f.read(), content['multipart-data'][0]['data'])
                self.assertEqual(r.status, 200)

    def test_POST_FILES_LIST(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            url = httpd.url('method', 'post')

            with open(__file__) as f:
                r = self.loop.run_until_complete(
                    client.request('post', url, files=[('some', f)],
                                   loop=self.loop))

                content = self.loop.run_until_complete(r.read(True))

                f.seek(0)
                filename = os.path.split(f.name)[-1]

                self.assertEqual(1, len(content['multipart-data']))
                self.assertEqual(
                    'some', content['multipart-data'][0]['name'])
                self.assertEqual(
                    filename, content['multipart-data'][0]['filename'])
                self.assertEqual(
                    f.read(), content['multipart-data'][0]['data'])
                self.assertEqual(r.status, 200)

    def test_POST_FILES_LIST_CT(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            url = httpd.url('method', 'post')

            with open(__file__) as f:
                r = self.loop.run_until_complete(
                    client.request('post', url,
                                   files=[('some', f, 'text/plain')]))

                content = self.loop.run_until_complete(r.read(True))

                f.seek(0)
                filename = os.path.split(f.name)[-1]

                self.assertEqual(1, len(content['multipart-data']))
                self.assertEqual(
                    'some', content['multipart-data'][0]['name'])
                self.assertEqual(
                    filename, content['multipart-data'][0]['filename'])
                self.assertEqual(
                    f.read(), content['multipart-data'][0]['data'])
                self.assertEqual(
                    'text/plain', content['multipart-data'][0]['content-type'])
                self.assertEqual(r.status, 200)

    def test_POST_FILES_SINGLE(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            url = httpd.url('method', 'post')

            with open(__file__) as f:
                r = self.loop.run_until_complete(
                    client.request('post', url, files=[f]))

                content = self.loop.run_until_complete(r.read(True))

                f.seek(0)
                filename = os.path.split(f.name)[-1]

                self.assertEqual(1, len(content['multipart-data']))
                self.assertEqual(
                    filename, content['multipart-data'][0]['name'])
                self.assertEqual(
                    filename, content['multipart-data'][0]['filename'])
                self.assertEqual(
                    f.read(), content['multipart-data'][0]['data'])
                self.assertEqual(r.status, 200)

    def test_POST_FILES_IO(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            url = httpd.url('method', 'post')

            data = io.BytesIO(b'data')

            r = self.loop.run_until_complete(
                client.request('post', url, files=[data]))

            content = self.loop.run_until_complete(r.read(True))

            self.assertEqual(1, len(content['multipart-data']))
            self.assertEqual(
                {'content-type': 'application/octet-stream',
                 'data': 'data',
                 'filename': 'unknown',
                 'name': 'unknown'}, content['multipart-data'][0])
            self.assertEqual(r.status, 200)

    def test_POST_FILES_WITH_DATA(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            url = httpd.url('method', 'post')

            with open(__file__) as f:
                r = self.loop.run_until_complete(
                    client.request('post', url,
                                   data={'test': 'true'}, files={'some': f}))

                content = self.loop.run_until_complete(r.read(True))

                self.assertEqual(2, len(content['multipart-data']))
                self.assertEqual(
                    'test', content['multipart-data'][0]['name'])
                self.assertEqual(
                    'true', content['multipart-data'][0]['data'])

                f.seek(0)
                filename = os.path.split(f.name)[-1]
                self.assertEqual(
                    'some', content['multipart-data'][1]['name'])
                self.assertEqual(
                    filename, content['multipart-data'][1]['filename'])
                self.assertEqual(
                    f.read(), content['multipart-data'][1]['data'])
                self.assertEqual(r.status, 200)

    def test_encoding(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            r = self.loop.run_until_complete(
                client.request('get', httpd.url('encoding', 'deflate')))
            self.assertEqual(r.status, 200)

            r = self.loop.run_until_complete(
                client.request('get', httpd.url('encoding', 'gzip')))
            self.assertEqual(r.status, 200)

    def test_cookies(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            c = http.cookies.Morsel()
            c.set('test3', '456', '456')

            r = self.loop.run_until_complete(
                client.request(
                    'get', httpd.url('method', 'get'),
                    cookies={'test1': '123', 'test2': c}))
            self.assertEqual(r.status, 200)

            content = self.loop.run_until_complete(r.content.read())
            self.assertIn(b'"Cookie": "test1=123; test3=456"', bytes(content))

    def test_set_cookies(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            resp = self.loop.run_until_complete(
                client.request('get', httpd.url('cookies')))
            self.assertEqual(resp.status, 200)

            self.assertEqual(resp.cookies['c1'].value, 'cookie1')
            self.assertEqual(resp.cookies['c2'].value, 'cookie2')

    def test_chunked(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            r = self.loop.run_until_complete(
                client.request('get', httpd.url('chunked')))
            self.assertEqual(r.status, 200)
            self.assertEqual(r['Transfer-Encoding'], 'chunked')
            content = self.loop.run_until_complete(r.read(True))
            self.assertEqual(content['path'], '/chunked')

    def test_timeout(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            httpd['noresponse'] = True
            self.assertRaises(
                tulip.TimeoutError,
                self.loop.run_until_complete,
                client.request('get', httpd.url('method', 'get'), timeout=0.1))

    def test_request_conn_error(self):
        self.assertRaises(
            OSError,
            self.loop.run_until_complete,
            client.request('get', 'http://0.0.0.0:1', timeout=0.1))

    def test_request_conn_closed(self):
        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            httpd['close'] = True
            self.assertRaises(
                tulip.http.HttpException,
                self.loop.run_until_complete,
                client.request('get', httpd.url('method', 'get')))

    def test_keepalive(self):
        from tulip.http import session
        s = session.Session()

        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            r = self.loop.run_until_complete(
                client.request('get', httpd.url('keepalive',), session=s))
            self.assertEqual(r.status, 200)
            content = self.loop.run_until_complete(r.read(True))
            self.assertEqual(content['content'], 'requests=1')
            r.close()

            r = self.loop.run_until_complete(
                client.request('get', httpd.url('keepalive'), session=s))
            self.assertEqual(r.status, 200)
            content = self.loop.run_until_complete(r.read(True))
            self.assertEqual(content['content'], 'requests=2')
            r.close()

    def test_session_close(self):
        from tulip.http import session
        s = session.Session()

        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            r = self.loop.run_until_complete(
                client.request(
                    'get', httpd.url('keepalive') + '?close=1', session=s))
            self.assertEqual(r.status, 200)
            content = self.loop.run_until_complete(r.read(True))
            self.assertEqual(content['content'], 'requests=1')
            r.close()

            r = self.loop.run_until_complete(
                client.request('get', httpd.url('keepalive'), session=s))
            self.assertEqual(r.status, 200)
            content = self.loop.run_until_complete(r.read(True))
            self.assertEqual(content['content'], 'requests=1')
            r.close()

    def test_session_cookies(self):
        from tulip.http import session
        s = session.Session()

        with test_utils.run_test_server(self.loop, router=Functional) as httpd:
            s.update_cookies({'test': '1'})
            r = self.loop.run_until_complete(
                client.request(
                    'get', httpd.url('cookies'), session=s))
            self.assertEqual(r.status, 200)
            content = self.loop.run_until_complete(r.read(True))

            self.assertEqual(content['headers']['Cookie'], 'test=1')
            r.close()

            cookies = sorted([(k, v.value) for k, v in s.cookies.items()])
            self.assertEqual(
                cookies, [('c1', 'cookie1'), ('c2', 'cookie2'), ('test', '1')])


class Functional(test_utils.Router):

    @test_utils.Router.define('/method/([A-Za-z]+)$')
    def method(self, match):
        meth = match.group(1).upper()
        if meth == self._method:
            self._response(self._start_response(200))
        else:
            self._response(self._start_response(400))

    @test_utils.Router.define('/redirect_err$')
    def redirect_err(self, match):
        self._response(
            self._start_response(302),
            headers={'Location': 'ftp://127.0.0.1/test/'})

    @test_utils.Router.define('/redirect/([0-9]+)$')
    def redirect(self, match):
        no = int(match.group(1).upper())
        rno = self._props['redirects'] = self._props.get('redirects', 0) + 1

        if rno >= no:
            self._response(
                self._start_response(302),
                headers={'Location': '/method/%s' % self._method.lower()})
        else:
            self._response(
                self._start_response(302),
                headers={'Location': self._path})

    @test_utils.Router.define('/encoding/(gzip|deflate)$')
    def encoding(self, match):
        mode = match.group(1)

        resp = self._start_response(200)
        resp.add_compression_filter(mode)
        resp.add_chunking_filter(100)
        self._response(resp, headers={'Content-encoding': mode}, chunked=True)

    @test_utils.Router.define('/chunked$')
    def chunked(self, match):
        resp = self._start_response(200)
        resp.add_chunking_filter(100)
        self._response(resp, chunked=True)

    @test_utils.Router.define('/keepalive$')
    def keepalive(self, match):
        self._transport._requests = getattr(
            self._transport, '_requests', 0) + 1
        resp = self._start_response(200)
        if 'close=' in self._query:
            self._response(
                resp, 'requests={}'.format(self._transport._requests))
        else:
            self._response(
                resp, 'requests={}'.format(self._transport._requests),
                headers={'CONNECTION': 'keep-alive'})

    @test_utils.Router.define('/cookies$')
    def cookies(self, match):
        cookies = http.cookies.SimpleCookie()
        cookies['c1'] = 'cookie1'
        cookies['c2'] = 'cookie2'

        resp = self._start_response(200)
        for cookie in cookies.output(header='').split('\n'):
            resp.add_header('Set-Cookie', cookie.strip())

        self._response(resp)
