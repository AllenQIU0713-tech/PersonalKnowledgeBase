"""In-memory original Handler and observer tests; no sockets, model or browser."""
import io
import json
import sys
import tempfile
import threading
import unittest
from http.client import HTTPResponse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pkb.server import Handler
from ar_http import ResponseGates, build_handler


class Wire:
    def __init__(self, data): self.data = data
    def makefile(self, *args): return io.BytesIO(self.data)


class NavigationDelivery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.server = SimpleNamespace(
            origin='http://127.0.0.1:18471', authority='127.0.0.1:18471',
            bootstrap='SECRET-BOOTSTRAP', session='SECRET-SESSION',
            store=SimpleNamespace(lock=threading.RLock()))

    def make(self, product=Handler, path='/unlock?token=SECRET-BOOTSTRAP', headers=None):
        observed = build_handler(product, self.root, ResponseGates(), lambda *a, **kw: None)
        req = object.__new__(observed)
        req.path, req.command, req.request_version = path, 'GET', 'HTTP/1.1'
        req.requestline = 'GET / HTTP/1.1'
        req.server, req.wfile = self.server, io.BytesIO()
        req.headers = {'Host': self.server.authority, 'Sec-Fetch-Site': 'none', **(headers or {})}
        return req

    def rows(self):
        return [json.loads(line) for line in (self.root/'private-navigation.jsonl').read_text().splitlines()]

    def test_original_303_wire_and_observer_return(self):
        req = self.make()
        req.route()
        response = HTTPResponse(Wire(req.wfile.getvalue()))
        response.begin()
        self.assertEqual(response.status, 303)
        self.assertEqual(response.getheader('Location'), '/')
        self.assertEqual(response.getheader('Content-Length'), '0')
        self.assertEqual(response.read(), b'')
        self.assertEqual(response.getheader('Set-Cookie'),
                         'pkb_session=SECRET-SESSION; HttpOnly; SameSite=Strict; Path=/')
        entered, returned = self.rows()[-2:]
        self.assertEqual(entered['event'], 'original_navigation_response')
        self.assertTrue(entered['location_is_root'])
        self.assertTrue(entered['session_cookie_attributes_match'])
        self.assertEqual(returned['event'], 'original_navigation_response_call_returned')
        self.assertFalse(returned['client_receipt_verified'])
        self.assertIsNone(self.server.bootstrap)
        raw = (self.root/'private-navigation.jsonl').read_text()
        self.assertNotIn('SECRET', raw)
        self.assertNotIn('?token', raw)

    def test_original_root_cookie_and_replay_policy(self):
        self.make().route()
        root = self.make(path='/', headers={'Cookie': 'pkb_session=SECRET-SESSION'})
        root.route()
        response = HTTPResponse(Wire(root.wfile.getvalue())); response.begin()
        self.assertEqual(response.status, 200)
        replay = self.make(); replay.route()
        response = HTTPResponse(Wire(replay.wfile.getvalue())); response.begin()
        self.assertEqual(response.status, 403)

    def test_cross_site_does_not_consume_bootstrap(self):
        req = self.make(headers={'Sec-Fetch-Site': 'cross-site'})
        req.route()
        self.assertEqual(self.server.bootstrap, 'SECRET-BOOTSTRAP')
        response = HTTPResponse(Wire(req.wfile.getvalue())); response.begin()
        self.assertEqual(response.status, 403)

    def test_original_write_failure_is_rethrown_without_secret(self):
        class FailingWriter:
            def write(self, value): raise BrokenPipeError('SECRET-transport-URL')
        req = self.make(); req.wfile = FailingWriter()
        with self.assertRaisesRegex(BrokenPipeError, 'SECRET-transport-URL'):
            req.route()
        self.assertIsNone(self.server.bootstrap)
        terminal = self.rows()[-1]
        self.assertEqual(terminal['event'], 'original_navigation_response_exception')
        self.assertEqual(terminal['exception_type'], 'BrokenPipeError')
        self.assertFalse(terminal['client_receipt_verified'])
        self.assertNotIn('SECRET', (self.root/'private-navigation.jsonl').read_text())

    def test_original_return_and_arguments_are_preserved(self):
        sentinel = object()
        payload = b''
        headers = {'Location': '/', 'Set-Cookie': 'pkb_session=SECRET; HttpOnly; SameSite=Strict; Path=/'}
        class Product:
            def route(inner): return inner.respond(303, payload, 'text/plain', headers)
            def respond(inner, status, data, content_type, actual_headers):
                self.assertIs(data, payload); self.assertIs(actual_headers, headers)
                self.assertEqual((status, content_type), (303, 'text/plain'))
                return sentinel
        self.assertIs(self.make(product=Product).route(), sentinel)

    def test_reset_and_timeout_keep_original_exception(self):
        for error_type in (ConnectionResetError, TimeoutError):
            with self.subTest(error=error_type.__name__):
                self.server.bootstrap = 'SECRET-BOOTSTRAP'
                error = error_type('SECRET-original-error')
                class Writer:
                    def write(self, value): raise error
                req = self.make(); req.wfile = Writer()
                with self.assertRaises(error_type) as caught: req.route()
                self.assertIs(caught.exception, error)
                self.assertEqual(self.rows()[-1]['exception_type'], error_type.__name__)
                self.assertNotIn('SECRET', (self.root/'private-navigation.jsonl').read_text())

    def test_observer_write_failure_does_not_mask_transport_failure(self):
        error = BrokenPipeError('SECRET-original-error')
        # Keep the write failure active through the outer observer's exception handler.
        class Writer:
            def write(self, value):
                self.patcher = patch('builtins.open', side_effect=OSError('observer unavailable'))
                self.patcher.start()
                raise error
        req = self.make(); writer = Writer(); req.wfile = writer
        try:
            with self.assertRaises(BrokenPipeError) as caught: req.route()
            self.assertIs(caught.exception, error)
            self.assertTrue(req._ar_navigation_observation_failed)
        finally:
            if hasattr(writer, 'patcher'): writer.patcher.stop()


if __name__ == '__main__': unittest.main(verbosity=2)
