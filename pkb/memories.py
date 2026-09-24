import json
from .store import now, uid


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
        result=[]
        for item in self.list():
            if item['status']!='confirmed' or item['privacy']!='allowed' or item['conflicts']:
                continue
            if not (item['topic'] in question or any(t in item['text'] for t in question.split() if len(t)>1)):
                continue
            if any(self.store.get(s)['privacy']!='allowed' for s in item['sources']):
                continue
            result.append({k:item[k] for k in ('id','topic','text','sources')})
            if len(result)>=5:
                break
        return result

    @staticmethod
    def clean_answers(db,identifier):
        for row in db.execute('SELECT answer_id FROM answer_memories WHERE memory_id=?',(identifier,)).fetchall():
            db.execute('DELETE FROM answers WHERE id=?',(row[0],))
        for row in db.execute('SELECT id,identifiers FROM outbound').fetchall():
            if identifier in json.loads(row['identifiers']):
                db.execute('DELETE FROM outbound WHERE id=?',(row['id'],))

    def delete(self,identifier):
        with self.store.lock,self.store.connect() as db:
            self.clean_answers(db,identifier)
            db.execute('INSERT OR REPLACE INTO memory_tombstones VALUES (?,?)',(identifier,now()))
            db.execute('DELETE FROM memories WHERE id=?',(identifier,))
