"""Frozen observation subclass: exact product route/respond retained, only delay and log."""
import base64,hashlib,json,secrets,threading,time
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from s2r2_http import App,DeniedCloud

class ResponseGates:
    def __init__(self):self.lock=threading.RLock();self.gate=None
    def arm(self,kind,value):
        if kind not in ('query','detail','status'):raise ValueError('invalid fixed gate kind')
        with self.lock:
            if self.gate and not self.gate['release'].is_set():raise ValueError('prior response gate not released')
            self.gate={'kind':kind,'value':value,'arrived':threading.Event(),'release':threading.Event(),'used':False}
    def delay(self,path,emit):
        with self.lock:
            gate=self.gate;url=urlsplit(path)
            match=gate and not gate['used'] and ((gate['kind']=='query' and url.path=='/api/documents/semantic-search' and parse_qs(url.query).get('query')==[gate['value']]) or (gate['kind']=='detail' and url.path=='/api/documents/'+gate['value']) or (gate['kind']=='status' and url.path=='/api/semantic/status'))
            if not match:return
            gate['used']=True;gate['arrived'].set()
        emit('response_gate_arrived',kind=gate['kind'])
        if not gate['release'].wait(25):
            emit('response_gate_hold_timeout',kind=gate['kind'])
            raise TimeoutError('bounded original response gate expired')
    def release(self):
        with self.lock:
            if self.gate:self.gate['release'].set()

def build_handler(ProductHandler,output,gates,emit):
    lock=threading.RLock();counter=[0];navigation_counter=[0]
    def navigation_record(row):
        with lock:
            with open(output/'private-navigation.jsonl','a',opener=lambda p,f:__import__('os').open(p,f,0o600)) as f:
                f.write(json.dumps(row,ensure_ascii=False)+'\n')
    class ObservedHandler(ProductHandler):
        def route(self):
            with lock:counter[0]+=1;self._ar_id=counter[0]
            self._ar_started=time.time_ns()
            # Observe only an actual owned test navigation; never Cookie/Auth or URL query.
            with lock:
                self._ar_navigation=urlsplit(self.path).path in ('/unlock','/') and navigation_counter[0]<16
                if self._ar_navigation:navigation_counter[0]+=1
            if self._ar_navigation:
                authority=self.headers.get('Host','')
                origin=self.headers.get('Origin','')
                try:
                    parsed_origin=urlsplit(origin)
                    safe_origin=(parsed_origin.scheme+'://'+parsed_origin.netloc) if origin and parsed_origin.scheme and parsed_origin.netloc and not parsed_origin.username and not parsed_origin.password and not parsed_origin.path and not parsed_origin.query and not parsed_origin.fragment else ('<non-origin omitted>' if origin else '')
                except ValueError:safe_origin='<invalid-origin omitted>'
                observation={'request_id':self._ar_id,'time_ns':self._ar_started,'path':urlsplit(self.path).path,'method':self.command,
                    'headers':{'Host':authority[:256] if '/' not in authority and '@' not in authority and '?' not in authority else '<non-authority omitted>',
                               'Origin':safe_origin[:256],
                               **{name:(self.headers.get(name,'') if self.headers.get(name,'') in allowed else '<unknown-value omitted>') for name,allowed in {'Sec-Fetch-Site':('','none','same-origin','same-site','cross-site'),'Sec-Fetch-Mode':('','navigate','cors','no-cors','same-origin','websocket'),'Sec-Fetch-Dest':('','document','empty','iframe','script','style','image','font','object','embed','worker')}.items()}},
                    'origin_present':bool(origin),'origin_matches_server':origin==self.server.origin if origin else None,
                    'host_matches_server':authority==self.server.authority,
                    'fetch_site_rejected_by_original_policy':self.headers.get('Sec-Fetch-Site') in ('cross-site','same-site')}
                with lock:
                    with open(output/'private-navigation.jsonl','a',opener=lambda p,f:__import__('os').open(p,f,0o600)) as f:f.write(json.dumps(observation,ensure_ascii=False)+'\n')
            original_reader=getattr(self,'rfile',None);chunks=[]
            class Reader:
                def read(inner,*args,**kwargs):
                    data=original_reader.read(*args,**kwargs);chunks.append(data);return data
                def __getattr__(inner,name):return getattr(original_reader,name)
            if original_reader is not None:self.rfile=Reader()
            try:return super().route()
            finally:
                if original_reader is not None:self.rfile=original_reader
                if chunks:
                    raw=b''.join(chunks);p=Path(output)/'private-request-bodies.jsonl'
                    with lock:
                        if not p.exists():p.touch(mode=0o600)
                        with p.open('a') as f:f.write(json.dumps({'request_id':self._ar_id,'path':self.path,'body_prefix_base64':base64.b64encode(raw[:262144]).decode(),'body_sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'truncated':len(raw)>262144})+'\n')
        def respond(self,status,data,content_type='application/json; charset=utf-8',headers=None):
            if getattr(self,'_ar_navigation',False):
                reason=data.get('error') if isinstance(data,dict) else None
                if reason not in ('拒绝跨站请求','只允许本机地址访问','启动链接已失效，请重启服务获取新链接','请使用终端显示的启动链接打开知识库'):reason=None
                response_headers=headers or {}
                cookie=SimpleCookie()
                try:cookie.load(response_headers.get('Set-Cookie',''))
                except Exception:cookie=SimpleCookie()
                session_cookie=cookie.get('pkb_session')
                navigation_record({'request_id':self._ar_id,'time_ns':time.time_ns(),'path':urlsplit(self.path).path,'status':status,'reason':reason,'event':'original_navigation_response',
                    'location_present':'Location' in response_headers,'location_is_root':response_headers.get('Location')=='/',
                    'set_cookie_present':'Set-Cookie' in response_headers,
                    'session_cookie_attributes_match':bool(session_cookie and session_cookie['httponly'] and session_cookie['samesite'].lower()=='strict' and session_cookie['path']=='/')})
            if self.path.startswith('/api/'):
                raw=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode('utf-8')
                row={'body_raw_utf8':raw.decode('utf-8',errors='replace'),'request_id':getattr(self,'_ar_id',None),'method':self.command,'path':self.path,'received_ns':getattr(self,'_ar_started',None),'response_ready_ns':time.time_ns(),'status':status,'content_type':content_type,'body':data.decode('utf-8',errors='replace') if isinstance(data,bytes) else data}
                private=self.path=='/api/session'
                p=Path(output)/('private-session-response.jsonl' if private else 'server-api.jsonl')
                with lock:
                    if private and not p.exists():p.touch(mode=0o600)
                    with p.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
                gates.delay(self.path,emit)
            try:
                value=super().respond(status,data,content_type,headers)
            except Exception as exc:
                if getattr(self,'_ar_navigation',False):
                    # Preserve the original failure even if the observer itself cannot write.
                    try:
                        navigation_record({'request_id':self._ar_id,'time_ns':time.time_ns(),'path':urlsplit(self.path).path,'status':status,
                            'event':'original_navigation_response_exception','client_receipt_verified':False,
                            'exception_type':type(exc).__name__ if type(exc).__name__ in ('BrokenPipeError','ConnectionResetError','TimeoutError','OSError','ValueError','RuntimeError') else 'OtherException'})
                    except Exception:
                        self._ar_navigation_observation_failed=True
                        try:emit('navigation_observation_failed',request_id=self._ar_id,stage='response_exception')
                        except Exception:pass
                raise
            if getattr(self,'_ar_navigation',False):
                navigation_record({'request_id':self._ar_id,'time_ns':time.time_ns(),'path':urlsplit(self.path).path,'status':status,
                    'event':'original_navigation_response_call_returned','client_receipt_verified':False})
            if self.path.startswith('/api/'):emit('original_response_sent',request_id=getattr(self,'_ar_id',None),status=status)
            return value
    return ObservedHandler

class ObservedApp(App):
    def __init__(self,store,embedding,modules,output,gates,emit):
        Handler,Answers,Extractor=modules
        server=self.server=ThreadingHTTPServer(('127.0.0.1',18471),build_handler(Handler,output,gates,emit));server.daemon_threads=True
        try:
            server.store,server.embeddings=store,embedding
            server.answers=Answers(store,embedding,DeniedCloud(emit));server.answers.reconcile_legacy_sources()
            server.extractor=Extractor(store)
            server.authority='127.0.0.1:18471';server.origin='http://'+server.authority
            server.bootstrap=secrets.token_urlsafe(32);server.session=secrets.token_hex(24);server.csrf=secrets.token_hex(24)
            self.thread=threading.Thread(target=server.serve_forever,daemon=True);self.emit,self.raw=emit,[]
        except BaseException:
            if getattr(server,'extractor',None):server.extractor.stop.set();server.extractor.thread.join(timeout=5)
            server.server_close()
            raise
