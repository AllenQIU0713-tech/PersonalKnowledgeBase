import json
import subprocess
import threading
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / 'scripts/extract.swift'
EXTENSIONS = {'.pdf': 'pdf', '.png': 'image', '.jpg': 'image', '.jpeg': 'image', '.heic': 'image', '.tiff': 'image', '.tif': 'image', '.webp': 'image'}


class Extractor:
    def __init__(self, store):
        self.store = store
        self.wake = threading.Event()
        self.stop = threading.Event()
        with store.connect() as db:
            db.execute("UPDATE documents SET status='queued' WHERE status='processing'")
        self.thread = threading.Thread(target=self.work, daemon=True)
        self.thread.start()
        self.wake.set()

    def enqueue(self, identifier):
        item = self.store.get(identifier)
        if Path(item['filename']).suffix.lower() not in EXTENSIONS:
            return item
        with self.store.lock, self.store.connect() as db:
            if item['status'] != 'processing':
                db.execute("UPDATE documents SET status='queued', error='' WHERE id=?", (identifier,))
                self.store.invalidate_document(db, identifier)
        self.wake.set()
        return self.store.get(identifier)

    def work(self):
        while not self.stop.is_set():
            self.wake.wait(2)
            self.wake.clear()
            with self.store.connect() as db:
                item = db.execute("SELECT * FROM documents WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not item:
                continue
            identifier = item['id']
            with self.store.lock, self.store.connect() as db:
                db.execute("UPDATE documents SET status='processing' WHERE id=?", (identifier,))
            try:
                executable = SCRIPT.parent.parent / '.build/extract'
                if not executable.exists():
                    raise ValueError('本地 OCR 提取器尚未构建，请运行 scripts/build-extractor.sh 后重试')
                process = subprocess.run([str(executable), str(self.store.root / 'originals' / identifier), EXTENSIONS[Path(item['filename']).suffix.lower()]], capture_output=True, timeout=180)
                if process.returncode:
                    raise ValueError(process.stderr.decode('utf-8', 'replace')[:500] or '本地解析失败')
                if len(process.stdout) > 12 * 1024 * 1024:
                    raise ValueError('提取正文超过 12 MiB 处理上限')
                pages = json.loads(process.stdout)
                with self.store.lock, self.store.connect() as db:
                    if db.execute('SELECT 1 FROM documents WHERE id=?', (identifier,)).fetchone():
                        self.store.set_chunks(db, identifier, [(p['page'], p['text']) for p in pages])
                        db.execute("UPDATE documents SET status='ready',error=? WHERE id=?", ('' if any(p['text'].strip() for p in pages) else '未识别到文字，仍可按标题与标签查找原件', identifier))
            except Exception as exc:
                with self.store.lock, self.store.connect() as db:
                    db.execute("UPDATE documents SET status='failed',error=? WHERE id=?", (str(exc)[:500], identifier))
                    self.store.invalidate_document(db, identifier)
            self.wake.set()
