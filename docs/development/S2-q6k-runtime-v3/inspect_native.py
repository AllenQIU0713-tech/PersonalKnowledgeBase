"""Hash installed native inputs and read Mach-O load metadata without loading them."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent
PREFIX = Path('/Users/allenqiu/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none')
paths = {path.resolve() for pattern in ('*.dylib', '*.so') for path in (PREFIX / 'lib').rglob(pattern)}
paths.add((PREFIX / 'bin/python3.12').resolve())
inventory = []
for path in sorted(paths):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(block)
    inventory.append({'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()})
commands = {
    'native-loads.txt': ['/usr/bin/otool', '-L'] + [str(path) for path in sorted(paths)],
    'native-file-types.txt': ['/usr/bin/file'] + [str(path) for path in sorted(paths)],
    'current-os.txt': ['/usr/bin/sw_vers'],
    'current-sdk.txt': ['/usr/bin/xcrun', '--show-sdk-version'],
    'current-clang.txt': ['/usr/bin/clang', '--version'],
    'current-clt.txt': ['/usr/sbin/pkgutil', '--pkg-info', 'com.apple.pkg.CLTools_Executables'],
}
records = []
for name, argv in commands.items():
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (ROOT / 'raw' / name).write_bytes(result.stdout)
    records.append({'argv': argv, 'returncode': result.returncode,
                    'stdout_file': 'raw/' + name,
                    'stdout_sha256': hashlib.sha256(result.stdout).hexdigest(),
                    'stderr': result.stderr.decode(errors='replace')})
out = {'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'native_files': inventory, 'native_file_count': len(inventory), 'commands': records,
       'scope': 'Current local bytes and static Mach-O load declarations only; no publisher per-file baseline or runtime approval',
       'model_or_product_tests_run': 0}
(ROOT / 'native-inventory.json').write_text(json.dumps(out, indent=2) + '\n')
print('Native inputs hashed:', len(inventory), '; metadata commands:', len(records))
