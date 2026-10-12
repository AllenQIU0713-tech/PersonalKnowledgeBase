import hashlib
import json
import shutil
import sqlite3
import threading
import uuid
import unicodedata
from datetime import date, datetime, timezone
import re

from .config import MAX_FILE, MIN_FREE

BUSINESS_TOKEN = re.compile(
    r'(?<![a-z0-9_-])[a-z0-9]+(?:[-_][a-z0-9]+)*(?![a-z0-9_-])')


def business_ids(text):
    normalized = unicodedata.normalize('NFKC', text).casefold()
    return {token for token in BUSINESS_TOKEN.findall(normalized)
            if any('a' <= char <= 'z' for char in token)
            and any(char.isdigit() for char in token)}


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
                CREATE TABLE IF NOT EXISTS pending_cleanup (id TEXT PRIMARY KEY, filename TEXT NOT NULL, error TEXT NOT NULL, created TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS document_metadata (
                    document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
                    source_type TEXT NOT NULL, legacy_id TEXT UNIQUE,
                    legacy_status TEXT NOT NULL, legacy_origin TEXT NOT NULL,
                    original_created TEXT NOT NULL, original_updated TEXT NOT NULL,
                    question_state TEXT NOT NULL, question_reason TEXT NOT NULL,
                    content_version INTEGER NOT NULL, qualification_version INTEGER NOT NULL,
                    updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS document_sources (
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    source_document_id TEXT NOT NULL, relation TEXT NOT NULL,
                    PRIMARY KEY(document_id,source_document_id));
                CREATE TABLE IF NOT EXISTS legacy_restore_sources (
                    memory_id TEXT NOT NULL, source_document_id TEXT NOT NULL,
                    PRIMARY KEY(memory_id,source_document_id));
                CREATE TABLE IF NOT EXISTS legacy_memory_map (
                    memory_id TEXT PRIMARY KEY, document_id TEXT NOT NULL UNIQUE,
                    snapshot TEXT NOT NULL, migrated TEXT NOT NULL,
                    question_state TEXT NOT NULL, reason TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS single_library_migrations (
                    name TEXT PRIMARY KEY, started TEXT NOT NULL, completed TEXT NOT NULL,
                    status TEXT NOT NULL, backup_path TEXT NOT NULL, backup_sha256 TEXT NOT NULL,
                    source_count INTEGER NOT NULL, migrated_count INTEGER NOT NULL,
                    blocked_count INTEGER NOT NULL, manifest TEXT NOT NULL);
            ''')
            stamp = now()
            db.execute('''INSERT OR IGNORE INTO document_metadata
                SELECT id,'collected',NULL,'','',created,created,'ready','',1,1,?
                FROM documents''', (stamp,))

        self.recover_deletions()

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
        if not isinstance(event_time, str):
            raise ValueError('事件日期须为 YYYY-MM-DD 字符串，未填写时使用空字符串')
        if event_time:
            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', event_time):
                raise ValueError('事件日期须为 YYYY-MM-DD')
            try:
                date.fromisoformat(event_time)
            except ValueError:
                raise ValueError('事件日期不是有效日期')
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
                    db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                               (identifier, title.strip(), filename, privacy, json.dumps(tags, ensure_ascii=False),
                                event_time, now(), hashlib.sha256(data).hexdigest(), len(data), status, error))
                    stamp = now()
                    db.execute('INSERT INTO document_metadata VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                               (identifier,'collected',None,'','',stamp,stamp,'ready','',1,1,stamp))
                    if text is not None:
                        self.set_chunks(db, identifier, [(None, text)])
            except Exception:
                path.unlink(missing_ok=True)
                raise
            return self.get(identifier)

    def set_chunks(self, db, identifier, pages):
        self.clean_answers(db, identifier)
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='semantic_vectors'").fetchone():
            db.execute('DELETE FROM semantic_vectors WHERE document_id=?', (identifier,))
        db.execute('DELETE FROM chunks WHERE document_id=?', (identifier,))
        position = 0
        for page, text in pages:
            for start in range(0, len(text), 700):
                part = text[start:start + 800]
                if not part.strip():
                    continue
                position += 1
                db.execute('INSERT INTO chunks VALUES (?,?,?,?,?)', (uid(), identifier, position, page, part))
        db.execute('''UPDATE document_metadata SET content_version=content_version+1,
                      qualification_version=qualification_version+1,updated=? WHERE document_id=?''',
                   (now(), identifier))

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
            metadata = db.execute('SELECT * FROM document_metadata WHERE document_id=?',
                                  (identifier,)).fetchone()
            if metadata:
                item.update({key: value for key, value in dict(metadata).items()
                             if key != 'document_id'})
            item['source_ids'] = [row[0] for row in db.execute(
                'SELECT source_document_id FROM document_sources WHERE document_id=? ORDER BY source_document_id',
                (identifier,))]
            legacy = db.execute('SELECT snapshot FROM legacy_memory_map WHERE document_id=?',
                                (identifier,)).fetchone()
            item['legacy_snapshot'] = json.loads(legacy[0]) if legacy else None
            item['chunks'] = [dict(r) for r in db.execute('SELECT * FROM chunks WHERE document_id=? ORDER BY position', (identifier,))]
            return item

    def question_eligible(self, db, identifier, seen=None):
        seen = set(seen or ())
        if identifier in seen:
            return False, '资料来源关系形成循环'
        branch = seen | {identifier}
        row = db.execute('''SELECT d.privacy,d.status,m.question_state,m.question_reason
                            FROM documents d JOIN document_metadata m ON m.document_id=d.id
                            WHERE d.id=?''', (identifier,)).fetchone()
        if not row:
            return False, '资料不存在或来源已删除'
        if row['privacy'] != 'allowed':
            return False, '资料被设为禁止外发'
        if row['status'] != 'ready':
            return False, '资料正文尚未解析完成'
        if row['question_state'] != 'ready':
            return False, row['question_reason'] or '资料尚未允许用于提问'
        for source in db.execute(
                'SELECT source_document_id FROM document_sources WHERE document_id=?',
                (identifier,)):
            allowed, reason = self.question_eligible(db, source[0], branch)
            if not allowed:
                return False, '来源不可用于提问：' + reason
        return True, ''

    def locally_browsable(self, db, identifier, seen=None):
        """Allow parsed local browsing while excluding missing sources and deleted rows."""
        seen = set(seen or ())
        if identifier in seen:
            return False, '资料来源关系形成循环'
        branch = seen | {identifier}
        row = db.execute('''SELECT d.status FROM documents d
                            WHERE d.id=? AND NOT EXISTS (
                                SELECT 1 FROM tombstones t WHERE t.id=d.id)''',
                         (identifier,)).fetchone()
        if not row:
            return False, '资料不存在或已删除'
        if row['status'] != 'ready':
            return False, '资料正文尚未解析完成'
        for source in db.execute(
                'SELECT source_document_id FROM document_sources WHERE document_id=?',
                (identifier,)):
            allowed, reason = self.locally_browsable(db, source[0], branch)
            if not allowed:
                return False, '来源不可用于本地语义查找：' + reason
        return True, ''

    def invalidate_document(self, db, identifier, qualification=True):
        self.clean_answers(db, identifier)
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='semantic_vectors'").fetchone():
            db.execute('DELETE FROM semantic_vectors WHERE document_id=?', (identifier,))
        if qualification:
            db.execute('''UPDATE document_metadata
                          SET qualification_version=qualification_version+1,updated=?
                          WHERE document_id=?''', (now(), identifier))

    def refresh_dependents(self, db, identifier):
        queue, seen = [identifier], set()
        while queue:
            source = queue.pop(0)
            for row in db.execute('''SELECT document_id FROM document_sources
                                     WHERE source_document_id=?''', (source,)).fetchall():
                dependent = row[0]
                if dependent in seen:
                    continue
                seen.add(dependent)
                allowed, reason = self.question_eligible(db, dependent)
                self.invalidate_document(db, dependent)
                if not allowed:
                    source_privacy = db.execute('SELECT privacy FROM documents WHERE id=?',
                                                (source,)).fetchone()
                    if source_privacy and source_privacy[0] == 'local':
                        db.execute("UPDATE documents SET privacy='local' WHERE id=?", (dependent,))
                    db.execute('''UPDATE document_metadata SET question_reason=?,updated=?
                                  WHERE document_id=?''', (reason, now(), dependent))
                else:
                    db.execute('''UPDATE document_metadata SET question_reason='',updated=?
                                  WHERE document_id=?''', (now(), dependent))
                queue.append(dependent)

    def set_question_state(self, identifier, state):
        if state not in ('ready', 'inactive'):
            raise ValueError('资料提问状态无效')
        with self.lock, self.connect() as db:
            row = db.execute('SELECT source_type FROM document_metadata WHERE document_id=?',
                             (identifier,)).fetchone()
            if not row:
                raise KeyError('资料不存在')
            if state == 'ready':
                db.execute("UPDATE document_metadata SET question_state='ready',question_reason='' WHERE document_id=?",
                           (identifier,))
                allowed, reason = self.question_eligible(db, identifier)
                if not allowed:
                    db.execute("UPDATE document_metadata SET question_state='inactive',question_reason=? WHERE document_id=?",
                               (reason, identifier))
                    raise ValueError(reason)
            else:
                db.execute("UPDATE document_metadata SET question_state='inactive',question_reason='用户已停用' WHERE document_id=?",
                           (identifier,))
            self.invalidate_document(db, identifier)
            self.refresh_dependents(db, identifier)
        return self.get(identifier)

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
                identifiers = business_ids(query)
                if identifiers:
                    document_ids = business_ids(metadata + '\n' + '\n'.join(r['text'] for r in chunks))
                    if not identifiers.intersection(document_ids):
                        continue
                elif tokens and not matching and not all(t in metadata for t in tokens):
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
            if privacy == 'allowed' and db.execute('''SELECT 1 FROM document_sources s
                    JOIN documents d ON d.id=s.source_document_id
                    WHERE s.document_id=? AND d.privacy='local' LIMIT 1''',
                    (identifier,)).fetchone():
                raise ValueError('来源资料禁止外发，该资料不能放宽隐私设置')
            db.execute('UPDATE documents SET privacy=? WHERE id=?', (privacy, identifier))
            self.invalidate_document(db, identifier)
            self.refresh_dependents(db, identifier)
        return self.get(identifier)

    def update_text(self, identifier, title, text, tags):
        if not isinstance(title, str) or not title.strip() or len(title) > 300:
            raise ValueError('标题须为 1–300 字')
        if not isinstance(text, str) or not text.strip():
            raise ValueError('正文须为 1 字以上且不超过 25 MiB')
        if (not isinstance(tags, list) or len(tags) > 30 or
                any(not isinstance(tag, str) or len(tag) > 80 for tag in tags)):
            raise ValueError('标签格式无效（最多 30 个，每个 80 字）')
        data = text.encode()
        if len(data) > MAX_FILE:
            raise ValueError('正文须为 1 字以上且不超过 25 MiB')
        with self.lock, self.connect() as db:
            row = db.execute('SELECT filename FROM documents WHERE id=?',
                             (identifier,)).fetchone()
            if not row:
                raise KeyError('资料不存在')
            if not row['filename'].lower().endswith(('.txt','.md','.markdown','.csv','.json')):
                raise ValueError('当前只支持直接修改文字资料正文')
            original = self.root / 'originals' / identifier
            previous_data = original.read_bytes()
            partial = original.with_name(identifier + '.update')
            partial.write_bytes(data)
            partial.chmod(0o600)
            try:
                partial.replace(original)
                db.execute('''UPDATE documents SET title=?,tags=?,sha256=?,size=?,status='ready',error=''
                              WHERE id=?''',
                           (title.strip(), json.dumps(tags, ensure_ascii=False),
                            hashlib.sha256(data).hexdigest(), len(data), identifier))
                self.set_chunks(db, identifier, [(None, text)])
                self.refresh_dependents(db, identifier)
                db.commit()
            except Exception:
                original.write_bytes(previous_data)
                original.chmod(0o600)
                raise
            finally:
                partial.unlink(missing_ok=True)
        return self.get(identifier)

    def delete(self, identifier):
        if not isinstance(identifier,str) or len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):
            raise ValueError('资料标识无效')
        with self.lock, self.connect() as db:
            row = db.execute('SELECT filename FROM documents WHERE id=?',(identifier,)).fetchone()
            db.execute('INSERT OR IGNORE INTO pending_cleanup VALUES (?,?,?,?)',(identifier,row['filename'] if row else '待清理原件','',now()))
            self.clean_answers(db, identifier)
            db.execute('INSERT OR REPLACE INTO tombstones VALUES (?,?)', (identifier, now()))
            db.execute('DELETE FROM documents WHERE id=?', (identifier,))
            self.refresh_dependents(db, identifier)
        return self.finish_delete(identifier)

    def finish_delete(self, identifier):
        with self.lock:
            try:
                (self.root / 'originals' / identifier).unlink(missing_ok=True)
            except OSError:
                with self.connect() as db:
                    db.execute('INSERT OR REPLACE INTO pending_cleanup VALUES (?,?,?,?)',
                               (identifier,'待清理原件','原件清理失败，请检查目录权限后重试；该资料已禁止检索和下载',now()))
                return {'deleted':identifier,'cleanup_pending':True}
            with self.connect() as db:
                db.execute('DELETE FROM pending_cleanup WHERE id=?',(identifier,))
            return {'deleted':identifier,'cleanup_pending':False}

    def recover_deletions(self):
        with self.connect() as db:
            identifiers = [r[0] for r in db.execute('SELECT id FROM tombstones')]
        for identifier in identifiers:
            if isinstance(identifier,str) and len(identifier)==32 and all(c in '0123456789abcdef' for c in identifier):
                self.finish_delete(identifier)

    def pending_deletions(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM pending_cleanup ORDER BY created')]

    def clean_answers(self, db, identifier):
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='answers'").fetchone():
            return
        answer_ids = [r[0] for r in db.execute('SELECT answer_id FROM answer_sources WHERE document_id=?', (identifier,))]
        chunk_ids = {r[0] for r in db.execute('SELECT id FROM chunks WHERE document_id=?', (identifier,))}
        for answer_id in answer_ids:
            db.execute('DELETE FROM answers WHERE id=?', (answer_id,))
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='legacy_memory_map'").fetchone():
            legacy = db.execute('SELECT memory_id FROM legacy_memory_map WHERE document_id=?',
                                (identifier,)).fetchone()
            if legacy and db.execute("SELECT 1 FROM sqlite_master WHERE name='answer_memories'").fetchone():
                for row in db.execute('SELECT answer_id FROM answer_memories WHERE memory_id=?',
                                      (legacy[0],)).fetchall():
                    db.execute('DELETE FROM answers WHERE id=?', (row[0],))
        for row in db.execute('SELECT id,identifiers FROM outbound').fetchall():
            if chunk_ids.intersection(json.loads(row['identifiers'])):
                db.execute('DELETE FROM outbound WHERE id=?', (row['id'],))
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='cloud_requests'").fetchone():
            for row in db.execute('SELECT id,identifiers FROM cloud_requests').fetchall():
                if chunk_ids.intersection(json.loads(row['identifiers'])):
                    db.execute('DELETE FROM cloud_requests WHERE id=?', (row['id'],))

    def clean_memories(self, db, identifier):
        # Legacy memory rows are recovery evidence. Source changes invalidate the
        # migrated document through document_sources; old tables stay read-only.
        self.refresh_dependents(db, identifier)
