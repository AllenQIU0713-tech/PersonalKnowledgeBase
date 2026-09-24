import os
from pathlib import Path

MAX_FILE = 25 * 1024 * 1024
MAX_REQUEST = 36 * 1024 * 1024
MIN_FREE = 128 * 1024 * 1024
DEFAULT_DATA = Path.home() / 'Library/Application Support/PersonalKnowledgeBase'


def data_directory(value=None):
    path = Path(value or os.environ.get('PKB_DATA_DIR') or DEFAULT_DATA).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    (path / 'originals').mkdir(exist_ok=True, mode=0o700)
    return path
