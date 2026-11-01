"""Regression for deleting a source referenced by the old memory schema.

Temporary synthetic SQLite only; no model, server, browser or network.
"""
import json
import io
import sys
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pkb.store import Store
from pkb.migration import LegacyMemoryMigration
from pkb.server import Handler
from pkb.embedding import Embeddings
from pkb.answers import Answers
from pkb.backup import export_backup, restore_backup
from s2r2_fixture import seed


class SourceDelete(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'synthetic'
        dataset = json.loads((Path(__file__).resolve().parents[1]/
            'fixtures/assisted-retrieval.json').read_text())
        self.store, self.mapping, _ = seed(self.root, dataset, (Store, LegacyMemoryMigration))
        # Real cache/answer schemas, but no worker, encoding or cloud provider.
        self.embeddings = Embeddings(self.store)
        self.answers = Answers(self.store, self.embeddings, cloud_provider=object())
        self.source = self.mapping['DOC-AR-SOURCE']['document_id']
        self.dependent = self.mapping['dependent']['document_id']
        with self.store.connect() as db:
            self.old_memories = [tuple(r) for r in db.execute('SELECT * FROM memories ORDER BY id')]
            self.old_history = [tuple(r) for r in db.execute('SELECT * FROM memory_history ORDER BY id')]
            self.old_snapshot = db.execute('SELECT snapshot FROM legacy_memory_map WHERE document_id=?',
                                          (self.dependent,)).fetchone()[0]
            self.links = [tuple(r) for r in db.execute(
                'SELECT memory_id,document_id FROM memory_sources WHERE document_id=?', (self.source,))]

    def assert_deleted_without_lost_lineage(self):
        with self.store.connect() as db:
            self.assertIsNone(db.execute('SELECT id FROM documents WHERE id=?', (self.source,)).fetchone())
            self.assertIsNotNone(db.execute('SELECT id FROM tombstones WHERE id=?', (self.source,)).fetchone())
            self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM memories ORDER BY id')], self.old_memories)
            self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM memory_history ORDER BY id')], self.old_history)
            self.assertEqual(db.execute('SELECT snapshot FROM legacy_memory_map WHERE document_id=?',
                                       (self.dependent,)).fetchone()[0], self.old_snapshot)
            for memory_id, source in self.links:
                self.assertIsNotNone(db.execute('SELECT 1 FROM legacy_restore_sources WHERE memory_id=? AND source_document_id=?',
                                               (memory_id, source)).fetchone())
            self.assertFalse(self.store.locally_browsable(db, self.dependent)[0])
            self.assertFalse(self.store.question_eligible(db, self.dependent)[0])
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.assertFalse((self.root/'originals'/self.source).exists())

    def test_delete_legacy_referenced_source(self):
        result = self.store.delete(self.source)
        self.assertFalse(result['cleanup_pending'])
        self.assert_deleted_without_lost_lineage()

    def test_restart_and_migration_cannot_restore_deleted_source(self):
        self.store.delete(self.source)
        self.store = Store(self.root)
        LegacyMemoryMigration(self.store).run()
        self.assert_deleted_without_lost_lineage()

    def test_repeated_delete_is_idempotent(self):
        self.store.delete(self.source)
        self.assertFalse(self.store.delete(self.source)['cleanup_pending'])
        self.assert_deleted_without_lost_lineage()

    def test_failed_transaction_restores_original_reference(self):
        with self.store.connect() as db:
            db.executescript("CREATE TRIGGER fail_test_delete BEFORE DELETE ON documents BEGIN SELECT RAISE(ABORT,'synthetic rollback'); END;")
        with self.assertRaises(Exception): self.store.delete(self.source)
        with self.store.connect() as db:
            self.assertEqual([tuple(r) for r in db.execute('SELECT memory_id,document_id FROM memory_sources WHERE document_id=?',
                (self.source,))], self.links)
            self.assertEqual(db.execute('SELECT * FROM legacy_restore_sources WHERE source_document_id=?', (self.source,)).fetchall(), [])
            self.assertIsNone(db.execute('SELECT id FROM tombstones WHERE id=?', (self.source,)).fetchone())
        self.assertTrue((self.root/'originals'/self.source).exists())

    def test_plain_document_delete_still_works(self):
        identifier = self.mapping['deletable']['document_id']
        self.assertFalse(self.store.delete(identifier)['cleanup_pending'])
        with self.assertRaises(KeyError): self.store.get(identifier)

    def test_real_delete_route_returns_200(self):
        req = object.__new__(Handler)
        req.server = SimpleNamespace(store=self.store, authority='127.0.0.1:18471',
            origin='http://127.0.0.1:18471', csrf='synthetic-csrf', session='synthetic-session')
        req.connection = SimpleNamespace(settimeout=lambda seconds: None)
        req.path = '/api/documents/'+self.source+'/delete'; req.command = 'POST'
        req.headers = Message()
        for key, value in {'Host':req.server.authority, 'Origin':req.server.origin,
                           'Cookie':'pkb_session=synthetic-session', 'X-PKB-CSRF':'synthetic-csrf',
                           'Content-Type':'application/json', 'Content-Length':'2'}.items():
            req.headers[key] = value
        req.rfile = io.BytesIO(b'{}')
        responses = []
        req.respond = lambda status, data, *args, **kwargs: responses.append((status, data))
        req.handle_request()
        self.assertEqual(responses, [(200, {'deleted':self.source,'cleanup_pending':False})])
        self.assert_deleted_without_lost_lineage()

    def test_store_without_legacy_tables(self):
        root = Path(self.temp.name)/'plain'; root.mkdir(); (root/'originals').mkdir()
        store = Store(root)
        item = store.add('synthetic ordinary document','note.txt',b'not user data',tags=[])
        self.assertFalse(store.delete(item['id'])['cleanup_pending'])
        with store.connect() as db: self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_source_and_dependent_cached_vectors_are_removed(self):
        # Unit-only cache sentinels; not embedding/quality evidence.
        with self.store.connect() as db:
            for identifier in (self.source, self.dependent):
                chunk = self.store.get(identifier)['chunks'][0]['id']
                db.execute('INSERT INTO semantic_vectors VALUES (?,?,?,?,?,?,?,?,?)',
                           (chunk, identifier, 'unit-sentinel', 1, 1, 'unit-no-model', 2, 1, '[1,0]'))
        self.store.delete(self.source)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM semantic_vectors WHERE document_id IN (?,?)',
                                        (self.source,self.dependent)).fetchone()[0], 0)
        self.assert_deleted_without_lost_lineage()

    def test_backup_restore_preserves_missing_source_lineage(self):
        self.store.delete(self.source)
        archive = Path(self.temp.name)/'after-delete.zip'
        export_backup(self.root, archive)
        restored = Path(self.temp.name)/'restored'; restored.mkdir(); (restored/'originals').mkdir()
        restore_backup(restored, archive)
        store = Store(restored); LegacyMemoryMigration(store).run()
        with store.connect() as db:
            self.assertIsNone(db.execute('SELECT id FROM documents WHERE id=?', (self.source,)).fetchone())
            self.assertFalse(store.locally_browsable(db, self.dependent)[0])
            for memory_id, source in self.links:
                self.assertIsNotNone(db.execute('SELECT 1 FROM legacy_restore_sources WHERE memory_id=? AND source_document_id=?',
                                               (memory_id, source)).fetchone())
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])


if __name__ == '__main__': unittest.main(verbosity=2)
