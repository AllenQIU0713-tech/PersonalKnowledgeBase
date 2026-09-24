import argparse
import fcntl
import base64
import hmac
import json
import mimetypes
import secrets
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import MAX_REQUEST, data_directory
from .store import Store
from .extract import Extractor
from .embedding import Embeddings
from .answers import Answers
from .memories import Memories

STATIC = Path(__file__).parent / 'static'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Request URLs and user data must not enter ordinary logs.

    def respond(self, status, data, content_type='application/json; charset=utf-8', headers=None):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def authenticated(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            token = cookie['pkb_session'].value if 'pkb_session' in cookie else ''
            return hmac.compare_digest(token, self.server.session)
        except Exception:
            return False

    def route(self):
        if self.headers.get('Host') != self.server.authority:
            return self.respond(403, {'error': '只允许本机地址访问'})
        origin = self.headers.get('Origin')
        if origin and origin != self.server.origin:
            return self.respond(403, {'error': '拒绝跨站请求'})
        if self.headers.get('Sec-Fetch-Site') in ('cross-site', 'same-site'):
            return self.respond(403, {'error': '拒绝跨站请求'})
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        if path == '/unlock' and self.command == 'GET':
            supplied = urllib.parse.parse_qs(parsed.query).get('token', [''])[0]
            with self.server.store.lock:
                if not self.server.bootstrap or not hmac.compare_digest(supplied, self.server.bootstrap):
                    return self.respond(403, {'error': '启动链接已失效，请重启服务获取新链接'})
                self.server.bootstrap = None
            return self.respond(303, b'', headers={'Location': '/', 'Set-Cookie': 'pkb_session=' + self.server.session + '; HttpOnly; SameSite=Strict; Path=/'})
        if not self.authenticated():
            return self.respond(401, {'error': '请使用终端显示的启动链接打开知识库'})
        body = {}
        if self.command == 'POST':
            if origin != self.server.origin or not hmac.compare_digest(self.headers.get('X-PKB-CSRF', ''), self.server.csrf):
                return self.respond(403, {'error': '会话校验失败，请刷新页面'})
            if self.headers.get('Transfer-Encoding') or self.headers.get_content_type() != 'application/json':
                return self.respond(400, {'error': '请求格式无效'})
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_REQUEST:
                return self.respond(413, {'error': '请求过大或为空'})
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError('请求必须是 JSON 对象')
        store = self.server.store
        if self.command == 'GET' and path in ('/', '/app.js', '/style.css'):
            file = STATIC / ('index.html' if path == '/' else path[1:])
            return self.respond(200, file.read_bytes(), (mimetypes.guess_type(str(file))[0] or 'text/plain') + '; charset=utf-8')
        if path == '/api/session' and self.command == 'GET':
            return self.respond(200, {'csrf': self.server.csrf, 'data_dir': str(store.root), 'semantic': self.server.embeddings.status(), 'cloud': False})
        if path == '/api/cleanup' and self.command == 'GET':
            return self.respond(200, {'items': store.pending_deletions()})
        if path == '/api/memories' and self.command == 'GET':
            return self.respond(200, {'items': self.server.memories.list()})
        if path == '/api/memories' and self.command == 'POST':
            return self.respond(201, self.server.memories.save(body))
        if path == '/api/memories/update' and self.command == 'POST':
            return self.respond(200, self.server.memories.save(body, body.get('id')))
        if path == '/api/memories/delete' and self.command == 'POST':
            self.server.memories.delete(body.get('id'))
            return self.respond(200, {'deleted': body.get('id')})
        if path == '/api/answers/preview' and self.command == 'POST':
            with store.lock:
                return self.respond(200, self.server.answers.context(body.get('question')))
        if path == '/api/answers/generate' and self.command == 'POST':
            return self.respond(200, self.server.answers.generate(body.get('question'), body.get('provider')))
        if path == '/api/answers' and self.command == 'GET':
            return self.respond(200, {'items': self.server.answers.history()})
        if path == '/api/outbound' and self.command == 'GET':
            return self.respond(200, {'items': self.server.answers.records()})
        if path == '/api/images/preview' and self.command == 'POST':
            item = store.get(body.get('document_id'))
            if item['privacy'] != 'allowed':
                raise ValueError('禁止外发资料不能进行云端图片理解')
            return self.respond(200, {'enabled': False, 'reason': '真实云端图片服务未配置，当前不会发送图片', 'document_id': item['id']})
        if path == '/api/documents' and self.command == 'GET':
            query = urllib.parse.parse_qs(parsed.query)
            args = {k: query.get(k, [''])[0] for k in ('query', 'tag', 'since', 'until')}
            return self.respond(200, {'items': self.server.embeddings.search(**args), 'semantic': self.server.embeddings.status()})
        if path == '/api/documents' and self.command == 'POST':
            data = base64.b64decode(body.get('data', ''), validate=True)
            item = store.add(body.get('title', ''), body.get('filename', 'note.txt'), data,
                             body.get('privacy', 'allowed'), body.get('tags', []), body.get('event_time', ''))
            self.server.extractor.enqueue(item['id'])
            return self.respond(201, store.get(item['id']))
        parts = path.strip('/').split('/')
        if len(parts) >= 3 and parts[:2] == ['api', 'documents']:
            identifier = parts[2]
            if len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
                raise KeyError('资料不存在')
            if len(parts) == 3 and self.command == 'GET':
                return self.respond(200, store.get(identifier))
            if len(parts) == 4 and parts[3] == 'original' and self.command == 'GET':
                item = store.get(identifier)
                return self.respond(200, (store.root / 'originals' / identifier).read_bytes(), 'application/octet-stream',
                                    {'Content-Disposition': "attachment; filename*=UTF-8''" + urllib.parse.quote(item['filename'], safe='')})
            if len(parts) == 4 and parts[3] == 'retry' and self.command == 'POST':
                return self.respond(200, self.server.extractor.enqueue(identifier))
            if len(parts) == 4 and parts[3] == 'delete' and self.command == 'POST':
                return self.respond(200, store.delete(identifier))
            if len(parts) == 4 and parts[3] == 'privacy' and self.command == 'POST':
                return self.respond(200, store.update_privacy(identifier, body.get('privacy')))
        return self.respond(404, {'error': '未找到接口'})

    def handle_request(self):
        try:
            self.connection.settimeout(30)
            self.route()
        except KeyError:
            self.respond(404, {'error': '资料不存在'})
        except (ValueError, TypeError, UnicodeError) as exc:
            self.respond(400, {'error': str(exc)[:300]})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception:
            self.respond(500, {'error': '本地处理失败，原有资料未主动删除；请重试或联系开发排查'})

    do_GET = handle_request
    do_POST = handle_request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--embedding-port', type=int)
    parser.add_argument('--embedding-model', default='')
    args = parser.parse_args()
    root = data_directory(args.data_dir)
    process_lock = (root / '.process.lock').open('a')
    try:
        fcntl.flock(process_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('同一资料目录已有服务或备份操作运行')
    store = Store(root)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.store = store
    server.extractor = Extractor(store)
    server.embeddings = Embeddings(store, args.embedding_port, args.embedding_model)
    server.answers = Answers(store, server.embeddings)
    server.memories = Memories(store)
    server.answers.memories = server.memories
    server.authority = '127.0.0.1:' + str(server.server_port)
    server.origin = 'http://' + server.authority
    server.bootstrap, server.session, server.csrf = (secrets.token_urlsafe(32) for _ in range(3))
    print('资料目录：' + str(store.root), flush=True)
    print('请用浏览器打开（一次性链接）：' + server.origin + '/unlock?token=' + server.bootstrap, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.extractor.stop.set()
        server.embeddings.stop.set()
        server.server_close()
        process_lock.close()


if __name__ == '__main__':
    main()
