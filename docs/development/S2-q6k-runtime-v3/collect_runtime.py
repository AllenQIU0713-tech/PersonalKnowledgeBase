"""Read-only installed-runtime provenance survey; metadata GET and artifact HEAD only."""
from pathlib import Path
import base64
import csv
import datetime as dt
import hashlib
import json
import os
import subprocess
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw'
RAW.mkdir(exist_ok=True)
PYTHON = Path('/Users/allenqiu/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none')
UV = Path('/Users/allenqiu/.local/bin/uv')
UV_COMMIT = '396ef7ce44e343095f3a5a5e8bc4b0b670ed0f5b'
RECEIPTS = []


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def request(url, name, method='GET'):
    u = urlsplit(url)
    if method == 'GET':
        allowed = ((u.hostname == 'raw.githubusercontent.com' and
                    ('/crates/uv-python/download-metadata.json' in u.path or
                     u.path.endswith(('/LICENSE', '/LICENSE-MIT', '/LICENSE-APACHE', '/vendor.txt')))) or
                   (u.hostname == 'pypi.org' and (u.path.endswith('/json') or u.path == '/simple/pip/')) or
                   (u.hostname == 'files.pythonhosted.org' and u.path.endswith('.whl.metadata')))
    else:
        allowed = method == 'HEAD' and u.hostname == 'github.com' and '/astral-sh/python-build-standalone/releases/download/20260623/' in u.path
    if u.scheme != 'https' or not allowed:
        raise ValueError('non-metadata request blocked')
    headers = {'User-Agent': 'PKB-Q6-Runtime-Metadata-Only/3'}
    if u.path == '/simple/pip/':
        headers['Accept'] = 'application/vnd.pypi.simple.v1+json'
    receipt = {'url': url, 'method': method, 'time': dt.datetime.now(dt.timezone.utc).isoformat(),
               'artifact_body_bytes': 0}
    try:
        with urlopen(Request(url, headers=headers, method=method), timeout=30) as response:
            body = b'' if method == 'HEAD' else response.read(8_000_001)
            if len(body) > 8_000_000:
                raise ValueError('metadata size cap')
            final = urlsplit(response.url)
            receipt.update(status=response.status, final_origin=final.scheme + '://' + final.netloc,
                           final_path=final.path, bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                           content_length=response.headers.get('Content-Length'))
        (RAW / name).write_bytes(body if method != 'HEAD' else json.dumps(receipt, indent=2).encode())
        receipt['raw_file'] = 'raw/' + name
        print(method, url, 'metadata_bytes', len(body), flush=True)
        return body, receipt
    except Exception as exc:
        receipt['error'] = type(exc).__name__ + ': ' + str(exc)
        print('ERROR', method, url, receipt['error'], flush=True)
        return None, receipt
    finally:
        RECEIPTS.append(receipt)
        (ROOT / 'receipts.json').write_text(json.dumps(RECEIPTS, indent=2) + '\n')


def local_file(path, copy_name=None):
    path = Path(path)
    item = {'path': str(path), 'realpath': str(path.resolve()), 'bytes': path.stat().st_size,
            'sha256': sha(path)}
    if copy_name:
        (RAW / copy_name).write_bytes(path.read_bytes())
        item['raw_copy'] = 'raw/' + copy_name
    return item


if __name__ == '__main__':
    info = {'created_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'approval_status': 'approval_blocked',
            'scope': 'installed runtime and frontend observation; no build approval'}
    argv = [str(PYTHON / 'bin/python3.12'), '-I', '-S', '-c',
            'import sys,sysconfig,platform,json;print(json.dumps(dict(version=sys.version,executable=sys.executable,prefix=sys.prefix,machine=platform.machine(),soabi=sysconfig.get_config_var("SOABI"),platform=platform.platform())))']
    info['interpreter_introspection_argv'] = argv
    info['interpreter_observation'] = json.loads(subprocess.check_output(argv, text=True))
    info['local_files'] = [local_file(PYTHON / 'bin/python3.12'),
                           local_file(PYTHON / 'lib/libpython3.12.dylib'),
                           local_file(PYTHON / 'BUILD', 'installed-python-BUILD.txt'),
                           local_file(PYTHON / 'lib/python3.12/LICENSE.txt', 'installed-python-LICENSE.txt'),
                           local_file(UV)]
    for name in ('uv-receipt.toml', 'pyvenv.cfg'):
        info['local_files'].append(local_file(Path('/Users/allenqiu/.local/share/uv/tools/browser-harness') / name,
                                             'browser-harness-' + name))
    site = PYTHON / 'lib/python3.12/site-packages'
    dist = site / 'pip-26.1.2.dist-info'
    for name in ('METADATA', 'INSTALLER', 'direct_url.json', 'RECORD'):
        info['local_files'].append(local_file(dist / name, 'installed-pip-' + name))
    info['local_files'].append(local_file(site / 'pip/_vendor/vendor.txt', 'installed-pip-vendor.txt'))
    record_check = {'checked': 0, 'unhashed': [], 'missing': [], 'mismatches': []}
    for relative, digest, size in csv.reader((dist / 'RECORD').read_text().splitlines()):
        path = (site / relative).resolve()
        if not path.is_relative_to(PYTHON.resolve()):
            raise ValueError('pip RECORD escapes installed runtime')
        if not digest:
            record_check['unhashed'].append(relative)
        elif not path.is_file():
            record_check['missing'].append(relative)
        else:
            algorithm, encoded = digest.split('=', 1)
            if algorithm != 'sha256':
                raise ValueError('unexpected RECORD digest algorithm')
            wanted = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)).hex()
            if sha(path) != wanted or (size and path.stat().st_size != int(size)):
                record_check['mismatches'].append(relative)
            record_check['checked'] += 1
    info['pip_record_self_consistency'] = record_check
    info['pip_record_evidence_limit'] = 'Local RECORD can be modified with files; consistency is not a trusted publisher baseline.'
    mapping_url = 'https://raw.githubusercontent.com/astral-sh/uv/' + UV_COMMIT + '/crates/uv-python/download-metadata.json'
    body, _ = request(mapping_url, 'uv-fixed-download-metadata.json')
    if body:
        entry = json.loads(body)['cpython-3.12.13-darwin-aarch64-none']
        info['expected_publisher_artifact'] = dict(entry, mapping_url=mapping_url, uv_commit=UV_COMMIT)
        _, head = request(entry['url'], 'python-expected-archive-head.json', method='HEAD')
        info['expected_publisher_artifact']['bytes_from_HEAD'] = head.get('content_length')
    request('https://raw.githubusercontent.com/python/cpython/v3.12.13/LICENSE', 'python31213-upstream-LICENSE.txt')
    request('https://raw.githubusercontent.com/astral-sh/uv/' + UV_COMMIT + '/LICENSE-MIT', 'uv-fixed-LICENSE-MIT.txt')
    request('https://raw.githubusercontent.com/astral-sh/uv/' + UV_COMMIT + '/LICENSE-APACHE', 'uv-fixed-LICENSE-APACHE.txt')
    body, _ = request('https://pypi.org/pypi/pip/26.1.2/json', 'pip2612-pypi.json')
    if body:
        wheel = next(f for f in json.loads(body)['urls'] if f['filename'] == 'pip-26.1.2-py3-none-any.whl')
        simple, _ = request('https://pypi.org/simple/pip/', 'pip-simple.json')
        row = next(f for f in json.loads(simple)['files'] if f['filename'] == wheel['filename'])
        expected = (row.get('core-metadata') or row.get('dist-info-metadata'))['sha256']
        sidecar, _ = request(wheel['url'] + '.metadata', 'pip2612-upstream.metadata')
        assert hashlib.sha256(sidecar).hexdigest() == expected
        direct = json.loads((dist / 'direct_url.json').read_text())
        info['pip_publisher_mapping'] = {k: wheel[k] for k in ('filename', 'url', 'size', 'digests')}
        info['pip_publisher_mapping'].update(local_direct_url_archive_hash_matches=(direct['archive_info']['hashes']['sha256'] == wheel['digests']['sha256']),
                                             local_METADATA_matches_published_sidecar=(sha(dist / 'METADATA') == expected))
    request('https://raw.githubusercontent.com/pypa/pip/26.1.2/src/pip/_vendor/vendor.txt', 'pip2612-upstream-vendor.txt')
    info['provenance_conclusion'] = 'Publisher expected archive can be mapped; installed interpreter bytes are not proven equal to that archive without a trusted installation receipt or publisher per-file baseline.'
    info['artifact_body_bytes_transferred'] = 0
    (ROOT / 'runtime-inventory.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n')
