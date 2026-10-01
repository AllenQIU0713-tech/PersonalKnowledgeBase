"""Fail-closed, idempotent migration from legacy memories to documents."""
import hashlib
import json
from pathlib import Path

from .store import now

MIGRATION_NAME = 'S1-single-library-legacy-memories-v1'


def _stable_id(prefix, value):
    return hashlib.sha256((prefix + value).encode()).hexdigest()[:32]


class LegacyMemoryMigration:
    def __init__(self, store):
        self.store = store

    def _tables(self, db):
        return {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}

    def _backup(self, fingerprint):
        directory = self.store.root / 'migration-backups'
        directory.mkdir(exist_ok=True, mode=0o700)
        destination = directory / ('pre-single-library-S1-' + fingerprint[:12] + '.zip')
        if not destination.exists():
            from .backup import export_backup
            export_backup(self.store.root, destination)
        return str(destination), hashlib.sha256(destination.read_bytes()).hexdigest()

    def _write_manifest(self, manifest):
        directory = self.store.root / 'migration-backups'
        directory.mkdir(exist_ok=True, mode=0o700)
        destination = directory / 'single-library-S1-manifest.json'
        partial = destination.with_suffix('.json.partial')
        partial.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        partial.chmod(0o600)
        partial.replace(destination)
        return destination

    def _memory_snapshot(self, db, row, sources, conflicts):
        history = [dict(item) for item in db.execute(
            'SELECT changed,snapshot FROM memory_history WHERE memory_id=? ORDER BY changed',
            (row['id'],))]
        return {
            'id': row['id'], 'topic': row['topic'], 'text': row['text'],
            'status': row['status'], 'privacy': row['privacy'],
            'origin': row['origin'], 'created': row['created'], 'updated': row['updated'],
            'sources': sources, 'conflicts': conflicts, 'history': history,
        }

    def _qualification(self, db, row, sources, conflicts):
        privacy = row['privacy']
        missing, restricted = [], []
        for source in sources:
            document = db.execute('SELECT privacy FROM documents WHERE id=?', (source,)).fetchone()
            if not document:
                missing.append(source)
            elif document['privacy'] != 'allowed':
                restricted.append(source)
        if restricted:
            privacy = 'local'
        if row['status'] == 'inactive':
            return privacy, 'inactive', '旧个人记忆已失效'
        if conflicts:
            return privacy, 'conflict', '旧个人记忆存在未解决冲突'
        if missing:
            return privacy, 'blocked_source', '旧来源缺失或无法核验'
        if row['status'] != 'confirmed':
            return privacy, 'review', '旧个人记忆尚未确认'
        if restricted:
            return privacy, 'ready', '旧来源禁止外发，已继承更严格隐私'
        if privacy != 'allowed':
            return privacy, 'ready', '旧个人记忆禁止外发'
        return privacy, 'ready', ''

    def _migrate_one(self, db, row):
        memory_id = row['id']
        mapped = db.execute('SELECT document_id FROM legacy_memory_map WHERE memory_id=?',
                            (memory_id,)).fetchone()
        if mapped:
            if not db.execute('SELECT 1 FROM documents WHERE id=?', (mapped[0],)).fetchone():
                if db.execute('SELECT 1 FROM tombstones WHERE id=?', (mapped[0],)).fetchone():
                    return False, mapped[0], True
                raise ValueError('旧个人记忆映射对应的资料不存在')
            return False, mapped[0], False
        document_id = _stable_id('legacy-memory:', memory_id)
        collision = db.execute('SELECT 1 FROM documents WHERE id=?', (document_id,)).fetchone()
        if collision:
            raise ValueError('旧个人记忆迁移标识与现有资料冲突')
        sources = {item[0] for item in db.execute(
            'SELECT document_id FROM memory_sources WHERE memory_id=?', (memory_id,))}
        if 'legacy_restore_sources' in self._tables(db):
            sources.update(item[0] for item in db.execute(
                'SELECT source_document_id FROM legacy_restore_sources WHERE memory_id=?',
                (memory_id,)))
        sources = sorted(sources)
        conflicts = [item[0] for item in db.execute('''
            SELECT id FROM memories WHERE id<>? AND topic=? AND text<>?
            AND status<>'inactive' AND ?<>'inactive' ORDER BY id''',
            (memory_id, row['topic'], row['text'], row['status']))]
        privacy, question_state, reason = self._qualification(db, row, sources, conflicts)
        data = row['text'].encode()
        original = self.store.root / 'originals' / document_id
        original.write_bytes(data)
        original.chmod(0o600)
        snapshot = self._memory_snapshot(db, row, sources, conflicts)
        tags = ['旧个人记忆', '原状态:' + row['status'], '原来源:' + row['origin']]
        try:
            db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?)', (
                document_id, row['topic'], 'legacy-memory-' + memory_id + '.txt', privacy,
                json.dumps(tags, ensure_ascii=False), '', row['created'],
                hashlib.sha256(data).hexdigest(), len(data), 'ready', ''))
            db.execute('INSERT INTO document_metadata VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (
                document_id, 'legacy_memory', memory_id, row['status'], row['origin'],
                row['created'], row['updated'], question_state, reason, 1, 1, row['updated']))
            chunk_id = _stable_id('legacy-memory-chunk:', memory_id)
            db.execute('INSERT INTO chunks VALUES (?,?,?,?,?)',
                       (chunk_id, document_id, 1, None, row['text']))
            for source in sources:
                db.execute('INSERT INTO document_sources VALUES (?,?,?)',
                           (document_id, source, 'legacy_memory_source'))
            db.execute('INSERT INTO legacy_memory_map VALUES (?,?,?,?,?,?)', (
                memory_id, document_id, json.dumps(snapshot, ensure_ascii=False), now(),
                question_state, reason))
        except Exception:
            original.unlink(missing_ok=True)
            raise
        return True, document_id, question_state != 'ready' or privacy != 'allowed'

    def run(self):
        with self.store.connect() as db:
            tables = self._tables(db)
            existing = db.execute('SELECT * FROM single_library_migrations WHERE name=?',
                                  (MIGRATION_NAME,)).fetchone()
            if not {'memories', 'memory_sources', 'memory_history'} <= tables:
                stamp = now()
                manifest = {'version': 1, 'source_count': 0, 'mappings': []}
                db.execute('INSERT OR REPLACE INTO single_library_migrations VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (MIGRATION_NAME, stamp, stamp, 'complete', '', '', 0, 0, 0,
                            json.dumps(manifest, ensure_ascii=False)))
                return dict(db.execute('SELECT * FROM single_library_migrations WHERE name=?',
                                       (MIGRATION_NAME,)).fetchone())
            memory_ids = [row[0] for row in db.execute('SELECT id FROM memories ORDER BY id')]
            count = len(memory_ids)
            unmapped = db.execute('''SELECT COUNT(*) FROM memories m
                LEFT JOIN legacy_memory_map l ON l.memory_id=m.id
                WHERE l.memory_id IS NULL''').fetchone()[0]
            if existing and existing['status'] == 'complete' and not unmapped:
                self._write_manifest(json.loads(existing['manifest']))
                return dict(existing)
        fingerprint = hashlib.sha256('\n'.join(memory_ids).encode()).hexdigest()
        backup_path, backup_hash = self._backup(fingerprint) if unmapped else ('', '')
        started = now()
        created_documents = []
        try:
            with self.store.lock, self.store.connect() as db:
                db.execute('INSERT OR REPLACE INTO single_library_migrations VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (MIGRATION_NAME, started, '', 'running', backup_path, backup_hash,
                            count, 0, 0, '{}'))
                created_count = 0
                mappings = []
                for row in db.execute('SELECT * FROM memories ORDER BY id').fetchall():
                    created, document_id, _ = self._migrate_one(db, row)
                    if created:
                        created_documents.append(document_id)
                    created_count += int(created)
                    mappings.append({'memory_id': row['id'], 'document_id': document_id})
                migrated = db.execute('SELECT COUNT(*) FROM legacy_memory_map').fetchone()[0]
                blocked = db.execute('''SELECT COUNT(*) FROM legacy_memory_map l
                    LEFT JOIN documents d ON d.id=l.document_id
                    LEFT JOIN document_metadata m ON m.document_id=l.document_id
                    WHERE d.id IS NULL OR d.privacy<>'allowed' OR m.question_state<>'ready' ''').fetchone()[0]
                manifest = {
                    'version': 1, 'source_count': count, 'migrated_count': migrated,
                    'created_count': created_count,
                    'blocked_count': blocked, 'backup_path': backup_path,
                    'backup_sha256': backup_hash, 'mappings': mappings,
                }
                completed = now()
                db.execute('''UPDATE single_library_migrations
                              SET completed=?,status='complete',migrated_count=?,blocked_count=?,manifest=?
                              WHERE name=?''',
                           (completed, migrated, blocked, json.dumps(manifest, ensure_ascii=False),
                            MIGRATION_NAME))
        except Exception:
            for document_id in created_documents:
                (self.store.root / 'originals' / document_id).unlink(missing_ok=True)
            raise
        self._write_manifest(manifest)
        with self.store.connect() as db:
            return dict(db.execute('SELECT * FROM single_library_migrations WHERE name=?',
                                   (MIGRATION_NAME,)).fetchone())
