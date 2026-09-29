import json
import re
import unicodedata
from fractions import Fraction
from .store import now, uid


QUESTION_PREFIXES = tuple(sorted(
    ('请告诉我', '请问'), key=len, reverse=True))
QUESTION_SUFFIXES = tuple(sorted(
    ('是什么', '吗'), key=len, reverse=True))
TOPIC_SUFFIXES = tuple(sorted((
    '会议纪要', '会议记录', '活动记录', '备忘录', '工作日志', '笔记',
    '记录', '纪要', '总结', '方案', '计划', '资料', '清单'),
    key=len, reverse=True))
GENERIC_TOPICS = frozenset(
    ('项目', '会议', '时间', '评审', '评审会') + TOPIC_SUFFIXES)
BUSINESS_TOKEN = re.compile(
    r'(?<![a-z0-9_-])[a-z0-9]+(?:[-_][a-z0-9]+)*(?![a-z0-9_-])')
EVENT_QUALIFIERS = ('上一次', '下一次', '本次')


def _compact(text):
    normalized = unicodedata.normalize('NFKC', text).casefold()
    return ''.join(char for char in normalized if unicodedata.category(char)[:1] in ('L', 'N'))


def _question_text(question):
    text = _compact(question)
    for prefix in QUESTION_PREFIXES:
        if text.startswith(prefix) and len(text) > len(prefix):
            text = text[len(prefix):]
            break
    for suffix in QUESTION_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[:-len(suffix)]
            break
    return text


def _topic_core(topic):
    text = _compact(topic)
    for suffix in TOPIC_SUFFIXES:
        if text.endswith(suffix):
            return text[:-len(suffix)]
    return text


def _business_ids(text):
    normalized = unicodedata.normalize('NFKC', text).casefold()
    tokens = BUSINESS_TOKEN.findall(normalized)
    return {token for token in tokens if
            any('a' <= char <= 'z' for char in token) and
            any(char.isdigit() for char in token)}


def _short_topic_exact(raw_question, topic):
    return (2 <= len(topic) <= 3 and raw_question == topic and
            topic not in GENERIC_TOPICS and not topic.isdecimal() and
            any(unicodedata.category(char).startswith('L') for char in topic))


def _theme_anchor(value):
    return (len(value) >= 4 and value not in GENERIC_TOPICS and
            not value.isdecimal() and
            any(unicodedata.category(char).startswith('L') for char in value))


def _remove_anchor(question, anchor):
    index = question.find(anchor)
    if index < 0:
        return None
    before, after = question[:index], question[index + len(anchor):]
    if after.startswith('的'):
        after = after[1:]
    return before + after


def _intent_match(intent, body):
    if not intent:
        return Fraction(0, 1)
    if len(intent) < 4:
        return None
    windows = list(dict.fromkeys(
        intent[index:index + 4] for index in range(len(intent) - 3)))
    matched = sum(window in body for window in windows)
    if matched * 2 < len(windows) or windows[-1] not in body:
        return None
    if any(qualifier in intent and qualifier not in body
           for qualifier in EVENT_QUALIFIERS):
        return None
    return Fraction(matched, len(windows))


def _relevance(item, question):
    raw_query = _compact(question)
    query = _question_text(question)
    topic = _compact(item['topic'])
    body = _compact(item['text'])
    core = _topic_core(item['topic'])
    if not raw_query or not query or not topic:
        return None

    if _short_topic_exact(raw_query, topic):
        return (3, Fraction(0, 1), len(topic))

    query_ids = _business_ids(question)
    candidate_ids = _business_ids(item['topic'] + '\n' + item['text'])
    matched_ids = query_ids & candidate_ids
    if query_ids and not matched_ids:
        return None

    theme_anchor = None
    theme_tier = 0
    if _theme_anchor(topic) and topic in query:
        theme_anchor, theme_tier = topic, 3
    elif _theme_anchor(core) and core in query:
        theme_anchor, theme_tier = core, 1

    identifier = max(matched_ids, key=lambda value: (len(value), value), default=None)
    if theme_anchor is None and identifier is None:
        return None

    intent = query
    if theme_anchor is not None:
        intent = _remove_anchor(intent, theme_anchor)
    if identifier is not None:
        compact_identifier = _compact(identifier)
        if compact_identifier in intent:
            intent = _remove_anchor(intent, compact_identifier)
    if intent is None:
        return None

    coverage = _intent_match(intent, body)
    if coverage is None:
        return None
    if identifier is not None:
        tier = 3
    elif theme_tier == 3:
        tier = 3
    elif intent:
        tier = 2
    else:
        tier = 1
    anchor_length = max(
        len(theme_anchor or ''), len(_compact(identifier or '')))
    return (tier, coverage, anchor_length)


class Memories:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY, topic TEXT NOT NULL, text TEXT NOT NULL,
                    status TEXT NOT NULL, privacy TEXT NOT NULL, origin TEXT NOT NULL,
                    created TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS memory_sources (
                    memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    PRIMARY KEY(memory_id,document_id));
                CREATE TABLE IF NOT EXISTS memory_history (
                    id TEXT PRIMARY KEY, memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                    changed TEXT NOT NULL, snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS answer_memories (
                    answer_id TEXT NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
                    memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE);
                CREATE TABLE IF NOT EXISTS memory_tombstones (id TEXT PRIMARY KEY,deleted TEXT NOT NULL);
            ''')

    def list(self):
        with self.store.connect() as db:
            items = [dict(r) for r in db.execute('SELECT * FROM memories ORDER BY updated DESC')]
            for item in items:
                item['sources'] = [r[0] for r in db.execute('SELECT document_id FROM memory_sources WHERE memory_id=?', (item['id'],))]
                item['conflicts'] = [other['id'] for other in items if other['id']!=item['id'] and other['topic']==item['topic'] and other['text']!=item['text'] and other['status']!='inactive' and item['status']!='inactive']
                item['history'] = [dict(r) for r in db.execute('SELECT changed,snapshot FROM memory_history WHERE memory_id=? ORDER BY changed', (item['id'],))]
            return items

    def save(self, payload, identifier=None, candidate=False):
        text, topic = payload.get('text'), payload.get('topic')
        privacy, status = payload.get('privacy','allowed'), payload.get('status','confirmed')
        sources = payload.get('sources',[])
        if not isinstance(text,str) or not 1<=len(text.strip())<=2000 or not isinstance(topic,str) or not 1<=len(topic.strip())<=100:
            raise ValueError('记忆需要主题（1–100 字）和正文（1–2000 字）')
        if privacy not in ('allowed','local') or status not in ('confirmed','pending','inactive'):
            raise ValueError('记忆状态或隐私无效')
        if not isinstance(sources,list) or len(sources)>20 or any(not isinstance(s,str) for s in sources):
            raise ValueError('来源须为最多 20 个资料标识')
        with self.store.lock, self.store.connect() as db:
            previous = None
            if identifier:
                previous = db.execute('SELECT * FROM memories WHERE id=?',(identifier,)).fetchone()
                if not previous:
                    raise KeyError('记忆不存在')
                # Sources of derived memories cannot silently be detached.
                old_sources = [r[0] for r in db.execute('SELECT document_id FROM memory_sources WHERE memory_id=?',(identifier,))]
                sources = list(set(sources+old_sources))
                self.clean_answers(db,identifier)
            for source in sources:
                row = db.execute('SELECT privacy FROM documents WHERE id=?',(source,)).fetchone()
                if not row:
                    raise ValueError('记忆来源不存在')
                if row['privacy']=='local':
                    privacy='local'
            if candidate:
                if not sources:
                    raise ValueError('推测记忆必须有来源')
                status='pending'
            identifier = identifier or uid()
            created = previous['created'] if previous else now()
            origin = previous['origin'] if previous else ('model' if candidate else 'manual')
            if previous:
                db.execute('INSERT INTO memory_history VALUES (?,?,?,?)',(uid(),identifier,now(),json.dumps(dict(previous),ensure_ascii=False)))
                db.execute('UPDATE memories SET topic=?,text=?,status=?,privacy=?,updated=? WHERE id=?',(topic.strip(),text.strip(),status,privacy,now(),identifier))
            else:
                db.execute('INSERT INTO memories VALUES (?,?,?,?,?,?,?,?)',(identifier,topic.strip(),text.strip(),status,privacy,origin,created,now()))
            db.execute('DELETE FROM memory_sources WHERE memory_id=?',(identifier,))
            for source in set(sources):
                db.execute('INSERT INTO memory_sources VALUES (?,?)',(identifier,source))
            return {'id':identifier}

    def eligible(self, question):
        candidates=[]
        for item in self.list():
            if item['status']!='confirmed' or item['privacy']!='allowed' or item['conflicts']:
                continue
            try:
                source_blocked = any(
                    self.store.get(source)['privacy']!='allowed'
                    for source in item['sources'])
            except Exception:
                # A missing or unreadable source fails closed for this memory.
                source_blocked = True
            if source_blocked:
                continue
            score = _relevance(item, question)
            if score:
                candidates.append((score,item))
        candidates.sort(key=lambda candidate:candidate[1]['id'])
        candidates.sort(key=lambda candidate:candidate[1]['updated'],reverse=True)
        candidates.sort(key=lambda candidate:candidate[0],reverse=True)
        return [{k:item[k] for k in ('id','topic','text','sources')}
                for _,item in candidates[:5]]

    @staticmethod
    def clean_answers(db,identifier):
        for row in db.execute('SELECT answer_id FROM answer_memories WHERE memory_id=?',(identifier,)).fetchall():
            db.execute('DELETE FROM answers WHERE id=?',(row[0],))
        for row in db.execute('SELECT id,identifiers FROM outbound').fetchall():
            if identifier in json.loads(row['identifiers']):
                db.execute('DELETE FROM outbound WHERE id=?',(row['id'],))
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='cloud_requests'").fetchone():
            for row in db.execute('SELECT id,identifiers FROM cloud_requests').fetchall():
                if identifier in json.loads(row['identifiers']):
                    db.execute('DELETE FROM cloud_requests WHERE id=?',(row['id'],))

    def delete(self,identifier):
        with self.store.lock,self.store.connect() as db:
            self.clean_answers(db,identifier)
            db.execute('INSERT OR REPLACE INTO memory_tombstones VALUES (?,?)',(identifier,now()))
            db.execute('DELETE FROM memories WHERE id=?',(identifier,))
