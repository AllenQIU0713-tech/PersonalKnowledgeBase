"""Top-level entry UX must preserve authentication and cross-site rejection."""
import unittest
from http.client import HTTPResponse
from html.parser import HTMLParser
from urllib.parse import urlsplit,parse_qs
import test_ar_navigation_delivery as harness


class Links(HTMLParser):
    def __init__(self): super().__init__(); self.hrefs=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a': self.hrefs.extend(v for k,v in attrs if k=='href')


class SameOriginEntry(unittest.TestCase):
    def setUp(self):
        self.h=harness.NavigationDelivery();self.h.setUp();self.addCleanup(self.h.doCleanups)

    def request(self,path='/unlock?token=SECRET-BOOTSTRAP',**overrides):
        headers={'Sec-Fetch-Site':'cross-site','Sec-Fetch-Mode':'navigate','Sec-Fetch-Dest':'document',**overrides}
        req=self.h.make(path=path,headers=headers);req.route()
        response=HTTPResponse(harness.Wire(req.wfile.getvalue()));response.begin()
        body=response.read().decode();links=Links();links.feed(body)
        return response,body,links.hrefs

    def test_cross_site_stays_403_without_consuming_secret(self):
        response,body,links=self.request()
        self.assertEqual(response.status,403)
        self.assertIn('text/html',response.getheader('Content-Type'))
        self.assertEqual(self.h.server.bootstrap,'SECRET-BOOTSTRAP')
        self.assertEqual(response.getheader('Set-Cookie'),None)
        self.assertIn("frame-ancestors 'none'",response.getheader('Content-Security-Policy'))
        self.assertEqual(links,['/unlock?token=SECRET-BOOTSTRAP'])
        self.assertNotIn('<script',body.lower())

    def test_following_same_origin_link_still_uses_one_time_guard(self):
        _,_,links=self.request()
        req=self.h.make(path=links[0],headers={'Sec-Fetch-Site':'same-origin'})
        req.route();response=HTTPResponse(harness.Wire(req.wfile.getvalue()));response.begin()
        self.assertEqual(response.status,303)
        self.assertIsNone(self.h.server.bootstrap)
        self.assertIsNotNone(response.getheader('Set-Cookie'))
        root=self.h.make(path='/',headers={'Cookie':'pkb_session=SECRET-SESSION','Sec-Fetch-Site':'same-origin'})
        root.route();response=HTTPResponse(harness.Wire(root.wfile.getvalue()));response.begin()
        self.assertEqual(response.status,200)
        replay=self.h.make(path=links[0]);replay.route()
        response=HTTPResponse(harness.Wire(replay.wfile.getvalue()));response.begin()
        self.assertEqual(response.status,403)

    def test_api_remains_json_rejected(self):
        response,body,links=self.request('/api/session')
        self.assertEqual(response.status,403);self.assertEqual(links,[])
        self.assertIn('application/json',response.getheader('Content-Type'))

    def test_wrong_host_origin_and_iframe_do_not_get_entry(self):
        for headers in ({'Host':'attacker.invalid'}, {'Origin':'https://attacker.invalid'},
                        {'Sec-Fetch-Dest':'iframe'}, {'Sec-Fetch-Mode':'cors'}):
            with self.subTest(headers=headers):
                response,_,links=self.request(**headers)
                self.assertEqual(response.status,403);self.assertEqual(links,[])
        self.assertEqual(self.h.server.bootstrap,'SECRET-BOOTSTRAP')

    def test_root_only_links_to_local_root(self):
        response,_,links=self.request('/')
        self.assertEqual(response.status,403);self.assertEqual(links,['/'])
        root=self.h.make(path='/');root.route()
        response=HTTPResponse(harness.Wire(root.wfile.getvalue()));response.begin()
        self.assertEqual(response.status,401)

    def test_malicious_token_and_redirect_are_not_reflected(self):
        for value in ('%22%3E%3Cscript%3E','https%3A%2F%2Fattacker.invalid','a'*257):
            response,body,links=self.request('/unlock?token='+value)
            self.assertEqual(response.status,403);self.assertEqual(links,[])
            self.assertNotIn('attacker.invalid',body);self.assertNotIn('<script',body.lower())
        _,_,links=self.request('/unlock?token=SECRET-BOOTSTRAP&next=https://attacker.invalid')
        self.assertEqual(links,['/unlock?token=SECRET-BOOTSTRAP'])

    def test_cross_site_post_remains_rejected(self):
        req=self.h.make(headers={'Sec-Fetch-Site':'cross-site','Sec-Fetch-Mode':'navigate','Sec-Fetch-Dest':'document'})
        req.command='POST';req.route()
        response=HTTPResponse(harness.Wire(req.wfile.getvalue()));response.begin()
        self.assertEqual(response.status,403);self.assertIn('application/json',response.getheader('Content-Type'))
        self.assertEqual(self.h.server.bootstrap,'SECRET-BOOTSTRAP')

    def test_same_origin_post_still_requires_csrf(self):
        req=self.h.make(path='/api/documents',headers={'Sec-Fetch-Site':'same-origin',
            'Cookie':'pkb_session=SECRET-SESSION','Origin':'http://127.0.0.1:18471','X-PKB-CSRF':'wrong'})
        self.h.server.csrf='synthetic-csrf';req.command='POST';req.route()
        response=HTTPResponse(harness.Wire(req.wfile.getvalue()));response.begin()
        self.assertEqual(response.status,403)


if __name__=='__main__':unittest.main(verbosity=2)
