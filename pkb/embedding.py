"""Versioned local semantic index. It never contacts a non-loopback host."""
import hashlib
import json
import math
import re
import threading
import unicodedata
import urllib.error
import urllib.request

from .store import now

PASSAGE_TEMPLATE_VERSION = 'single-library-passage-v1'
QUERY_TEMPLATE_VERSION = 'qwen3-query-v1'
QUERY_INSTRUCTION = 'Given a query, retrieve relevant passages that answer the query'
POOLING = 'last'
RRF_K = 60
MAX_SEMANTIC_CANDIDATES = 40
MAX_RESULTS = 6
MAX_PER_DOCUMENT = 2
APPROVED_MODEL_SHA256 = '06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439'
BUSINESS_TOKEN = re.compile(
    r'(?<![a-z0-9_-])[a-z0-9]+(?:[-_][a-z0-9]+)*(?![a-z0-9_-])')


class SemanticUnavailable(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('本地模型不允许重定向')


def _normalized(text):
    return unicodedata.normalize('NFKC', text).casefold()


def _business_ids(text):
    tokens = BUSINESS_TOKEN.findall(_normalized(text))
    return {token for token in tokens
            if any('a' <= char <= 'z' for char in token)
            and any(char.isdigit() for char in token)}


class Embeddings:
    def __init__(self, store, port=None, model=''):
        self.store, self.port, self.model = store, port, model
        if port is not None and (not 1 <= port <= 65535 or not model):
            raise ValueError('请指定有效的本地向量端口和模型 SHA256 标识')
        if model and model != APPROVED_MODEL_SHA256:
            raise ValueError('本版只允许产品固定的 Qwen3-Embedding-0.6B Q8_0 模型')
        signature_text = ':'.join((model, PASSAGE_TEMPLATE_VERSION,
                                   QUERY_TEMPLATE_VERSION, POOLING))
        self.signature = hashlib.sha256(signature_text.encode()).hexdigest()
        self.error = ''
        self.error_state = ''
        self.stop = threading.Event()
        self.worker = None
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS semantic_index_config (
                    id INTEGER PRIMARY KEY CHECK(id=1), signature TEXT NOT NULL,
                    model TEXT NOT NULL, passage_template TEXT NOT NULL,
                    query_template TEXT NOT NULL, pooling TEXT NOT NULL,
                    dimension INTEGER NOT NULL, generation INTEGER NOT NULL,
                    threshold REAL, calibration_report_hash TEXT NOT NULL,
                    revision INTEGER NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS semantic_vectors (
                    chunk_id TEXT PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    source_hash TEXT NOT NULL, content_version INTEGER NOT NULL,
                    qualification_version INTEGER NOT NULL, signature TEXT NOT NULL,
                    dimension INTEGER NOT NULL, generation INTEGER NOT NULL,
                    vector TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS semantic_vectors_document
                    ON semantic_vectors(document_id);
            ''')
            existing = db.execute('SELECT * FROM semantic_index_config WHERE id=1').fetchone()
            if not existing:
                db.execute('INSERT INTO semantic_index_config VALUES (1,?,?,?,?,?,0,1,NULL,\'\',1,?)',
                           (self.signature, model, PASSAGE_TEMPLATE_VERSION,
                            QUERY_TEMPLATE_VERSION, POOLING, now()))
            elif existing['signature'] != self.signature:
                db.execute('DELETE FROM semantic_vectors')
                db.execute('''UPDATE semantic_index_config SET signature=?,model=?,
                    passage_template=?,query_template=?,pooling=?,dimension=0,
                    generation=generation+1,threshold=NULL,calibration_report_hash='',
                    revision=revision+1,updated=? WHERE id=1''',
                           (self.signature, model, PASSAGE_TEMPLATE_VERSION,
                            QUERY_TEMPLATE_VERSION, POOLING, now()))
        if port:
            self._start_worker()

    def _start_worker(self):
        if self.worker and self.worker.is_alive():
            return
        self.worker = threading.Thread(target=self.work, daemon=True)
        self.worker.start()

    @staticmethod
    def passage_text(title, tags, text):
        tags_text = '、'.join(tags)
        return '标题：%s\n标签：%s\n正文：%s' % (title, tags_text, text)

    def encode(self, text, query=False):
        if not self.port:
            raise SemanticUnavailable('本地语义服务未配置')
        if query:
            text = 'Instruct: %s\nQuery: %s' % (QUERY_INSTRUCTION, text)
        body = json.dumps({'input': [text], 'model': self.model}).encode()
        request = urllib.request.Request(
            'http://127.0.0.1:%d/v1/embeddings' % self.port,
            data=body, headers={'Content-Type': 'application/json'})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=30) as response:
            result = json.loads(response.read(2 * 1024 * 1024))
        values = result['data'][0]['embedding']
        if (not isinstance(values, list) or not 1 <= len(values) <= 8192 or
                any(not isinstance(value, (float, int)) or not math.isfinite(value)
                    for value in values)):
            raise ValueError('本地模型返回无效向量')
        norm = math.sqrt(sum(value * value for value in values))
        if not norm:
            raise ValueError('本地模型返回零向量')
        return [value / norm for value in values]

    def _eligible_chunks(self, db):
        rows = []
        for row in db.execute('''SELECT c.*,d.title,d.tags,d.event_time,d.sha256,
                                  m.content_version,m.qualification_version
                                  FROM chunks c JOIN documents d ON d.id=c.document_id
                                  JOIN document_metadata m ON m.document_id=d.id
                                  ORDER BY c.id'''):
            allowed, _ = self.store.question_eligible(db, row['document_id'])
            if allowed:
                rows.append(row)
        return rows

    def _browseable_chunks(self, db):
        rows = []
        for row in db.execute('''SELECT c.*,d.title,d.tags,d.event_time,d.sha256,
                                  m.source_type,m.content_version,m.qualification_version
                                  FROM chunks c JOIN documents d ON d.id=c.document_id
                                  JOIN document_metadata m ON m.document_id=d.id
                                  ORDER BY c.id'''):
            allowed, _ = self.store.locally_browsable(db, row['document_id'])
            if allowed:
                rows.append(row)
        return rows

    def _source_hash(self, row):
        payload = json.dumps({
            'title': row['title'], 'tags': json.loads(row['tags']),
            'text': row['text'], 'chunk_id': row['id'],
            'content_version': row['content_version'],
            'qualification_version': row['qualification_version'],
            'template': PASSAGE_TEMPLATE_VERSION,
        }, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(payload.encode()).hexdigest()

    def _next_pending(self):
        with self.store.connect() as db:
            config = db.execute('SELECT * FROM semantic_index_config WHERE id=1').fetchone()
            browseable = self._browseable_chunks(db)
            valid_ids = {row['id'] for row in browseable}
            if valid_ids:
                marks = ','.join('?' for _ in valid_ids)
                db.execute('DELETE FROM semantic_vectors WHERE chunk_id NOT IN (' + marks + ')',
                           tuple(valid_ids))
            else:
                db.execute('DELETE FROM semantic_vectors')
            for row in browseable:
                source_hash = self._source_hash(row)
                vector = db.execute('SELECT * FROM semantic_vectors WHERE chunk_id=?',
                                    (row['id'],)).fetchone()
                if (not vector or vector['signature'] != self.signature or
                        vector['generation'] != config['generation'] or
                        vector['source_hash'] != source_hash or
                        vector['content_version'] != row['content_version'] or
                        vector['qualification_version'] != row['qualification_version']):
                    return dict(row), source_hash, dict(config)
        return None

    def work(self):
        while not self.stop.is_set():
            pending = self._next_pending()
            if not pending:
                self.stop.wait(2)
                continue
            row, source_hash, config = pending
            try:
                text = self.passage_text(row['title'], json.loads(row['tags']), row['text'])
                vector = self.encode(text)
                with self.store.lock, self.store.connect() as db:
                    current = db.execute('''SELECT c.*,d.title,d.tags,
                        m.content_version,m.qualification_version
                        FROM chunks c JOIN documents d ON d.id=c.document_id
                        JOIN document_metadata m ON m.document_id=d.id WHERE c.id=?''',
                                         (row['id'],)).fetchone()
                    allowed, _ = self.store.locally_browsable(db, row['document_id'])
                    live_config = db.execute(
                        'SELECT * FROM semantic_index_config WHERE id=1').fetchone()
                    if (not current or not allowed or
                            self._source_hash(current) != source_hash or
                            live_config['generation'] != config['generation'] or
                            live_config['signature'] != self.signature):
                        continue
                    dimension = len(vector)
                    if live_config['dimension'] not in (0, dimension):
                        raise ValueError('本地模型向量维度与当前索引不一致')
                    if live_config['dimension'] == 0:
                        db.execute('UPDATE semantic_index_config SET dimension=?,updated=? WHERE id=1',
                                   (dimension, now()))
                    db.execute('INSERT OR REPLACE INTO semantic_vectors VALUES (?,?,?,?,?,?,?,?,?)',
                               (row['id'], row['document_id'], source_hash,
                                row['content_version'], row['qualification_version'],
                                self.signature, dimension, config['generation'],
                                json.dumps(vector)))
                self.error = ''
                self.error_state = ''
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
                self.error = '本地语义服务不可用：' + str(exc)[:180]
                self.error_state = 'service_unavailable'
                self.stop.wait(15)
            except Exception as exc:
                self.error = '本地语义索引失败：' + str(exc)[:180]
                self.error_state = 'index_error'
                self.stop.wait(15)

    def retry(self):
        self.error = ''
        self.error_state = ''
        if self.port:
            self._start_worker()
        return self.status()

    def set_calibration(self, threshold, report_hash):
        if (not isinstance(threshold, (float, int)) or not math.isfinite(threshold)
                or not -1 <= threshold <= 1):
            raise ValueError('余弦门槛必须是 -1 到 1 的有限数值')
        if not isinstance(report_hash, str) or not re.fullmatch(r'[0-9a-f]{64}', report_hash):
            raise ValueError('校准报告 SHA256 无效')
        with self.store.lock, self.store.connect() as db:
            db.execute('''UPDATE semantic_index_config SET threshold=?,calibration_report_hash=?,
                          revision=revision+1,updated=? WHERE id=1''',
                       (float(threshold), report_hash, now()))
        return self.status()

    def status(self):
        with self.store.connect() as db:
            config = dict(db.execute(
                'SELECT * FROM semantic_index_config WHERE id=1').fetchone())
            eligible_rows = self._eligible_chunks(db)
            eligible = len(eligible_rows)
            indexed = 0
            for row in eligible_rows:
                source_hash = self._source_hash(row)
                if db.execute('''SELECT 1 FROM semantic_vectors WHERE chunk_id=?
                    AND signature=? AND generation=? AND source_hash=?
                    AND content_version=? AND qualification_version=?''',
                              (row['id'], self.signature, config['generation'], source_hash,
                               row['content_version'], row['qualification_version'])).fetchone():
                    indexed += 1
            excluded = db.execute('SELECT COUNT(*) FROM chunks').fetchone()[0] - eligible
            excluded_reasons = {'local': 0, 'unparsed': 0, 'restricted': 0, 'no_text': 0}
            for row in db.execute('''SELECT d.id,d.privacy,d.status,m.question_state,
                (SELECT COUNT(*) FROM chunks c WHERE c.document_id=d.id) AS chunk_count
                FROM documents d JOIN document_metadata m ON m.document_id=d.id'''):
                if row['privacy'] != 'allowed':
                    excluded_reasons['local'] += 1
                elif row['status'] != 'ready':
                    excluded_reasons['unparsed'] += 1
                elif row['question_state'] != 'ready':
                    excluded_reasons['restricted'] += 1
                elif not row['chunk_count']:
                    excluded_reasons['no_text'] += 1
            browseable_rows = self._browseable_chunks(db)
            browseable_indexed = 0
            for row in browseable_rows:
                source_hash = self._source_hash(row)
                if db.execute('''SELECT 1 FROM semantic_vectors WHERE chunk_id=?
                    AND signature=? AND generation=? AND source_hash=?
                    AND content_version=? AND qualification_version=?''',
                              (row['id'], self.signature, config['generation'], source_hash,
                               row['content_version'], row['qualification_version'])).fetchone():
                    browseable_indexed += 1
        if not self.port:
            state, reason = 'service_unavailable', '本地语义服务未配置'
        elif self.error_state:
            state, reason = self.error_state, self.error
        elif eligible == 0:
            state, reason = 'no_evidence', '当前没有可用于提问的已解析资料'
        elif indexed < eligible:
            state, reason = 'indexing', '正在建立完整语义索引'
        elif config['threshold'] is None:
            state, reason = 'calibration_required', '当前模型尚未完成余弦门槛校准'
        else:
            state, reason = 'ready', '本地语义检索已就绪'
        if not self.port:
            browse_state = 'service_unavailable'
        elif self.error_state:
            browse_state = self.error_state
        elif not browseable_rows:
            browse_state = 'no_evidence'
        elif browseable_indexed < len(browseable_rows):
            browse_state = 'indexing'
        else:
            browse_state = 'ready'
        browse_reason = {
            'service_unavailable': '本地 embedding 服务未就绪，语义查找已暂停',
            'no_evidence': '当前没有已解析且来源有效的本地资料',
            'indexing': '正在建立完整的本地语义查找索引',
            'index_error': self.error or '本地语义索引发生错误',
            'ready': '本地语义查找已就绪',
        }.get(browse_state, self.error or '本地语义查找暂不可用')
        return {
            'state': state, 'reason': reason, 'enabled': bool(self.port),
            'model': self.model, 'eligible': eligible, 'indexed': indexed,
            'pending': max(0, eligible - indexed), 'excluded': max(0, excluded),
            'excluded_reasons': excluded_reasons,
            'signature': self.signature, 'generation': config['generation'],
            'revision': config['revision'], 'dimension': config['dimension'],
            'calibrated': config['threshold'] is not None,
            'threshold': config['threshold'],
            'passage_template': PASSAGE_TEMPLATE_VERSION,
            'query_template': QUERY_TEMPLATE_VERSION, 'pooling': POOLING,
            'browse': {'state': browse_state, 'reason': browse_reason,
                       'available': browse_state == 'ready',
                       'indexed': browseable_indexed, 'eligible': len(browseable_rows),
                       'pending': max(0, len(browseable_rows) - browseable_indexed)},
        }

    def search(self, query, tag='', since='', until=''):
        return self.store.search(query, tag, since, until)

    def search_with_mode(self, query, tag='', since='', until=''):
        return self.retrieve(query, tag, since, until)

    @staticmethod
    def _source_label(source_type):
        return '迁移自个人记忆' if source_type == 'legacy_memory' else '收集资料'

    def browse(self, query, limit=20):
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            raise ValueError('语义查找内容须为 1–2000 字')
        if not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ValueError('语义查找结果数无效')
        index_status = self.status()
        browse_status = index_status['browse']
        if browse_status['state'] == 'no_evidence':
            return [], browse_status
        if browse_status['state'] != 'ready':
            raise SemanticUnavailable(browse_status['reason'])
        try:
            query_vector = self.encode(query.strip(), query=True)
        except Exception as exc:
            self.error = '本地语义服务不可用：' + str(exc)[:180]
            self.error_state = 'service_unavailable'
            raise SemanticUnavailable('本地语义查找已暂停：' + self.error) from None
        with self.store.connect() as db:
            config = dict(db.execute('SELECT * FROM semantic_index_config WHERE id=1').fetchone())
            if (config['signature'] != index_status['signature'] or
                    config['generation'] != index_status['generation'] or
                    config['revision'] != index_status['revision']):
                raise SemanticUnavailable('本地语义查找索引已变化，请重新查找')
            if len(query_vector) != config['dimension']:
                raise SemanticUnavailable('查询向量维度与本地语义索引不一致')
            rows = db.execute('''SELECT c.*,d.title,d.tags,d.event_time,d.created,d.privacy,
                d.status,m.source_type,m.question_state,m.question_reason,
                m.content_version,m.qualification_version,v.vector,v.source_hash
                FROM semantic_vectors v
                JOIN chunks c ON c.id=v.chunk_id JOIN documents d ON d.id=c.document_id
                JOIN document_metadata m ON m.document_id=d.id
                WHERE v.signature=? AND v.generation=? ORDER BY c.id''',
                              (self.signature, config['generation'])).fetchall()
            scored = []
            for row in rows:
                allowed, _ = self.store.locally_browsable(db, row['document_id'])
                if not allowed or self._source_hash(row) != row['source_hash']:
                    continue
                vector = json.loads(row['vector'])
                if (len(vector) != len(query_vector) or
                        any(not isinstance(value, (int, float)) or not math.isfinite(value)
                            for value in vector)):
                    raise SemanticUnavailable('本地语义索引包含无效或维度不一致的向量')
                scored.append((sum(a * b for a, b in zip(query_vector, vector)), row))
        scored.sort(key=lambda item: (-item[0], item[1]['id']))
        results, per_document = [], {}
        for similarity, row in scored:
            if len(results) >= limit:
                break
            count = per_document.get(row['document_id'], 0)
            if count >= MAX_PER_DOCUMENT:
                continue
            per_document[row['document_id']] = count + 1
            results.append({
                'rank': len(results) + 1,
                'document_id': row['document_id'], 'chunk_id': row['id'],
                'title': row['title'], 'source_type': row['source_type'],
                'source_label': self._source_label(row['source_type']),
                'privacy': row['privacy'], 'status': row['status'],
                'question_state': row['question_state'],
                'question_reason': row['question_reason'],
                'excerpt': row['text'][:400],
                'page': row['page'], 'semantic_similarity': similarity,
                'content_version': row['content_version'],
                'qualification_version': row['qualification_version'],
            })
        return results, {'state': 'ready', 'reason': '按本地余弦相似度排序',
                         'indexed': browse_status['indexed'],
                         'eligible': browse_status['eligible']}

    def _exact_features(self, query, row):
        normalized_query = _normalized(query)
        query_ids = _business_ids(query)
        content_ids = _business_ids(row['title'] + '\n' + row['tags'] + '\n' + row['text'])
        title = _normalized(row['title']).strip()
        tags = [_normalized(tag).strip() for tag in json.loads(row['tags'])]
        date = row['event_time']
        return (
            int(bool(query_ids & content_ids)),
            int(bool(title and title in normalized_query)),
            int(any(tag and tag in normalized_query for tag in tags)),
            int(bool(date and date in query)),
        )

    def retrieve(self, query, tag='', since='', until=''):
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            raise ValueError('问题须为 1–2000 字')
        status = self.status()
        if status['state'] == 'no_evidence':
            return [], {'mode': 'semantic', 'state': 'no_evidence',
                        'reason': status['reason'], 'index': status}
        if status['state'] != 'ready':
            raise SemanticUnavailable(status['reason'])
        try:
            query_vector = self.encode(query.strip(), query=True)
        except Exception as exc:
            self.error = '本地语义服务不可用：' + str(exc)[:180]
            self.error_state = 'service_unavailable'
            raise SemanticUnavailable(self.error) from None
        if len(query_vector) != status['dimension']:
            self.error = '查询向量维度与当前索引不一致'
            self.error_state = 'index_error'
            raise SemanticUnavailable(self.error)
        with self.store.connect() as db:
            config = dict(db.execute('SELECT * FROM semantic_index_config WHERE id=1').fetchone())
            if (config['revision'] != status['revision'] or
                    config['generation'] != status['generation'] or
                    config['threshold'] != status['threshold']):
                raise SemanticUnavailable('语义索引配置已变化，请重新提问')
            rows = db.execute('''SELECT c.*,d.title,d.tags,d.event_time,d.created,d.privacy,
                d.status,m.source_type,m.question_state,m.content_version,m.qualification_version,
                v.vector,v.source_hash FROM semantic_vectors v
                JOIN chunks c ON c.id=v.chunk_id JOIN documents d ON d.id=c.document_id
                JOIN document_metadata m ON m.document_id=d.id
                WHERE v.signature=? AND v.generation=? ORDER BY c.id''',
                              (self.signature, config['generation'])).fetchall()
            scored = []
            for row in rows:
                allowed, _ = self.store.question_eligible(db, row['document_id'])
                if not allowed:
                    continue
                date_value = (row['event_time'] or row['created'])[:10]
                if ((tag and tag not in json.loads(row['tags'])) or
                        (since and date_value < since) or (until and date_value > until)):
                    continue
                vector = json.loads(row['vector'])
                if (len(vector) != len(query_vector) or
                        any(not isinstance(value, (float, int)) or not math.isfinite(value)
                            for value in vector)):
                    raise SemanticUnavailable('语义索引包含无效或维度不一致的向量')
                similarity = sum(a * b for a, b in zip(query_vector, vector))
                if similarity >= config['threshold']:
                    scored.append((similarity, row))
        scored.sort(key=lambda item: (-item[0], item[1]['id']))
        scored = scored[:MAX_SEMANTIC_CANDIDATES]
        if not scored:
            return [], {'mode': 'semantic', 'state': 'no_match',
                        'reason': '本次未找到足够相关的资料', 'index': status}
        semantic_rank = {row['id']: index for index, (_, row) in enumerate(scored, 1)}
        exact_candidates = []
        for _, row in scored:
            features = self._exact_features(query, row)
            if any(features):
                exact_candidates.append((features, row['id']))
        exact_candidates.sort(key=lambda item: tuple([-value for value in item[0]]) + (item[1],))
        exact_rank = {identifier: index for index, (_, identifier)
                      in enumerate(exact_candidates, 1)}
        ranked = []
        for similarity, row in scored:
            sem_rank = semantic_rank[row['id']]
            ex_rank = exact_rank.get(row['id'])
            score = 0.8 / (RRF_K + sem_rank)
            if ex_rank:
                score += 0.2 / (RRF_K + ex_rank)
            ranked.append((score, similarity, row))
        ranked.sort(key=lambda item: (-item[0], -item[1], item[2]['id']))
        results, per_document = [], {}
        for score, similarity, row in ranked:
            if len(results) >= MAX_RESULTS:
                break
            count = per_document.get(row['document_id'], 0)
            if count >= MAX_PER_DOCUMENT:
                continue
            per_document[row['document_id']] = count + 1
            results.append({
                'id': row['document_id'], 'title': row['title'],
                'source_type': row['source_type'],
                'source_label': self._source_label(row['source_type']),
                'privacy': row['privacy'], 'status': row['status'],
                'question_state': row['question_state'], 'tags': json.loads(row['tags']),
                'event_time': row['event_time'], 'created': row['created'],
                'excerpt': row['text'][:400], 'text': row['text'],
                'chunk_id': row['id'], 'page': row['page'],
                'semantic_similarity': similarity, 'fused_score': score,
                'content_version': row['content_version'],
                'qualification_version': row['qualification_version'],
            })
        return results, {'mode': 'semantic', 'state': 'ready',
                         'reason': '本次使用已校准的本地语义检索与精确增强。',
                         'index': status}
