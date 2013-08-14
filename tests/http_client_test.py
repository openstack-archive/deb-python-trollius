# -*- coding: utf-8 -*-
"""Tests for tulip/http/client.py"""

import unittest
import unittest.mock
import urllib.parse

import tulip
import tulip.http

from tulip.http.client import HttpRequest, HttpResponse


class HttpResponseTests(unittest.TestCase):

    def setUp(self):
        self.loop = tulip.new_event_loop()
        tulip.set_event_loop(None)

        self.transport = unittest.mock.Mock()
        self.stream = tulip.StreamBuffer(loop=self.loop)
        self.response = HttpResponse('get', 'http://python.org')

    def tearDown(self):
        self.loop.close()

    def test_close(self):
        self.response.transport = self.transport
        self.response.close()
        self.assertIsNone(self.response.transport)
        self.assertTrue(self.transport.close.called)
        self.response.close()
        self.response.close()

    def test_repr(self):
        self.response.status = 200
        self.response.reason = 'Ok'
        self.assertIn(
            '<HttpResponse(http://python.org) [200 Ok]>', repr(self.response))


class HttpRequestTests(unittest.TestCase):

    def setUp(self):
        self.loop = tulip.new_event_loop()
        tulip.set_event_loop(None)

        self.transport = unittest.mock.Mock()
        self.stream = tulip.StreamBuffer(loop=self.loop)

    def tearDown(self):
        self.loop.close()

    def test_method(self):
        req = HttpRequest('get', 'http://python.org/')
        self.assertEqual(req.method, 'GET')

        req = HttpRequest('head', 'http://python.org/')
        self.assertEqual(req.method, 'HEAD')

        req = HttpRequest('HEAD', 'http://python.org/')
        self.assertEqual(req.method, 'HEAD')

    def test_version(self):
        req = HttpRequest('get', 'http://python.org/', version='1.0')
        self.assertEqual(req.version, (1, 0))

    def test_version_err(self):
        self.assertRaises(
            ValueError,
            HttpRequest, 'get', 'http://python.org/', version='1.c')

    def test_host_port(self):
        req = HttpRequest('get', 'http://python.org/')
        self.assertEqual(req.host, 'python.org')
        self.assertEqual(req.port, 80)
        self.assertFalse(req.ssl)

        req = HttpRequest('get', 'https://python.org/')
        self.assertEqual(req.host, 'python.org')
        self.assertEqual(req.port, 443)
        self.assertTrue(req.ssl)

        req = HttpRequest('get', 'https://python.org:960/')
        self.assertEqual(req.host, 'python.org')
        self.assertEqual(req.port, 960)
        self.assertTrue(req.ssl)

    def test_host_port_err(self):
        self.assertRaises(
            ValueError, HttpRequest, 'get', 'http://python.org:123e/')

    def test_host_header(self):
        req = HttpRequest('get', 'http://python.org/')
        self.assertEqual(req.headers['host'], 'python.org')

        req = HttpRequest('get', 'http://python.org/',
                          headers={'host': 'example.com'})
        self.assertEqual(req.headers['host'], 'example.com')

    def test_headers(self):
        req = HttpRequest('get', 'http://python.org/',
                          headers={'Content-Type': 'text/plain'})
        self.assertIn('Content-Type', req.headers)
        self.assertEqual(req.headers['Content-Type'], 'text/plain')
        self.assertEqual(req.headers['Accept-Encoding'], 'gzip, deflate')

    def test_headers_list(self):
        req = HttpRequest('get', 'http://python.org/',
                          headers=[('Content-Type', 'text/plain')])
        self.assertIn('Content-Type', req.headers)
        self.assertEqual(req.headers['Content-Type'], 'text/plain')

    def test_headers_default(self):
        req = HttpRequest('get', 'http://python.org/',
                          headers={'Accept-Encoding': 'deflate'})
        self.assertEqual(req.headers['Accept-Encoding'], 'deflate')

    def test_invalid_url(self):
        self.assertRaises(ValueError, HttpRequest, 'get', 'hiwpefhipowhefopw')

    def test_invalid_idna(self):
        self.assertRaises(
            ValueError, HttpRequest, 'get', 'http://\u2061owhefopw.com')

    def test_no_path(self):
        req = HttpRequest('get', 'http://python.org')
        self.assertEqual('/', req.path)

    def test_basic_auth(self):
        req = HttpRequest('get', 'http://python.org', auth=('nkim', '1234'))
        self.assertIn('Authorization', req.headers)
        self.assertEqual('Basic bmtpbToxMjM0', req.headers['Authorization'])

    def test_basic_auth_from_url(self):
        req = HttpRequest('get', 'http://nkim:1234@python.org')
        self.assertIn('Authorization', req.headers)
        self.assertEqual('Basic bmtpbToxMjM0', req.headers['Authorization'])

        req = HttpRequest('get', 'http://nkim@python.org')
        self.assertIn('Authorization', req.headers)
        self.assertEqual('Basic bmtpbTo=', req.headers['Authorization'])

        req = HttpRequest(
            'get', 'http://nkim@python.org', auth=('nkim', '1234'))
        self.assertIn('Authorization', req.headers)
        self.assertEqual('Basic bmtpbToxMjM0', req.headers['Authorization'])

    def test_basic_auth_err(self):
        self.assertRaises(
            ValueError, HttpRequest,
            'get', 'http://python.org', auth=(1, 2, 3))

    def test_no_content_length(self):
        req = HttpRequest('get', 'http://python.org')
        req.send(self.transport)
        self.assertEqual('0', req.headers.get('Content-Length'))

        req = HttpRequest('head', 'http://python.org')
        req.send(self.transport)
        self.assertEqual('0', req.headers.get('Content-Length'))

    def test_path_is_not_double_encoded(self):
        req = HttpRequest('get', "http://0.0.0.0/get/test case")
        self.assertEqual(req.path, "/get/test%20case")

        req = HttpRequest('get', "http://0.0.0.0/get/test%20case")
        self.assertEqual(req.path, "/get/test%20case")

    def test_params_are_added_before_fragment(self):
        req = HttpRequest(
            'GET', "http://example.com/path#fragment", params={"a": "b"})
        self.assertEqual(
            req.path, "/path?a=b#fragment")

        req = HttpRequest(
            'GET',
            "http://example.com/path?key=value#fragment", params={"a": "b"})
        self.assertEqual(
            req.path, "/path?key=value&a=b#fragment")

    def test_cookies(self):
        req = HttpRequest(
            'get', 'http://test.com/path', cookies={'cookie1': 'val1'})
        self.assertIn('Cookie', req.headers)
        self.assertEqual('cookie1=val1', req.headers['cookie'])

        req = HttpRequest(
            'get', 'http://test.com/path',
            headers={'cookie': 'cookie1=val1'},
            cookies={'cookie2': 'val2'})
        self.assertEqual('cookie1=val1; cookie2=val2', req.headers['cookie'])

    def test_unicode_get(self):
        def join(*suffix):
            return urllib.parse.urljoin('http://python.org/', '/'.join(suffix))

        url = 'http://python.org'
        req = HttpRequest('get', url, params={'foo': 'f\xf8\xf8'})
        self.assertEqual('/?foo=f%C3%B8%C3%B8', req.path)
        req = HttpRequest('', url, params={'f\xf8\xf8': 'f\xf8\xf8'})
        self.assertEqual('/?f%C3%B8%C3%B8=f%C3%B8%C3%B8', req.path)
        req = HttpRequest('', url, params={'foo': 'foo'})
        self.assertEqual('/?foo=foo', req.path)
        req = HttpRequest('', join('\xf8'), params={'foo': 'foo'})
        self.assertEqual('/%C3%B8?foo=foo', req.path)

    def test_query_multivalued_param(self):
        for meth in HttpRequest.ALL_METHODS:
            req = HttpRequest(
                meth, 'http://python.org',
                params=(('test', 'foo'), ('test', 'baz')))
            self.assertEqual(req.path, '/?test=foo&test=baz')

    def test_post_data(self):
        for meth in HttpRequest.POST_METHODS:
            req = HttpRequest(meth, 'http://python.org/', data={'life': '42'})
            req.send(self.transport)
            self.assertEqual('/', req.path)
            self.assertEqual(b'life=42', req.body[0])
            self.assertEqual('application/x-www-form-urlencoded',
                             req.headers['content-type'])

    def test_get_with_data(self):
        for meth in HttpRequest.GET_METHODS:
            req = HttpRequest(meth, 'http://python.org/', data={'life': '42'})
            self.assertEqual('/?life=42', req.path)

    @unittest.mock.patch('tulip.http.client.tulip')
    def test_content_encoding(self, m_tulip):
        req = HttpRequest('get', 'http://python.org/', compress='deflate')
        req.send(self.transport)
        self.assertEqual(req.headers['Transfer-encoding'], 'chunked')
        self.assertEqual(req.headers['Content-encoding'], 'deflate')
        m_tulip.http.Request.return_value\
            .add_compression_filter.assert_called_with('deflate')

    @unittest.mock.patch('tulip.http.client.tulip')
    def test_content_encoding_header(self, m_tulip):
        req = HttpRequest('get', 'http://python.org/',
                          headers={'Content-Encoding': 'deflate'})
        req.send(self.transport)
        self.assertEqual(req.headers['Transfer-encoding'], 'chunked')
        self.assertEqual(req.headers['Content-encoding'], 'deflate')

        m_tulip.http.Request.return_value\
            .add_compression_filter.assert_called_with('deflate')
        m_tulip.http.Request.return_value\
            .add_chunking_filter.assert_called_with(8196)

    def test_chunked(self):
        req = HttpRequest(
            'get', 'http://python.org/',
            headers={'Transfer-encoding': 'gzip'})
        req.send(self.transport)
        self.assertEqual('gzip', req.headers['Transfer-encoding'])

        req = HttpRequest(
            'get', 'http://python.org/',
            headers={'Transfer-encoding': 'chunked'})
        req.send(self.transport)
        self.assertEqual('chunked', req.headers['Transfer-encoding'])

    @unittest.mock.patch('tulip.http.client.tulip')
    def test_chunked_explicit(self, m_tulip):
        req = HttpRequest(
            'get', 'http://python.org/', chunked=True)
        req.send(self.transport)

        self.assertEqual('chunked', req.headers['Transfer-encoding'])
        m_tulip.http.Request.return_value\
                            .add_chunking_filter.assert_called_with(8196)

    @unittest.mock.patch('tulip.http.client.tulip')
    def test_chunked_explicit_size(self, m_tulip):
        req = HttpRequest(
            'get', 'http://python.org/', chunked=1024)
        req.send(self.transport)
        self.assertEqual('chunked', req.headers['Transfer-encoding'])
        m_tulip.http.Request.return_value\
                            .add_chunking_filter.assert_called_with(1024)

    def test_chunked_length(self):
        req = HttpRequest(
            'get', 'http://python.org/',
            headers={'Content-Length': '1000'}, chunked=1024)
        req.send(self.transport)
        self.assertEqual(req.headers['Transfer-Encoding'], 'chunked')
        self.assertNotIn('Content-Length', req.headers)
