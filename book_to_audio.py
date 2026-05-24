from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Iterable

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

BASE = Path(__file__).resolve().parent
LIBRARY_FILE = BASE / 'book_library.json'
OUTPUT_DIR = BASE / 'audio_books'
DEFAULT_CHUNK_CHARS = 2200
DEFAULT_RATE = 190
PREFERRED_VOICES = ['Ting-Ting', 'Meijia', 'Sin-ji', 'Kyoko']
AUDIO_INDEX_FILE = OUTPUT_DIR / 'audio_index.json'


def load_library() -> list[dict]:
    return json.loads(LIBRARY_FILE.read_text(encoding='utf-8'))


def normalize_text(text: str) -> str:
    text = str(text or '').replace('\r', '\n').replace('\x00', '')
    text = re.sub(r'<script.*?>.*?</script>', ' ', text, flags=re.I | re.S)
    text = re.sub(r'<style.*?>.*?</style>', ' ', text, flags=re.I | re.S)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;|&#160;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def clean_title(title: str) -> str:
    title = re.sub(r'\s*[=＝]\s*.*', '', title)
    title = re.sub(r'\s*\((z-library|1lib|z-lib).*?\)$', '', title, flags=re.I)
    title = re.sub(r'\s*\((z-library|1lib|z-lib).*?\)', '', title, flags=re.I)
    title = re.sub(r'\s{2,}', ' ', title)
    return title.strip(' -_')


def extract_epub_text(path: Path) -> tuple[str, int]:
    docs: list[str] = []
    with zipfile.ZipFile(path) as zf:
        names = sorted(n for n in zf.namelist() if n.lower().endswith(('.html', '.xhtml', '.htm')))
        for name in names:
            try:
                raw = zf.read(name).decode('utf-8', errors='ignore')
            except Exception:
                continue
            text = normalize_text(raw)
            if len(text) > 20:
                docs.append(text)
    return '\n\n'.join(docs), len(docs)


def extract_pdf_text(path: Path) -> tuple[str, int]:
    if fitz is None:
        raise RuntimeError('PyMuPDF 未安裝，無法讀取 PDF。')
    doc = fitz.open(path)
    try:
        pages = []
        for i in range(doc.page_count):
            text = normalize_text(doc.load_page(i).get_text('text'))
            if text:
                pages.append(text)
        return '\n\n'.join(pages), doc.page_count
    finally:
        doc.close()


def extract_full_text(book: dict) -> tuple[str, int]:
    local_path = Path(book.get('local_path', ''))
    if not local_path.exists():
        raise FileNotFoundError(f'找不到本機書檔：{local_path}')
    suffix = local_path.suffix.lower()
    if suffix == '.epub':
        return extract_epub_text(local_path)
    if suffix == '.pdf':
        return extract_pdf_text(local_path)
    raise ValueError(f'不支援的格式：{suffix}')


def split_sentences(text: str) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []
    parts = re.split(r'(?<=[。！？!?\.])\s+|\n\n+', text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(text: str, max_chars: int = DEFAULT_CHUNK_CHARS) -> list[str]:
    sentences = split_sentences(text)
    if not sentences:
        return []
    chunks: list[str] = []
    buf = ''
    for sent in sentences:
        if len(sent) > max_chars:
            if buf:
                chunks.append(buf.strip())
                buf = ''
            for i in range(0, len(sent), max_chars):
                chunks.append(sent[i:i + max_chars].strip())
            continue
        candidate = f'{buf} {sent}'.strip() if buf else sent
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            chunks.append(buf.strip())
            buf = sent
    if buf:
        chunks.append(buf.strip())
    return chunks


def sanitize_name(name: str) -> str:
    return re.sub(r'[^\w\-\u4e00-\u9fff]+', '_', name).strip('_') or 'book'


def available_voices() -> list[str]:
    try:
        out = subprocess.check_output(['/usr/bin/say', '-v', '?'], text=True, encoding='utf-8', errors='ignore')
    except Exception:
        return []
    voices = []
    for line in out.splitlines():
        if not line.strip():
            continue
        voices.append(line.split()[0])
    return voices


def pick_voice(preferred: str | None = None) -> str | None:
    voices = available_voices()
    if preferred and preferred in voices:
        return preferred
    for voice in PREFERRED_VOICES:
        if voice in voices:
            return voice
    return voices[0] if voices else None


def seconds_estimate(text: str, rate: int) -> int:
    words = max(1, len(re.findall(r'\S+', text)))
    return round((words / max(rate, 1)) * 60)


def synthesize_chunk(text_path: Path, out_m4a: Path, voice: str | None, rate: int) -> None:
    aiff_path = out_m4a.with_suffix('.aiff')
    cmd = ['/usr/bin/say']
    if voice:
        cmd += ['-v', voice]
    cmd += ['-r', str(rate), '-f', str(text_path), '-o', str(aiff_path)]
    subprocess.run(cmd, check=True)
    subprocess.run([
        '/usr/bin/afconvert',
        '-f', 'm4af',
        '-d', 'aac',
        str(aiff_path),
        str(out_m4a),
    ], check=True)
    aiff_path.unlink(missing_ok=True)


def write_playlist(book_dir: Path, audio_files: Iterable[Path]) -> None:
    playlist = book_dir / 'playlist.m3u'
    lines = ['#EXTM3U'] + [f.name for f in audio_files]
    playlist.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def rebuild_audio_index() -> list[dict]:
    entries: list[dict] = []
    if not OUTPUT_DIR.exists():
        AUDIO_INDEX_FILE.write_text('[]\n', encoding='utf-8')
        return entries
    for manifest_path in sorted(OUTPUT_DIR.glob('*/manifest.json')):
        try:
            data = json.loads(manifest_path.read_text(encoding='utf-8'))
        except Exception:
            continue
        book_dir = manifest_path.parent
        entries.append({
            'id': data.get('id', ''),
            'title': data.get('title', ''),
            'author': data.get('author', ''),
            'category': data.get('category', ''),
            'voice': data.get('voice', ''),
            'rate': data.get('rate', 0),
            'chunk_count': data.get('chunk_count', 0),
            'source_pages': data.get('source_pages', 0),
            'total_seconds_estimate': data.get('total_seconds_estimate', 0),
            'generated_at': data.get('generated_at', ''),
            'playlist': str((book_dir / 'playlist.m3u').resolve()),
            'full_text': str((book_dir / 'full_text.txt').resolve()),
            'audio_dir': str((book_dir / 'audio_chunks').resolve()),
            'manifest_path': str(manifest_path.resolve()),
            'sample_audio': str((book_dir / 'audio_chunks' / '0001.m4a').resolve()),
        })
    AUDIO_INDEX_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
    return entries


def convert_book(book: dict, voice: str | None, rate: int, max_chars: int, limit_chunks: int | None = None, force: bool = False) -> dict:
    title = clean_title(book.get('title', '未命名書籍'))
    book_id = book.get('id') or sanitize_name(title)
    book_dir = OUTPUT_DIR / f'{book_id}_{sanitize_name(title)[:60]}'
    text_dir = book_dir / 'text_chunks'
    audio_dir = book_dir / 'audio_chunks'
    book_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    full_text, source_pages = extract_full_text(book)
    full_text = normalize_text(full_text)
    if len(full_text) < 200:
        raise RuntimeError('抽出的全文過短，可能是掃描型 PDF 或無可讀文字。')

    (book_dir / 'full_text.txt').write_text(full_text, encoding='utf-8')
    chunks = chunk_text(full_text, max_chars=max_chars)
    if limit_chunks is not None:
        chunks = chunks[:limit_chunks]

    manifest = {
        'output_dir': str(book_dir.resolve()),
        'id': book_id,
        'title': title,
        'author': book.get('author', ''),
        'category': book.get('category', '其他'),
        'source_path': book.get('local_path', ''),
        'format': book.get('format', ''),
        'source_pages': source_pages,
        'chunk_count': len(chunks),
        'voice': voice,
        'rate': rate,
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'files': [],
    }

    audio_files: list[Path] = []
    for idx, chunk in enumerate(chunks, start=1):
        txt_file = text_dir / f'{idx:04d}.txt'
        out_file = audio_dir / f'{idx:04d}.m4a'
        txt_file.write_text(chunk, encoding='utf-8')
        if force or not out_file.exists():
            synthesize_chunk(txt_file, out_file, voice, rate)
        duration = seconds_estimate(chunk, rate)
        manifest['files'].append({
            'index': idx,
            'text_file': str(txt_file),
            'audio_file': str(out_file),
            'chars': len(chunk),
            'seconds_estimate': duration,
        })
        audio_files.append(out_file)

    manifest['total_seconds_estimate'] = sum(x['seconds_estimate'] for x in manifest['files'])
    (book_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    write_playlist(book_dir, audio_files)
    return manifest


def select_books(library: list[dict], book_id: str | None, title_keyword: str | None, all_books: bool) -> list[dict]:
    if all_books:
        return [b for b in library if b.get('exists') and b.get('local_path')]
    if book_id:
        return [b for b in library if b.get('id') == book_id]
    if title_keyword:
        keyword = title_keyword.lower().strip()
        return [b for b in library if keyword in str(b.get('title', '')).lower()]
    raise SystemExit('請至少提供 --book-id、--title 或 --all')


def main() -> None:
    parser = argparse.ArgumentParser(description='把電子書批次轉成整本語音 chunk 檔案')
    parser.add_argument('--book-id', help='指定書籍 ID')
    parser.add_argument('--title', help='用書名關鍵字選書')
    parser.add_argument('--all', action='store_true', help='處理所有本機書')
    parser.add_argument('--voice', help='指定 macOS say 聲音，例如 Ting-Ting')
    parser.add_argument('--rate', type=int, default=DEFAULT_RATE, help='朗讀速度，預設 190')
    parser.add_argument('--max-chars', type=int, default=DEFAULT_CHUNK_CHARS, help='每段最大字元數')
    parser.add_argument('--limit-chunks', type=int, help='只轉前幾段，方便測試')
    parser.add_argument('--force', action='store_true', help='強制重做已存在的音檔')
    args = parser.parse_args()

    if not LIBRARY_FILE.exists():
        raise SystemExit(f'找不到 {LIBRARY_FILE}')
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    library = load_library()
    books = select_books(library, args.book_id, args.title, args.all)
    if not books:
        raise SystemExit('找不到符合條件的書')

    voice = pick_voice(args.voice)
    print(f'voice={voice or "default"}')
    for book in books:
        print(f'\n=== 轉換：{book.get("title")} ===')
        manifest = convert_book(book, voice=voice, rate=args.rate, max_chars=args.max_chars, limit_chunks=args.limit_chunks, force=args.force)
        print(f"完成：{manifest['chunk_count']} 段，約 {manifest['total_seconds_estimate'] // 60} 分鐘")
        print(f"輸出：{OUTPUT_DIR / (manifest['id'] + '_' + sanitize_name(manifest['title'])[:60])}")
    index = rebuild_audio_index()
    print(f'\n已更新整體索引：{AUDIO_INDEX_FILE} · 共 {len(index)} 本')


if __name__ == '__main__':
    main()
