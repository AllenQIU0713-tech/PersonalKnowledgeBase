import hashlib
import json
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from .config import MAX_FILE, MIN_FREE


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid.uuid4().hex


class Store:
    def __init__(self, root):
        self.root = root
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, filename TEXT NOT NULL,
                    privacy TEXT NOT NULL, tags TEXT NOT NULL, event_time TEXT NOT NULL,
                    created TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
                    status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '');
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL, page INTEGER, text TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
                CREATE TABLE IF NOT EXISTS tombstones (id TEXT PRIMARY KEY, deleted TEXT NOT NULL);
            ''')

    def connect(self):
        db = sqlite3.connect(str(self.root / 'knowledge.sqlite3'), timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def add(self, title, filename, data, privacy='allowed', tags=None, event_time=''):
        if privacy not in ('allowed', 'local'):
            raise ValueError('隐私级别无效')
        if len(data) > MAX_FILE:
            raise ValueError('单文件最多 25 MiB')
        if not isinstance(tags, list) or any(not isinstance(t, str) or len(t) > 80 for t in tags) or len(tags) > 30:
            raise ValueError('标签格式无效（最多 30 个，每个 80 字）')
        if not isinstance(title, str) or not title.strip() or len(title) > 300:
            raise ValueError('标题须为 1–300 字')
        if not isinstance(filename, str) or len(filename) > 500:
            raise ValueError('文件名无效')
        if event_time:
            datetime.fromisoformat(event_time)
        with self.lock:
            if shutil.disk_usage(self.root).free < len(data) + MIN_FREE:
                raise ValueError('磁盘空间不足，请至少保留 128 MiB')
            identifier = uid()
            path = self.root / 'originals' / identifier
            path.write_bytes(data)
            path.chmod(0o600)
            try:
                text = None
                status, error = 'unparsed', ''
                if filename.lower().endswith(('.txt', '.md', '.markdown', '.csv', '.json')):
                    try:
                        text = data.decode('utf-8-sig')
                        status = 'ready'
                    except UnicodeError:
                        status, error = 'failed', '无法按 UTF-8 解析，可转换编码后重新导入；原件已保留'
                with self.connect() as db:
                    db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                               (identifier, title.strip(), filename, privacy, json.dumps(tags, ensure_ascii=False),
                                event_time, now(), hashlib.sha256(data).hexdigest(), len(data), status, error))
                    if text is not None:
                        self.set_chunks(db, identifier, [(None, text)])
            except Exception:
                path.unlink(missing_ok=True)
                raise
            return self.get(identifier)

    def set_chunks(self, db, identifier, pages):
        db.execute('DELETE FROM chunks WHERE document_id=?', (identifier,))
        position = 0
        for page, text in pages:
            for start in range(0, len(text), 700):
                part = text[start:start + 800]
                if not part.strip():
                    continue
                position += 1
                db.execute('INSERT INTO chunks VALUES (?,?,?,?,?)', (uid(), identifier, position, page, part))

    @staticmethod
    def unpack(row):
        item = dict(row)
        item['tags'] = json.loads(item['tags'])
        return item

    def get(self, identifier):
        with self.connect() as db:
            row = db.execute('SELECT * FROM documents WHERE id=?', (identifier,)).fetchone()
            if row is None:
                raise KeyError('资料不存在')
            item = self.unpack(row)
            item['chunks'] = [dict(r) for r in db.execute('SELECT * FROM chunks WHERE document_id=? ORDER BY position', (identifier,))]
            return item

    def search(self, query='', tag='', since='', until=''):
        if len(query) > 1000:
            raise ValueError('查询最多 1000 字')
        with self.connect() as db:
            rows = db.execute('SELECT * FROM documents ORDER BY created DESC').fetchall()
            results = []
            for row in rows:
                item = self.unpack(row)
                date = (item['event_time'] or item['created'])[:10]
                if tag and tag not in item['tags'] or since and date < since or until and date > until:
                    continue
                chunks = db.execute('SELECT * FROM chunks WHERE document_id=? ORDER BY position', (item['id'],)).fetchall()
                tokens = query.casefold().split()
                metadata = (item['title'] + ' ' + ' '.join(item['tags']) + ' ' + item['filename']).casefold()
                matching = [r for r in chunks if all(t in r['text'].casefold() for t in tokens)]
                if tokens and not matching and not all(t in metadata for t in tokens):
                    continue
                best = matching[0] if matching else (chunks[0] if chunks else None)
                item['excerpt'] = best['text'][:400] if best else '正文尚未解析，可按标题与标签查找'
                item['chunk_id'] = best['id'] if best else None
                item['page'] = best['page'] if best else None
                results.append(item)
                if len(results) >= 100:
                    break
            return results

    def update_privacy(self, identifier, privacy):
        if privacy not in ('allowed', 'local'):
            raise ValueError('隐私级别无效')
        with self.lock, self.connect() as db:
            if not db.execute('SELECT 1 FROM documents WHERE id=?', (identifier,)).fetchone():
                raise KeyError('资料不存在')
            db.execute('UPDATE documents SET privacy=? WHERE id=?', (privacy, identifier))
        return self.get(identifier)

    def delete(self, identifier):
        with self.lock, self.connect() as db:
            db.execute('INSERT OR REPLACE INTO tombstones VALUES (?,?)', (identifier, now()))
            db.execute('DELETE FROM documents WHERE id=?', (identifier,))
        (self.root / 'originals' / identifier).unlink(missing_ok=True)
