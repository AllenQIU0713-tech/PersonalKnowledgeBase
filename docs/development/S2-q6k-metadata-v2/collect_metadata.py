"""Read only official metadata; never GET a package or executable artifact.

Uses the packaging parser already bundled with the host's pip. This is an
approval-preparation inventory, not an installer or a product test runner.
"""
import datetime as dt
import email
import hashlib
import html.parser
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener

from pip._vendor.packaging.markers import default_environment
from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.specifiers import SpecifierSet
from pip._vendor.packaging.tags import cpython_tags, compatible_tags, mac_platforms
from pip._vendor.packaging.utils import canonicalize_name, parse_wheel_filename
from pip._vendor.packaging.version import Version, InvalidVersion

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw'
RAW.mkdir(exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc).isoformat()
CUTOFF = '2026-10-17T15:59:59'
TARGET = '3.12.15'
ENV = dict(default_environment(), python_version='3.12', python_full_version=TARGET,
           implementation_name='cpython', implementation_version=TARGET,
           os_name='posix', sys_platform='darwin', platform_machine='arm64',
           platform_system='Darwin', platform_release='25.6.0',
           platform_version='macOS 26.5 target', extra='')
PLATFORMS = list(mac_platforms(version=(26, 5), arch='arm64'))
TAGS = list(cpython_tags(python_version=(3, 12), platforms=PLATFORMS))
TAGS += list(compatible_tags(python_version=(3, 12), interpreter='cp312',
                             platforms=PLATFORMS))
TAG_RANK = {tag: n for n, tag in enumerate(TAGS)}
RECEIPTS = []
CACHE = {}
ROOTS = ['torch==2.11.0', 'numpy~=2.2.6', 'sentencepiece>=0.1.98,<0.3.0',
         'transformers==4.57.6', 'protobuf>=4.21,<5', 'tqdm>=4.27',
         'pyyaml>=5.1', 'requests>=2.25', 'poetry-core>=1.0.0']


def allowed(url, method):
    u = urlsplit(url)
    if u.scheme != 'https':
        return False
    if method == 'HEAD':
        return u.hostname == 'download-r2.pytorch.org' and u.path.endswith('.whl')
    if u.hostname == 'pypi.org':
        return u.path.endswith('/json') or u.path.startswith('/simple/')
    if u.hostname == 'files.pythonhosted.org':
        return u.path.endswith('.whl.metadata')
    if u.hostname == 'download-r2.pytorch.org':
        return u.path.endswith('.whl.metadata')
    return (u.hostname == 'download.pytorch.org' and
            u.path == '/whl/cpu/torch/')


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl, req.get_method()):
            raise ValueError('artifact or non-allowlisted redirect blocked')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = build_opener(SafeRedirect())


def read(url, save=None, accept=None, method='GET'):
    if not allowed(url, method):
        raise ValueError('non-metadata request blocked: ' + url)
    headers = {'User-Agent': 'PKB-Q6-Metadata-Only/2'}
    if accept:
        headers['Accept'] = accept
    req = Request(url, headers=headers, method=method)
    with OPENER.open(req, timeout=30) as response:
        payload = b'' if method == 'HEAD' else response.read(12_000_001)
        if len(payload) > 12_000_000:
            raise ValueError('metadata size cap exceeded')
        receipt = {'url': url, 'final_url': response.url, 'method': method,
                   'retrieved_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                   'body_bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(),
                   'content_type': response.headers.get('Content-Type'),
                   'content_length': response.headers.get('Content-Length'),
                   'artifact_body_bytes': 0}
    if save:
        (RAW / save).write_bytes(payload)
        receipt['raw_file'] = 'raw/' + save
    RECEIPTS.append(receipt)
    (ROOT / 'receipts.json').write_text(json.dumps(RECEIPTS, indent=2) + '\n')
    print(method, url, 'metadata_bytes=' + str(len(payload)), flush=True)
    return payload, receipt


def pypi(name, version=None):
    key = (name, version)
    if key not in CACHE:
        url = 'https://pypi.org/pypi/' + name + ('/' + version if version else '') + '/json'
        save = name + '-' + version + '-pypi.json' if version else None
        CACHE[key] = json.loads(read(url, save=save)[0])
    return CACHE[key]


def wheel_rank(filename):
    try:
        tags = parse_wheel_filename(filename)[3]
    except Exception:
        return None
    ranks = [TAG_RANK[tag] for tag in tags if tag in TAG_RANK]
    return min(ranks) if ranks else None


def choices(name, requirements):
    data = pypi(name)
    versions = []
    for text, files in data['releases'].items():
        try:
            version = Version(text)
        except InvalidVersion:
            continue
        if version.is_prerelease or version.is_devrelease:
            continue
        if not all(version in req.specifier for req in requirements):
            continue
        wheels = []
        for f in files:
            rank = wheel_rank(f['filename'])
            if (rank is None or f.get('yanked') or f.get('packagetype') != 'bdist_wheel' or
                    f.get('upload_time', '') > CUTOFF or
                    TARGET not in SpecifierSet(f.get('requires_python') or '')):
                continue
            wheels.append((rank, f))
        if wheels:
            versions.append((version, text, sorted(wheels, key=lambda x: (x[0], x[1]['filename']))))
    return sorted(versions, key=lambda x: x[0], reverse=True)


class TorchIndex(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.entries = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'href' in attrs:
            self.entries.append(attrs)


def selected_metadata(name, version, wheel):
    key = ('selected', name, version)
    if key in CACHE:
        return CACHE[key]
    release = pypi(name, version)
    filename = wheel['filename']
    if name == 'torch':
        parser = TorchIndex()
        parser.feed(read('https://download.pytorch.org/whl/cpu/torch/',
                         save='torch-cpu-index.html')[0].decode())
        match = [a for a in parser.entries
                 if unquote(urlsplit(a['href']).path).endswith('/' + filename)]
        if len(match) != 1:
            raise ValueError('CPU index artifact is missing/ambiguous')
        entry = match[0]
        url, fragment = entry['href'].split('#', 1)
        artifact_hash = fragment.removeprefix('sha256=') if hasattr(str, 'removeprefix') else fragment[7:]
        sidecar_hash = entry['data-core-metadata'].split('=', 1)[1]
        _, head = read(url, method='HEAD')
        size = int(head['content_length'])
        index = 'https://download.pytorch.org/whl/cpu/torch/'
    else:
        simple = json.loads(read('https://pypi.org/simple/' + name + '/',
                                 accept='application/vnd.pypi.simple.v1+json')[0])
        matches = [f for f in simple['files'] if f['filename'] == filename]
        if len(matches) != 1:
            raise ValueError('PyPI artifact is missing/ambiguous')
        entry = matches[0]
        md = entry.get('core-metadata') or entry.get('dist-info-metadata')
        if not isinstance(md, dict) or 'sha256' not in md:
            raise ValueError('verified PEP 658 metadata unavailable: ' + filename)
        sidecar_hash = md['sha256']
        url, size, artifact_hash = wheel['url'], wheel['size'], wheel['digests']['sha256']
        if entry['hashes']['sha256'] != artifact_hash:
            raise ValueError('PyPI JSON/simple artifact hash mismatch')
        index = 'https://pypi.org/simple/' + name + '/'
    metadata, receipt = read(url + '.metadata', save=filename + '.metadata')
    if receipt['sha256'] != sidecar_hash or not metadata.startswith(b'Metadata-Version:'):
        raise ValueError('PEP 658 metadata integrity mismatch')
    msg = email.message_from_bytes(metadata)
    if canonicalize_name(msg['Name']) != name or Version(msg['Version']) != Version(version):
        raise ValueError('selected wheel metadata identity mismatch')
    result = {'name': name, 'version': version, 'filename': filename,
              'url': url, 'index': index, 'bytes': size, 'sha256': artifact_hash,
              'wheel_tags': sorted(str(t) for t in parse_wheel_filename(filename)[3]),
              'requires_python': msg.get('Requires-Python'),
              'requires_dist': msg.get_all('Requires-Dist', []),
              'metadata_sha256': sidecar_hash,
              'metadata_file': receipt['raw_file'],
              'license_expression': msg.get('License-Expression'),
              'license_classifiers': [c for c in msg.get_all('Classifier', []) if c.startswith('License ::')],
              'license_declared': msg.get('License'),
              'license_files': msg.get_all('License-File', []),
              'license_evidence': 'selected-wheel-publisher-metadata; bundled files not inspected'}
    if name == 'torch':
        result['same_name_pypi_artifact'] = {
            'url': wheel['url'], 'bytes': wheel['size'],
            'sha256': wheel['digests']['sha256'], 'selected': False}
    CACHE[key] = result
    return result


def solve(constraints, selected):
    unresolved = [name for name in constraints if name not in selected]
    if not unresolved:
        return selected
    name = unresolved[0]
    for _, version, wheels in choices(name, constraints[name]):
        for _, wheel in wheels:
            item = selected_metadata(name, version, wheel)
            new_constraints = {n: list(v) for n, v in constraints.items()}
            new_selected = dict(selected, **{name: item})
            valid = True
            for text in item['requires_dist']:
                req = Requirement(text)
                if req.marker and not req.marker.evaluate(ENV):
                    continue
                if req.url or req.extras:
                    raise ValueError('direct URL/extras need explicit review: ' + text)
                key = canonicalize_name(req.name)
                new_constraints.setdefault(key, []).append(req)
                if key in new_selected and Version(new_selected[key]['version']) not in req.specifier:
                    valid = False
                    break
            if valid:
                result = solve(new_constraints, new_selected)
                if result is not None:
                    return result
            break
    return None


if __name__ == '__main__':
    try:
        constraints = {}
        for text in ROOTS:
            req = Requirement(text)
            constraints.setdefault(canonicalize_name(req.name), []).append(req)
        selected = solve(constraints, {})
        if selected is None:
            raise ValueError('no complete metadata-only candidate solution')
        for item in selected.values():
            item['active_dependencies'] = []
            item['excluded_by_target_marker'] = []
            for text in item['requires_dist']:
                req = Requirement(text)
                if req.marker and not req.marker.evaluate(ENV):
                    item['excluded_by_target_marker'].append(text)
                else:
                    dep = selected[canonicalize_name(req.name)]
                    if Version(dep['version']) not in req.specifier:
                        raise ValueError('candidate solution violates requirement: ' + text)
                    item['active_dependencies'].append(text)
        result = {'schema_version': 1, 'status': 'candidate_metadata_only_awaiting_audit',
                  'approval_status': 'approval_blocked', 'created_at': NOW,
                  'collector_python': sys.version, 'collector_executable': sys.executable,
                  'packaging_source': 'existing system pip._vendor.packaging',
                  'target_marker_environment': ENV, 'target_platform': 'macOS 26.5 arm64',
                  'python_target_provenance': '3.12.15 marker target only; runtime artifact not selected',
                  'source_strategy': 'torch CPU index only; all other wheels PyPI only; local gguf source separately',
                  'root_requirements': ROOTS, 'wheels': sorted(selected.values(), key=lambda x: x['name']),
                  'wheel_count': len(selected),
                  'wheel_artifact_total_bytes': sum(x['bytes'] for x in selected.values()),
                  'package_artifact_body_bytes_transferred_by_collector': 0,
                  'limitations': ['No artifacts downloaded/installed or licenses inside archives inspected',
                                  'Runtime/toolchain/source archive provenance and complete budget still pending',
                                  'This custom metadata candidate solution requires independent audit; not an installation lock']}
        (ROOT / 'wheel-inventory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print('COMPLETE', result['wheel_count'], result['wheel_artifact_total_bytes'], flush=True)
    except Exception as exc:
        (ROOT / 'collection-error.json').write_text(json.dumps({'type': type(exc).__name__, 'error': str(exc)}, indent=2) + '\n')
        raise
