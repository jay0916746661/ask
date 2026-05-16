from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
WATCH_DIR = Path(os.environ.get('JIM_BOOK_WATCH_DIR', str(Path.home() / 'Desktop' / '電子書'))).expanduser()
POLL_SECONDS = int(os.environ.get('JIM_BOOK_POLL_SECONDS', '30'))
LOG_FILE = BASE / 'book_sync_watch.log'


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def snapshot() -> dict[str, tuple[int, int]]:
    if not WATCH_DIR.exists():
        return {}
    snap = {}
    for path in WATCH_DIR.iterdir():
        if not path.is_file() or path.suffix.lower() not in {'.pdf', '.epub'}:
            continue
        stat = path.stat()
        snap[str(path)] = (int(stat.st_size), int(stat.st_mtime))
    return snap


def run_sync() -> None:
    result = subprocess.run([sys.executable, str(BASE / 'book_sync.py')], cwd=BASE, text=True, capture_output=True)
    if result.stdout.strip():
        log(result.stdout.strip())
    if result.returncode != 0:
        log(result.stderr.strip() or 'book_sync failed')


def main() -> int:
    log(f'watching {WATCH_DIR}')
    last = snapshot()
    run_sync()
    while True:
        time.sleep(POLL_SECONDS)
        current = snapshot()
        if current != last:
            log('detected folder changes, syncing library')
            run_sync()
            last = current
    
if __name__ == '__main__':
    raise SystemExit(main())
