"""Real candidate Handler assembly and authenticated raw loopback API capture."""
from http.server import ThreadingHTTPServer
import json
import secrets
import threading
import urllib.request
import urllib.error

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args): raise ValueError('redirect forbidden')

class DeniedCloud:
    name='test-denied-real-cloud'
    destination='https://example.invalid/forbidden'
    def __init__(self,emit): self.emit=emit
    def configured(self): return False
    def answer(self,payload): self.emit('forbidden_provider_attempt');raise AssertionError('real cloud forbidden')

class App:
    def __init__(self, store, embedding, modules, emit):
        Handler,Answers=modules
        server=self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.daemon_threads=True
        server.store,server.embeddings=store,embedding
        server.answers=Answers(store,embedding,DeniedCloud(emit))
        server.answers.reconcile_legacy_sources()
        server.authority='127.0.0.1:%d'%server.server_port
        server.origin='http://'+server.authority
        server.bootstrap=None;server.session=secrets.token_hex(24);server.csrf=secrets.token_hex(24)
        self.thread=threading.Thread(target=server.serve_forever,daemon=True)
        self.emit,self.raw=emit,[]
    def start(self):
        self.thread.start();self.emit('candidate_http_start',port=self.server.server_port);return self
    def call(self,path,body=None):
        if not path.startswith('/api/'): raise ValueError('only local API paths')
        headers={'Cookie':'pkb_session='+self.server.session,'Origin':self.server.origin,'X-PKB-CSRF':self.server.csrf}
        data=None if body is None else json.dumps(body,ensure_ascii=False).encode()
        if data is not None: headers['Content-Type']='application/json'
        request=urllib.request.Request(self.server.origin+path,data=data,headers=headers)
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        try: response=opener.open(request,timeout=10)
        except urllib.error.HTTPError as exc: response=exc
        with response:
            raw=response.read(4*1024*1024);status=response.status;response_headers=dict(response.headers)
        result=json.loads(raw)
        self.raw.append({'path':path,'request':body,'status':status,'headers':response_headers,'body_raw_utf8':raw.decode(),'body':result})
        if response_headers.get('Cache-Control')!='no-store': raise AssertionError('API permits stale caching')
        self.emit('candidate_api_response',path=path,status=status)
        return status,result
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)
        if self.thread.is_alive(): raise RuntimeError('HTTP server did not stop')
        self.emit('candidate_http_stop')
