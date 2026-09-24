"""Local llama.cpp adapter. Never contacts a non-loopback host."""
import hashlib
import json
import math
import threading
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('本地模型不允许重定向')


class Embeddings:
    def __init__(self, store, port=None, model=''):
        self.store, self.port, self.model = store, port, model
        if port is not None and (not 1 <= port <= 65535 or not model):
            raise ValueError('请指定有效的本地向量端口和模型 SHA256 标识')
        self.signature = hashlib.sha256(('qwen3:last:query-v1:' + model).encode()).hexdigest()
        self.error = ''
        self.stop = threading.Event()
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS vectors (chunk_id TEXT PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE, signature TEXT NOT NULL, vector TEXT NOT NULL)')
            if port:
                db.execute('DELETE FROM vectors WHERE signature<>?', (self.signature,))
        if port:
            threading.Thread(target=self.work, daemon=True).start()

    def encode(self, text, query=False):
        if query:
            text = 'Instruct: Given a query, retrieve relevant passages that answer the query\nQuery: ' + text
        body = json.dumps({'input': [text], 'model': self.model}).encode()
        request = urllib.request.Request('http://127.0.0.1:%d/v1/embeddings' % self.port, data=body, headers={'Content-Type': 'application/json'})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=30) as response:
            result = json.loads(response.read(2 * 1024 * 1024))
        values = result['data'][0]['embedding']
        if not isinstance(values, list) or not 1 <= len(values) <= 8192 or any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in values):
            raise ValueError('本地模型返回无效向量')
        norm = math.sqrt(sum(v*v for v in values))
        if not norm:
            raise ValueError('本地模型返回零向量')
        return [v/norm for v in values]

    def work(self):
        while not self.stop.is_set():
            with self.store.connect() as db:
                chunk = db.execute('SELECT c.* FROM chunks c LEFT JOIN vectors v ON c.id=v.chunk_id WHERE v.chunk_id IS NULL LIMIT 1').fetchone()
            if not chunk:
                self.stop.wait(2)
                continue
            try:
                vector = self.encode(chunk['text'])
                with self.store.lock, self.store.connect() as db:
                    if db.execute('SELECT 1 FROM chunks WHERE id=?', (chunk['id'],)).fetchone():
                        db.execute('INSERT OR REPLACE INTO vectors VALUES (?,?,?)', (chunk['id'], self.signature, json.dumps(vector)))
                self.error = ''
            except Exception:
                self.error = '本地向量服务不可用或返回无效数据；关键词检索仍可用'
                self.stop.wait(15)

    def status(self):
        with self.store.connect() as db:
            total = db.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]
            indexed = db.execute('SELECT COUNT(*) FROM vectors WHERE signature=?', (self.signature,)).fetchone()[0]
        return {'enabled': bool(self.port), 'model': self.model, 'total': total, 'indexed': indexed, 'error': self.error}

    def search(self, query, tag='', since='', until=''):
        lexical = self.store.search(query, tag, since, until)
        if not self.port or not query.strip():
            return lexical
        try:
            vector = self.encode(query, query=True)
            with self.store.connect() as db:
                rows = db.execute('SELECT c.*, v.vector FROM vectors v JOIN chunks c ON c.id=v.chunk_id WHERE v.signature=?', (self.signature,)).fetchall()
            scored = []
            for row in rows:
                other = json.loads(row['vector'])
                if len(other) != len(vector):
                    raise ValueError('向量维度不一致')
                scored.append((sum(a*b for a,b in zip(vector,other)),row))
            scores, items = {}, {}
            for rank, item in enumerate(lexical):
                scores[item['id']] = 1/(60+rank+1)
                items[item['id']] = item
            rank = 0
            seen = set()
            for similarity, row in sorted(scored,key=lambda r:r[0],reverse=True):
                identifier = row['document_id']
                if identifier in seen:
                    continue
                item = self.store.get(identifier)
                date = (item['event_time'] or item['created'])[:10]
                if tag and tag not in item['tags'] or since and date < since or until and date > until:
                    continue
                seen.add(identifier)
                rank += 1
                if rank > 40:
                    break
                scores[identifier] = scores.get(identifier,0)+1/(60+rank)
                item.pop('chunks', None)
                item.update(excerpt=row['text'][:400], chunk_id=row['id'], page=row['page'])
                items.setdefault(identifier,item)
            self.error = ''
            return [items[k] for k in sorted(scores,key=scores.get,reverse=True)][:100]
        except Exception:
            self.error = '语义检索不可用，当前结果仅使用关键词'
            return lexical
