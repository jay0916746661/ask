import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
import streamlit as st

st.set_page_config(page_title='有聲書中心', layout='wide')

BASE = Path(os.path.dirname(os.path.dirname(__file__)))
AUDIO_DIR = BASE / 'audio_books'
AUDIO_INDEX_FILE = AUDIO_DIR / 'audio_index.json'
LIBRARY_FILE = BASE / 'book_library.json'
AUDIO_SCRIPT = BASE / 'book_to_audio.py'
BATCH_SCRIPT = BASE / 'book_audio_batch.py'
BATCH_STATUS = AUDIO_DIR / 'batch_status.json'
CLOUD_AUDIO_DIR = Path(os.environ.get(
    'JIM_AUDIO_CLOUD_DIR',
    str(Path.home() / 'Library' / 'CloudStorage' / 'GoogleDrive-jay0916746661@gmail.com' / '我的雲端硬碟' / 'Jim有聲書'),
)).expanduser()


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def format_time(seconds: int) -> str:
    seconds = int(seconds or 0)
    if seconds < 60:
        return f'{seconds} 秒'
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f'{minutes} 分 {sec} 秒' if sec else f'{minutes} 分'
    hours, minutes = divmod(minutes, 60)
    return f'{hours}h {minutes}m' if minutes else f'{hours}h'


def run_audio(book_id: str, limit_chunks: int | None = None, force: bool = False):
    cmd = [sys.executable, str(AUDIO_SCRIPT), '--book-id', book_id]
    if limit_chunks:
        cmd += ['--limit-chunks', str(limit_chunks)]
    if force:
        cmd += ['--force']
    result = subprocess.run(cmd, cwd=BASE, text=True, capture_output=True)
    return result.returncode == 0, result.stdout, result.stderr


def start_batch(max_books: int = 5):
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    out = (AUDIO_DIR / 'batch_current.stdout.log').open('w')
    err = (AUDIO_DIR / 'batch_current.stderr.log').open('w')
    proc = subprocess.Popen(
        [sys.executable, str(BATCH_SCRIPT), '--max-books', str(max_books)],
        cwd=BASE,
        stdout=out,
        stderr=err,
        start_new_session=True,
    )
    return proc.pid


def audio_output_dir(entry: dict) -> Path | None:
    manifest_path = Path(entry.get('manifest_path', ''))
    if manifest_path.exists():
        return manifest_path.parent
    audio_dir = Path(entry.get('audio_dir', ''))
    return audio_dir.parent if audio_dir.exists() else None


def sync_audio_to_cloud(entry: dict) -> Path:
    src = audio_output_dir(entry)
    if not src or not src.exists():
        raise FileNotFoundError('找不到這本有聲書的輸出資料夾')
    CLOUD_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    dest = CLOUD_AUDIO_DIR / src.name
    shutil.copytree(src, dest, dirs_exist_ok=True)
    return dest


def book_map(books: list[dict]) -> dict:
    return {b.get('id', ''): b for b in books if b.get('id')}


def audio_label(item: dict) -> str:
    return f"第 {int(item.get('index', 0)):03d} 段 · {format_time(item.get('seconds_estimate', 0))}"


st.title('🎧 有聲書中心')
st.caption('把你的電子書轉成整本語音，直接播放，並同步到 Google Drive。')

books = load_json(LIBRARY_FILE, [])
books_by_id = book_map(books)
audio_rows = sorted(load_json(AUDIO_INDEX_FILE, []), key=lambda r: r.get('generated_at', ''), reverse=True)
batch = load_json(BATCH_STATUS, {})
cloud_count = len(list(CLOUD_AUDIO_DIR.rglob('*.m4a'))) if CLOUD_AUDIO_DIR.exists() else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric('有聲書', len(audio_rows))
m2.metric('段數', sum(int(x.get('chunk_count') or 0) for x in audio_rows))
m3.metric('可聽時間', format_time(sum(int(x.get('total_seconds_estimate') or 0) for x in audio_rows)))
m4.metric('Drive 音檔', cloud_count)

if batch.get('state') == 'running':
    st.info(f"背景批次：{batch.get('current_index', '?')} / {batch.get('total', '?')} · {batch.get('title', '')}")
elif batch.get('state') == 'done':
    st.success(f"背景批次已完成 · {batch.get('updated_at', '')}")

player_tab, generate_tab, cloud_tab = st.tabs(['播放器', '生成', '雲端同步'])

with player_tab:
    if not audio_rows:
        st.info('目前還沒有已生成的有聲書。')
    else:
        labels = [f"{x.get('title', '')} · {x.get('chunk_count', 0)} 段 · {format_time(x.get('total_seconds_estimate', 0))}" for x in audio_rows]
        selected_label = st.selectbox('選擇有聲書', labels)
        entry = audio_rows[labels.index(selected_label)]
        manifest = load_json(Path(entry.get('manifest_path', '')), {})
        files = manifest.get('files', [])
        book = books_by_id.get(entry.get('id', ''), {})

        left, right = st.columns([1, 2], gap='large')
        with left:
            cover = book.get('cover_path')
            if cover and Path(cover).exists():
                st.image(cover, use_container_width=True)
            else:
                st.markdown(
                    f"<div style='background:#2f3b35;color:#f6f1e8;padding:24px;min-height:260px;border-radius:12px;display:flex;align-items:end;font-size:28px;font-weight:800;line-height:1.25;'>{escape(entry.get('title', ''))}</div>",
                    unsafe_allow_html=True,
                )
        with right:
            st.markdown(f"### {entry.get('title', '')}")
            st.caption(f"{entry.get('category', '其他')} · {entry.get('voice', 'default')} · {entry.get('generated_at', '')}")
            c1, c2, c3 = st.columns(3)
            c1.metric('段數', entry.get('chunk_count', 0))
            c2.metric('時長', format_time(entry.get('total_seconds_estimate', 0)))
            c3.metric('來源頁/章', entry.get('source_pages', 0))

        if files:
            if 'standalone_audio_idx' not in st.session_state:
                st.session_state['standalone_audio_idx'] = 1
            max_idx = len(files)
            idx = min(max(1, int(st.session_state.get('standalone_audio_idx', 1))), max_idx)
            n1, n2, n3, n4 = st.columns([1, 1, 2, 1])
            with n1:
                if st.button('上一段', disabled=idx <= 1, use_container_width=True):
                    st.session_state['standalone_audio_idx'] = idx - 1
                    st.rerun()
            with n2:
                if st.button('下一段', disabled=idx >= max_idx, use_container_width=True):
                    st.session_state['standalone_audio_idx'] = idx + 1
                    st.rerun()
            with n3:
                idx = st.number_input('段落', min_value=1, max_value=max_idx, value=idx, step=1)
                st.session_state['standalone_audio_idx'] = idx
            with n4:
                st.caption(f'{idx} / {max_idx}')

            chosen = files[idx - 1]
            audio_path = Path(chosen.get('audio_file', ''))
            text_path = Path(chosen.get('text_file', ''))
            st.markdown(f"**{audio_label(chosen)}**")
            if audio_path.exists():
                data = audio_path.read_bytes()
                st.audio(data, format='audio/mp4')
                st.download_button('下載這段音檔', data=data, file_name=audio_path.name, mime='audio/mp4', use_container_width=True)
            else:
                st.warning('這段音檔不存在，可能還在生成中。')

            if text_path.exists():
                with st.expander('這段文字'):
                    st.markdown(
                        f"<div style='background:#faf7f2;border:1px solid #e8dfd1;border-radius:12px;padding:16px;line-height:1.9;'>{escape(text_path.read_text(encoding='utf-8')[:7000]).replace(chr(10), '<br>')}</div>",
                        unsafe_allow_html=True,
                    )

with generate_tab:
    generated_ids = {x.get('id') for x in audio_rows}
    local_books = [b for b in books if b.get('exists') and b.get('local_path')]
    mode = st.radio('選書', ['尚未生成', '全部本機書'], horizontal=True)
    candidates = [b for b in local_books if b.get('id') not in generated_ids] if mode == '尚未生成' else local_books
    if candidates:
        title = st.selectbox('選一本生成', [b.get('title', '') for b in candidates])
        book = next(b for b in candidates if b.get('title') == title)
        st.caption(f"{book.get('category', '其他')} · {(book.get('format') or '').upper()} · {book.get('page_count') or '—'} 頁/章")
        g1, g2, g3 = st.columns(3)
        with g1:
            if st.button('先測 1 段', use_container_width=True):
                ok, out, err = run_audio(book.get('id', ''), limit_chunks=1, force=True)
                st.success('完成') if ok else st.error('失敗')
                st.code(out or err)
        with g2:
            if st.button('生成整本', type='primary', use_container_width=True):
                ok, out, err = run_audio(book.get('id', ''), force=True)
                st.success('完成') if ok else st.error('失敗')
                st.code(out or err)
        with g3:
            if st.button('背景跑 5 本', use_container_width=True):
                pid = start_batch(5)
                st.success(f'背景批次已啟動：PID {pid}')
    else:
        st.success('目前沒有尚未生成的本機書。')

with cloud_tab:
    st.markdown('**Google Drive 目標資料夾**')
    st.code(str(CLOUD_AUDIO_DIR))
    st.metric('Drive 已有音檔', cloud_count)
    if audio_rows:
        labels = [x.get('title', '') for x in audio_rows]
        title = st.selectbox('選一本同步', labels, key='cloud_one')
        entry = next(x for x in audio_rows if x.get('title', '') == title)
        c1, c2 = st.columns(2)
        with c1:
            if st.button('同步這一本', use_container_width=True):
                try:
                    dest = sync_audio_to_cloud(entry)
                    st.success(f'已同步到：{dest}')
                except Exception as exc:
                    st.error(str(exc))
        with c2:
            if st.button('同步全部', use_container_width=True):
                ok = 0
                errors = []
                for item in audio_rows:
                    try:
                        sync_audio_to_cloud(item)
                        ok += 1
                    except Exception as exc:
                        errors.append(f"{item.get('title', '')}: {exc}")
                st.success(f'已同步 {ok} 本')
                if errors:
                    st.warning('\n'.join(errors[:5]))
