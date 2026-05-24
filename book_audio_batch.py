from __future__ import annotations

import argparse
import json
import subprocess
import sys
import re
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
LIBRARY_FILE = BASE / 'book_library.json'
AUDIO_DIR = BASE / 'audio_books'
LOG_FILE = BASE / 'audio_books' / 'batch_convert.log'
STATUS_FILE = BASE / 'audio_books' / 'batch_status.json'
SCRIPT = BASE / 'book_to_audio.py'


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def log(msg: str) -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG_FILE.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def completed_ids() -> set[str]:
    done = set()
    for manifest in AUDIO_DIR.glob('*/manifest.json'):
        data = load_json(manifest, {})
        if data.get('id') and int(data.get('chunk_count') or 0) > 0:
            done.add(data['id'])
    return done


def looks_like_real_book(book: dict) -> bool:
    title = str(book.get('title') or '').strip()
    if len(title) < 6:
        return False
    if re.fullmatch(r'[A-Z0-9_() .-]{1,16}', title):
        return False
    pages = int(book.get('page_count') or 0)
    return pages == 0 or pages >= 10


def pick_books(library: list[dict], include_pdf: bool) -> list[dict]:
    done = completed_ids()
    out = []
    for b in library:
        if not b.get('exists') or not b.get('local_path'):
            continue
        if b.get('id') in done:
            continue
        if not looks_like_real_book(b):
            continue
        fmt = str(b.get('format') or '').lower()
        if fmt == 'pdf' and not include_pdf:
            continue
        if fmt not in {'epub', 'pdf'}:
            continue
        out.append(b)
    out.sort(key=lambda b: (
        str(b.get('format')).lower() != 'epub',
        not bool(b.get('cover_path')),
        max(10, min(int(b.get('page_count') or 9999), 160)),
        b.get('title', ''),
    ))
    return out


def write_status(status: dict) -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description='批次把書庫電子書轉成整本語音')
    parser.add_argument('--max-books', type=int, default=5, help='這次最多轉幾本，預設 5')
    parser.add_argument('--include-pdf', action='store_true', help='也處理 PDF；預設先處理 EPUB')
    parser.add_argument('--force', action='store_true', help='傳給 book_to_audio.py 重新生成')
    args = parser.parse_args()

    library = load_json(LIBRARY_FILE, [])
    queue = pick_books(library, include_pdf=args.include_pdf)[:args.max_books]
    log(f'queue={len(queue)} max_books={args.max_books} include_pdf={args.include_pdf}')
    if not queue:
        write_status({'state': 'idle', 'message': 'no queued books', 'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')})
        return

    for idx, book in enumerate(queue, 1):
        title = book.get('title', '')
        book_id = book.get('id', '')
        write_status({
            'state': 'running',
            'current_index': idx,
            'total': len(queue),
            'book_id': book_id,
            'title': title,
            'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        })
        log(f'[{idx}/{len(queue)}] START {book_id} {title}')
        cmd = [sys.executable, str(SCRIPT), '--book-id', book_id]
        if args.force:
            cmd.append('--force')
        proc = subprocess.run(cmd, cwd=BASE, text=True, capture_output=True)
        if proc.returncode == 0:
            log(f'[{idx}/{len(queue)}] DONE {book_id}')
            if proc.stdout.strip():
                log(proc.stdout.strip().splitlines()[-1])
        else:
            log(f'[{idx}/{len(queue)}] FAIL {book_id}')
            if proc.stderr.strip():
                log(proc.stderr.strip()[-1200:])

    write_status({'state': 'done', 'processed': len(queue), 'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')})
    log('batch complete')


if __name__ == '__main__':
    main()
