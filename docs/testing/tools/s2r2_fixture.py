"""Synthetic seeding; actual candidate modules supplied only after preflight."""
import json
from pathlib import Path

def seed(root, dataset, modules):
    Store, Migration = modules
    root = Path(root).resolve(); root.mkdir(parents=True, exist_ok=True)
    (root/'originals').mkdir(exist_ok=True)
    store, mapping = Store(root), {}
    is_qa = 'collection_documents' in dataset
    documents = dataset['collection_documents'] if is_qa else [r for r in dataset['records'] if r['storage']=='documents']
    sources = dataset.get('source_records', [])
    def add(record):
        alias = record.get('fixture_id', record.get('id'))
        if record.get('exists') is False or record.get('source_present') is False: return
        parsed = record.get('parsed', True)
        item = store.add(record.get('title', alias), 'synthetic.txt' if parsed else 'synthetic.bin',
                         record['text'].encode('utf-8'), privacy=record.get('privacy','allowed'), tags=record.get('tags',[]))
        mapping[alias] = {'document_id': item['id'], 'chunk_ids': [c['id'] for c in item['chunks']]}
    for record in documents+sources: add(record)
    legacy = dataset['legacy_memories'] if is_qa else [r for r in dataset['records'] if r['storage']=='legacy_memories_then_migration']
    # Exact legacy schema consumed by actual migration, never fabricate migrated documents.
    with store.connect() as db:
        db.executescript('''CREATE TABLE memories (id TEXT PRIMARY KEY, topic TEXT NOT NULL, text TEXT NOT NULL,
          status TEXT NOT NULL, privacy TEXT NOT NULL, origin TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
          CREATE TABLE memory_sources (memory_id TEXT NOT NULL REFERENCES memories(id), document_id TEXT NOT NULL REFERENCES documents(id), PRIMARY KEY(memory_id,document_id));
          CREATE TABLE memory_history (id TEXT PRIMARY KEY,memory_id TEXT NOT NULL,changed TEXT NOT NULL,snapshot TEXT NOT NULL);
          CREATE TABLE memory_conflicts (id TEXT PRIMARY KEY,memory_id TEXT NOT NULL,other_memory_id TEXT NOT NULL,reason TEXT NOT NULL,resolved INTEGER NOT NULL);''')
        for record in legacy:
            db.execute('INSERT INTO memories VALUES (?,?,?,?,?,?,?,?)', (record['memory_id'],record['topic'],record['text'],record['legacy_status'],record['privacy'],record['origin'],'2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00'))
            for source in record.get('sources', record.get('source_dependencies', [])):
                db.execute('INSERT INTO memory_sources VALUES (?,?)',(record['memory_id'],mapping[source]['document_id']))
        for record in dataset.get('legacy_restore_sources', []):
            source = record['source_document_id']
            actual = mapping.get(source,{}).get('document_id', source)
            db.execute('INSERT INTO legacy_restore_sources VALUES (?,?)',(record['memory_id'],actual))
    migration = Migration(store).run()
    with store.connect() as db:
        for record in legacy:
            row = db.execute('SELECT document_id FROM legacy_memory_map WHERE memory_id=?',(record['memory_id'],)).fetchone()
            if row is None: raise AssertionError('migration failed to map '+record['memory_id'])
            item = {'document_id':row[0], 'chunk_ids':[r[0] for r in db.execute('SELECT id FROM chunks WHERE document_id=? ORDER BY position',(row[0],))]}
            mapping[record['fixture_id']] = item
            mapping[record['memory_id']] = item
            metadata = db.execute('SELECT source_type FROM document_metadata WHERE document_id=?',(row[0],)).fetchone()
            if metadata[0] != 'legacy_memory': raise AssertionError('real migration source enum mismatch')
    return store, mapping, migration
