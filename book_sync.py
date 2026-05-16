from __future__ import annotations

import json
import os
import re
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

BASE = Path(__file__).resolve().parent
LIBRARY_FILE = BASE / 'book_library.json'
META_FILE = BASE / 'book_sync_meta.json'
WATCH_DIR = Path(os.environ.get('JIM_BOOK_WATCH_DIR', str(Path.home() / 'Desktop' / '電子書'))).expanduser()
WATCH_EXTS = {'.pdf', '.epub'}
PREVIEW_CHARS = 900
COVER_DIR = BASE / 'book_covers'

DRIVE_FOLDERS = {
    '1M5rpvl_NhAMxyHI0ctESFTVk1PCgI-SP': '電子書',
    '1dkXy8stPOmvIFpv1kqY6AXcwtFvRDQ0w': '待看電子書',
}

CATEGORY_KEYWORDS = {
    '投資/財富': ['投資', '財富', '錢', '理財', '股票', '經濟', '致富', '資產', 'money', '金錢', '退休', '財務', '商業金融'],
    'AI/科技': ['ai', '人工智慧', 'gpt', 'agent', '科技', '程式', '大腦', '第二大腦', 'machine learning', 'deep learning'],
    '人性/心理': ['人性', '心理', '洞察', '博弈', '消費', '認知', '思考', '自卑', 'scarcity', 'mindfuck', '情緒'],
    '生活/心智': ['生活', '冥想', '專注', '習慣', '成長', '覺悟', '多巴胺', '軟技能', '破圈', '睡覺', '學習'],
    '溝通/談判': ['談判', '溝通', '關係', '說話', '影響', '表達', 'body language', '身體語言'],
    '商業/創業': ['商業', '變現', '社群', '行銷', '創業', 'sales', '產品', '品牌'],
    '其他': [],
}


def ensure_cover_dir() -> None:
    COVER_DIR.mkdir(parents=True, exist_ok=True)


def clean_title(raw: str) -> str:
    name = Path(raw).stem
    name = re.sub(r'\s*[=＝]\s*.*', '', name)
    name = re.sub(r'\s*\((z-library|1lib|z-lib).*?\)$', '', name, flags=re.I)
    name = re.sub(r'\s*\((z-library|1lib|z-lib).*?\)', '', name, flags=re.I)
    name = re.sub(r'\s{2,}', ' ', name)
    return name.strip(' -_')


def guess_category(title: str) -> str:
    t = title.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if cat == '其他':
            continue
        if any(k.lower() in t for k in kws):
            return cat
    return '其他'


def extract_author(raw: str) -> str:
    matches = re.findall(r'\(([^()]{2,60})\)', raw)
    for candidate in matches:
        if re.search(r'z-library|1lib|z-lib', candidate, re.I):
            continue
        return candidate.strip()
    return ''


def strip_html(text: str) -> str:
    text = re.sub(r'<script.*?>.*?</script>', ' ', text, flags=re.I | re.S)
    text = re.sub(r'<style.*?>.*?</style>', ' ', text, flags=re.I | re.S)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;|&#160;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def save_cover_bytes(book_id: str, ext: str, data: bytes) -> str:
    ensure_cover_dir()
    ext = ext.lower().lstrip('.') or 'jpg'
    if ext == 'jpeg':
        ext = 'jpg'
    out = COVER_DIR / f'{book_id}.{ext}'
    out.write_bytes(data)
    return str(out)


def extract_epub_cover(path: Path, book_id: str) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            opf_name = next((n for n in names if n.lower().endswith('.opf')), '')
            cover_href = ''
            if opf_name:
                root = ET.fromstring(zf.read(opf_name))
                ns = {'opf': 'http://www.idpf.org/2007/opf'}
                meta_cover = root.find('.//opf:meta[@name="cover"]', ns)
                if meta_cover is not None:
                    cover_id = meta_cover.attrib.get('content', '')
                    if cover_id:
                        item = root.find(f".//opf:item[@id='{cover_id}']", ns)
                        if item is not None:
                            cover_href = item.attrib.get('href', '')
                if not cover_href:
                    for item in root.findall('.//opf:item', ns):
                        href = item.attrib.get('href', '')
                        item_id = item.attrib.get('id', '')
                        props = item.attrib.get('properties', '')
                        if 'cover-image' in props or 'cover' in item_id.lower() or 'cover' in href.lower():
                            cover_href = href
                            break
                if cover_href:
                    base = Path(opf_name).parent
                    candidate = (base / cover_href).as_posix()
                    if candidate in names:
                        return save_cover_bytes(book_id, Path(candidate).suffix or '.jpg', zf.read(candidate))
            fallback = next((n for n in names if 'cover' in n.lower() and n.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))), '')
            if not fallback:
                fallback = next((n for n in names if n.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))), '')
            if fallback:
                return save_cover_bytes(book_id, Path(fallback).suffix or '.jpg', zf.read(fallback))
    except Exception:
        return ''
    return ''


def extract_pdf_cover(path: Path, book_id: str) -> str:
    try:
        import fitz
    except Exception:
        return ''
    try:
        ensure_cover_dir()
        out = COVER_DIR / f'{book_id}.jpg'
        if out.exists() and out.stat().st_size > 0:
            return str(out)
        doc = fitz.open(path)
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False)
        pix.save(out)
        doc.close()
        return str(out)
    except Exception:
        return ''


def extract_cover(path: Path, book_id: str) -> str:
    if path.suffix.lower() == '.epub':
        return extract_epub_cover(path, book_id)
    if path.suffix.lower() == '.pdf':
        return extract_pdf_cover(path, book_id)
    return ''


def extract_epub_preview(path: Path) -> tuple[str, int | None]:
    try:
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(('.html', '.xhtml', '.htm'))]
            parts = []
            for name in names[:8]:
                try:
                    raw = zf.read(name).decode('utf-8', errors='ignore')
                except Exception:
                    continue
                text = strip_html(raw)
                if text:
                    parts.append(text)
                if sum(len(x) for x in parts) >= PREVIEW_CHARS:
                    break
            preview = '\n\n'.join(parts)[:PREVIEW_CHARS].strip()
            return preview, len(names) or None
    except Exception:
        return '', None


def extract_pdf_preview(path: Path) -> tuple[str, int | None]:
    try:
        import fitz
    except Exception:
        return '', None
    try:
        doc = fitz.open(path)
        texts = []
        page_count = len(doc)
        for idx in range(min(8, page_count)):
            text = doc[idx].get_text('text')
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                texts.append(text)
            if sum(len(x) for x in texts) >= PREVIEW_CHARS:
                break
        doc.close()
        return '\n\n'.join(texts)[:PREVIEW_CHARS].strip(), page_count
    except Exception:
        return '', None


def extract_preview(path: Path) -> tuple[str, int | None]:
    if path.suffix.lower() == '.epub':
        return extract_epub_preview(path)
    if path.suffix.lower() == '.pdf':
        return extract_pdf_preview(path)
    return '', None


def scan_local_books() -> list[dict]:
    books = []
    if not WATCH_DIR.exists():
        return books
    for path in sorted(WATCH_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file() or path.suffix.lower() not in WATCH_EXTS:
            continue
        stat = path.stat()
        title = clean_title(path.name)
        book_id = f'local_{abs(hash(str(path))) % 10**12:012d}'
        preview, page_count = extract_preview(path)
        cover_path = extract_cover(path, book_id)
        books.append({
            'id': book_id,
            'title': title,
            'author': extract_author(path.name),
            'category': guess_category(title),
            'source': '本機',
            'folder': str(WATCH_DIR),
            'format': path.suffix.lower().lstrip('.'),
            'size_mb': round(stat.st_size / 1024 / 1024, 2),
            'mtime': int(stat.st_mtime),
            'added_date': time.strftime('%Y-%m-%d', time.localtime(stat.st_mtime)),
            'local_path': str(path),
            'exists': True,
            'preview': preview,
            'page_count': page_count,
            'cover_path': cover_path,
        })
    return books


def scan_drive_books() -> list[dict]:
    try:
        import gdown
    except Exception:
        return []

    books = []
    for folder_id, shelf in DRIVE_FOLDERS.items():
        url = f'https://drive.google.com/drive/folders/{folder_id}'
        try:
            files = gdown.download_folder(url, quiet=True, use_cookies=False, skip_download=True)
        except Exception:
            continue
        if not files:
            continue
        seen = set()
        for f in files:
            raw_name = Path(f.path).name if hasattr(f, 'path') else str(f)
            title = clean_title(raw_name)
            if not title or title in seen:
                continue
            seen.add(title)
            books.append({
                'id': f'drive_{folder_id[-6:]}_{abs(hash(title)) % 10**10:010d}',
                'title': title,
                'author': extract_author(raw_name),
                'category': guess_category(title),
                'source': 'Google Drive',
                'folder': shelf,
                'format': Path(raw_name).suffix.lower().lstrip('.'),
                'size_mb': None,
                'mtime': 0,
                'added_date': time.strftime('%Y-%m-%d'),
                'local_path': '',
                'exists': False,
                'preview': '',
                'page_count': None,
                'cover_path': '',
            })
    return books


def merge_books(local_books: list[dict], drive_books: list[dict]) -> list[dict]:
    merged = {}
    for book in drive_books + local_books:
        key = book['title'].strip().lower()
        current = merged.get(key)
        if not current:
            merged[key] = dict(book)
            continue
        if current['source'] != book['source']:
            current['source'] = '本機 + Google Drive'
        if book.get('exists'):
            current['exists'] = True
            current['local_path'] = book.get('local_path', '')
            current['format'] = book.get('format') or current.get('format')
            current['size_mb'] = book.get('size_mb') or current.get('size_mb')
            current['mtime'] = max(int(current.get('mtime') or 0), int(book.get('mtime') or 0))
            current['added_date'] = book.get('added_date') or current.get('added_date')
            current['preview'] = book.get('preview') or current.get('preview', '')
            current['page_count'] = book.get('page_count') or current.get('page_count')
            current['cover_path'] = book.get('cover_path') or current.get('cover_path', '')
        if not current.get('author') and book.get('author'):
            current['author'] = book['author']
        if current.get('category') == '其他' and book.get('category') and book['category'] != '其他':
            current['category'] = book['category']
    items = list(merged.values())
    items.sort(key=lambda x: (int(x.get('mtime') or 0), x.get('added_date') or '', x['title']), reverse=True)
    return items


def main() -> int:
    local_books = scan_local_books()
    drive_books = scan_drive_books()
    library = merge_books(local_books, drive_books)
    LIBRARY_FILE.write_text(json.dumps(library, ensure_ascii=False, indent=2), encoding='utf-8')
    META_FILE.write_text(json.dumps({
        'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'watch_dir': str(WATCH_DIR),
        'local_count': len(local_books),
        'drive_count': len(drive_books),
        'merged_count': len(library),
        'cover_count': sum(1 for b in library if b.get('cover_path')),
        'preview_count': sum(1 for b in library if b.get('preview')),
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"updated library: local={len(local_books)} drive={len(drive_books)} merged={len(library)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
