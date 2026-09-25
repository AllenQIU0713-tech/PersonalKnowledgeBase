"""Offline backup and restore. Server must be stopped; shared process lock enforces it."""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
from .config import data_directory, MIN_FREE
from .store import Store, now
from .embedding import Embeddings
from .answers import Answers
from .memories import Memories

MAX_BACKUP = 2 * 1024**3
HISTORY_SCHEMA = 2


@contextmanager
def exclusive(root):
    handle = (root / '.process.lock').open('a')
    try:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise ValueError('知识库正在运行，请先停止服务再备份或恢复')
    try:
        yield
    finally:
        handle.close()


def export_backup(root,destination):
    store=Store(root)
    embeddings=Embeddings(store)
    answers=Answers(store,embeddings)
    memories=Memories(store)
    answers.memories=memories
    answers.reconcile_legacy_sources()
    destination=Path(destination).expanduser().resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        raise ValueError('备份目标已存在，请选择新文件名')
    with tempfile.TemporaryDirectory(dir=root) as temp:
        snapshot=Path(temp)/'knowledge.sqlite3'
        with sqlite3.connect(str(root/'knowledge.sqlite3')) as source, sqlite3.connect(str(snapshot)) as target:
            source.backup(target)
            target.execute('PRAGMA journal_mode=DELETE')
        with sqlite3.connect(str(snapshot)) as db:
            identifiers=[r[0] for r in db.execute('SELECT id FROM documents')]
        files={'knowledge.sqlite3':snapshot}
        for identifier in identifiers:
            files['originals/'+identifier]=root/'originals'/identifier
        sizes={name:path.stat().st_size for name,path in files.items()}
        if sum(sizes.values())>MAX_BACKUP:
            raise ValueError('本版备份上限为 2 GiB，请减少资料或另行备份数据目录')
        if shutil.disk_usage(destination.parent).free<sum(sizes.values())+MIN_FREE:
            raise ValueError('备份目标空间不足')
        manifest={'format':1,'history_schema':HISTORY_SCHEMA,'created':now(),'files':{name:{'size':sizes[name],'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for name,path in files.items()}}
        destination.parent.mkdir(parents=True,exist_ok=True)
        partial=destination.with_name(destination.name+'.partial')
        try:
            with partial.open('xb') as handle:
                os.chmod(partial,0o600)
                with zipfile.ZipFile(handle,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))
                    for name,path in files.items():
                        archive.write(path,name)
            os.replace(partial,destination)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
    return str(destination)


def restore_backup(root,source):
    # Restore merges records; it never rolls current content back or weakens privacy.
    store=Store(root)
    embeddings=Embeddings(store)
    answers=Answers(store,embeddings)
    memories=Memories(store)
    answers.reconcile_legacy_sources()
    with tempfile.TemporaryDirectory(dir=root) as temp:
        staging=Path(temp)
        with zipfile.ZipFile(source) as archive:
            names=archive.namelist()
            if len(set(names))!=len(names) or 'manifest.json' not in names:
                raise ValueError('备份目录重复或缺少清单')
            if sum(i.file_size for i in archive.infolist())>MAX_BACKUP+1024**2:
                raise ValueError('备份解压后超过 2 GiB 上限')
            if archive.getinfo('manifest.json').file_size>1024**2:
                raise ValueError('备份清单过大')
            manifest=json.loads(archive.read('manifest.json'))
            if manifest.get('format')!=1 or not isinstance(manifest.get('files'),dict):
                raise ValueError('不支持的备份格式')
            files=manifest['files']
            history_import_allowed=manifest.get('history_schema')==HISTORY_SCHEMA
            if set(names)!=set(files)|{'manifest.json'} or 'knowledge.sqlite3' not in files:
                raise ValueError('备份文件与清单不一致')
            if shutil.disk_usage(root).free<sum(i.file_size for i in archive.infolist())*2+MIN_FREE:
                raise ValueError('恢复空间不足')
            for name,metadata in files.items():
                if name!='knowledge.sqlite3':
                    parts=name.split('/')
                    if len(parts)!=2 or parts[0]!='originals' or len(parts[1])!=32 or any(c not in '0123456789abcdef' for c in parts[1]):
                        raise ValueError('备份包含无效路径')
                data=archive.read(name)
                if len(data)!=metadata['size'] or hashlib.sha256(data).hexdigest()!=metadata['sha256']:
                    raise ValueError('备份完整性校验失败')
                target=staging/name
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(data)
                target.chmod(0o600)
        # Archive was fully extracted, hash-checked, and is no longer modified.
        # immutable permits reading older self-contained WAL-header snapshots without sidecars.
        incoming=sqlite3.connect('file:'+str(staging/'knowledge.sqlite3')+'?mode=ro&immutable=1',uri=True)
        incoming.row_factory=sqlite3.Row
        try:
            if incoming.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise ValueError('备份数据库损坏')
            # No execution of backup SQL: copy only whitelisted table values into our schema.
            current=store.connect()
            moved=[]
            committed=False
            try:
                with current:
                    for table in ('tombstones','memory_tombstones'):
                        if incoming.execute('SELECT 1 FROM sqlite_master WHERE type="table" AND name=?',(table,)).fetchone():
                            for row in incoming.execute('SELECT id,deleted FROM '+table):
                                if not re.fullmatch('[0-9a-f]{32}', row['id']):
                                    raise ValueError('删除记录标识无效')
                                current.execute('INSERT OR REPLACE INTO '+table+' VALUES (?,?)',tuple(row))
                    for row in current.execute('SELECT id FROM tombstones').fetchall():
                        store.clean_answers(current,row[0])
                        store.clean_memories(current,row[0])
                        current.execute('DELETE FROM documents WHERE id=?',(row[0],))
                    for row in current.execute('SELECT id FROM memory_tombstones').fetchall():
                        memories.clean_answers(current,row[0])
                        current.execute('DELETE FROM memories WHERE id=?',(row[0],))
                    deleted={r[0] for r in current.execute('SELECT id FROM tombstones')}
                    imported=set()
                    for row in incoming.execute('SELECT * FROM documents'):
                        identifier=row['id']
                        if not isinstance(identifier,str) or not re.fullmatch('[0-9a-f]{32}',identifier):
                            raise ValueError('资料标识无效')
                        if identifier in deleted:
                            continue
                        existing=current.execute('SELECT privacy FROM documents WHERE id=?',(identifier,)).fetchone()
                        if existing:
                            if row['privacy']=='local':
                                store.clean_answers(current,identifier)
                                current.execute("UPDATE documents SET privacy='local' WHERE id=?",(identifier,))
                            continue
                        original=staging/'originals'/identifier
                        if 'originals/'+identifier not in files or row['privacy'] not in ('allowed','local') or hashlib.sha256(original.read_bytes()).hexdigest()!=row['sha256']:
                            raise ValueError('资料原件校验失败')
                        shutil.copyfile(original,root/'originals'/identifier)
                        (root/'originals'/identifier).chmod(0o600)
                        moved.append(identifier)
                        columns=('id','title','filename','privacy','tags','event_time','created','sha256','size','status','error')
                        current.execute('INSERT INTO documents VALUES ('+','.join('?' for _ in columns)+')',tuple(row[c] for c in columns))
                        imported.add(identifier)
                    for row in incoming.execute('SELECT * FROM chunks'):
                        if row['document_id'] in imported:
                            current.execute('INSERT INTO chunks VALUES (?,?,?,?,?)',tuple(row[c] for c in ('id','document_id','position','page','text')))
                    tables={r[0] for r in incoming.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if {'memories','memory_sources','memory_history'}<=tables:
                        for row in incoming.execute('SELECT * FROM memories'):
                            identifier=row['id']
                            if current.execute('SELECT 1 FROM memory_tombstones WHERE id=?',(identifier,)).fetchone() or current.execute('SELECT 1 FROM memories WHERE id=?',(identifier,)).fetchone():
                                continue
                            sources=[r[0] for r in incoming.execute('SELECT document_id FROM memory_sources WHERE memory_id=?',(identifier,))]
                            if any(s in deleted or not current.execute('SELECT 1 FROM documents WHERE id=?',(s,)).fetchone() for s in sources):
                                continue
                            privacy=row['privacy']
                            if any(current.execute('SELECT privacy FROM documents WHERE id=?',(s,)).fetchone()[0]=='local' for s in sources):
                                privacy='local'
                            current.execute('INSERT INTO memories VALUES (?,?,?,?,?,?,?,?)',(identifier,row['topic'],row['text'],row['status'],privacy,row['origin'],row['created'],row['updated']))
                            for s in sources:
                                current.execute('INSERT INTO memory_sources VALUES (?,?)',(identifier,s))
                            for h in incoming.execute('SELECT * FROM memory_history WHERE memory_id=?',(identifier,)):
                                current.execute('INSERT INTO memory_history VALUES (?,?,?,?)',tuple(h[c] for c in ('id','memory_id','changed','snapshot')))
                    legacy_answers_skipped = 0
                    legacy_outbound_skipped = 0
                    if not history_import_allowed:
                        if 'answers' in tables:
                            legacy_answers_skipped = incoming.execute(
                                'SELECT COUNT(*) FROM answers').fetchone()[0]
                        if 'outbound' in tables:
                            legacy_outbound_skipped = incoming.execute(
                                'SELECT COUNT(*) FROM outbound').fetchone()[0]
                    if history_import_allowed and {'answers','answer_sources','outbound'}<=tables:
                        for row in incoming.execute('SELECT * FROM answers'):
                            if current.execute('SELECT 1 FROM answers WHERE id=?',(row['id'],)).fetchone():
                                continue
                            sources=incoming.execute('SELECT document_id,chunk_id FROM answer_sources WHERE answer_id=?',(row['id'],)).fetchall()
                            memory_ids=[r[0] for r in incoming.execute('SELECT memory_id FROM answer_memories WHERE answer_id=?',(row['id'],))] if 'answer_memories' in tables else []
                            if not sources and not memory_ids:
                                continue
                            if any(not current.execute("SELECT 1 FROM chunks c JOIN documents d ON d.id=c.document_id WHERE c.id=? AND d.id=? AND d.privacy='allowed'",tuple(s)).fetchone() for s in [(x['chunk_id'],x['document_id']) for x in sources]):
                                continue
                            if any(not current.execute("SELECT 1 FROM memories WHERE id=? AND privacy='allowed' AND status='confirmed'",(m,)).fetchone() for m in memory_ids):
                                continue
                            current.execute('INSERT INTO answers VALUES (?,?,?,?,?)',tuple(row[c] for c in ('id','created','question','answer','provider')))
                            for source in sources:
                                current.execute('INSERT INTO answer_sources VALUES (?,?,?)',(row['id'],source['document_id'],source['chunk_id']))
                            for memory_id in memory_ids:
                                current.execute('INSERT INTO answer_memories VALUES (?,?)',(row['id'],memory_id))
                        for row in incoming.execute('SELECT * FROM outbound'):
                            identifiers=json.loads(row['identifiers'])
                            if all(current.execute("SELECT 1 FROM chunks c JOIN documents d ON d.id=c.document_id WHERE c.id=? AND d.privacy='allowed'",(i,)).fetchone() or current.execute("SELECT 1 FROM memories WHERE id=? AND privacy='allowed'",(i,)).fetchone() for i in identifiers):
                                current.execute('INSERT OR IGNORE INTO outbound VALUES (?,?,?,?,?,?)',tuple(row[c] for c in ('id','created','purpose','provider','identifiers','simulated')))
                    current.execute("UPDATE documents SET status='queued' WHERE status='processing'")
                committed=True
                for identifier in deleted:
                    store.finish_delete(identifier)
                history = ('仅恢复安全版本备份中来源仍存在且允许外发的问答；'
                           '向量由当前模型重建')
                if not history_import_allowed:
                    history = ('旧备份的问答历史与外发记录未导入；原件、索引和个人记忆已按规则恢复')
                return {
                    'imported': len(imported),
                    'deleted_records_applied': len(deleted),
                    'legacy_answers_skipped': legacy_answers_skipped,
                    'legacy_outbound_skipped': legacy_outbound_skipped,
                    'history': history,
                }
            except Exception:
                if not committed:
                    for identifier in moved:
                        (root/'originals'/identifier).unlink(missing_ok=True)
                raise
            finally:
                current.close()
        finally:
            incoming.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=['export','restore'])
    parser.add_argument('file')
    parser.add_argument('--data-dir')
    args=parser.parse_args()
    root=data_directory(args.data_dir)
    with exclusive(root):
        if args.operation=='export':
            print(export_backup(root,args.file))
        else:
            print(json.dumps(restore_backup(root,args.file),ensure_ascii=False))

if __name__=='__main__':
    main()
