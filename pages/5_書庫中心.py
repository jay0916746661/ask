import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
import streamlit as st

st.set_page_config(page_title='書庫中心', layout='wide')

BASE = Path(os.path.dirname(os.path.dirname(__file__)))
LIBRARY_FILE = BASE / 'book_library.json'
META_FILE = BASE / 'book_sync_meta.json'
READING_FILE = BASE / 'book_reading_state.json'
SYNC_SCRIPT = BASE / 'book_sync.py'
AUDIO_SCRIPT = BASE / 'book_to_audio.py'
AUDIO_DIR = BASE / 'audio_books'
AUDIO_INDEX_FILE = AUDIO_DIR / 'audio_index.json'
WATCH_DIR = Path(os.environ.get('JIM_BOOK_WATCH_DIR', str(Path.home() / 'Desktop' / '電子書'))).expanduser()


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def run_sync():
    result = subprocess.run([sys.executable, str(SYNC_SCRIPT)], cwd=BASE, text=True, capture_output=True)
    return result.returncode == 0, result.stdout, result.stderr


def run_audio(book: dict, limit_chunks: int | None = None, force: bool = False):
    cmd = [sys.executable, str(AUDIO_SCRIPT), '--book-id', book.get('id', '')]
    if limit_chunks:
        cmd += ['--limit-chunks', str(limit_chunks)]
    if force:
        cmd += ['--force']
    result = subprocess.run(cmd, cwd=BASE, text=True, capture_output=True)
    return result.returncode == 0, result.stdout, result.stderr


def load_library():
    return load_json(LIBRARY_FILE, [])


def load_meta():
    return load_json(META_FILE, {})


def load_reading():
    data = load_json(READING_FILE, {'logs': [], 'resume': {}})
    data.setdefault('logs', [])
    data.setdefault('resume', {})
    return data


def load_audio_index():
    rows = load_json(AUDIO_INDEX_FILE, [])
    return rows if isinstance(rows, list) else []


def audio_map():
    return {row.get('id', ''): row for row in load_audio_index() if row.get('id')}


def format_audio_time(seconds: int) -> str:
    seconds = int(seconds or 0)
    if seconds < 60:
        return f'{seconds} 秒'
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f'{minutes} 分 {sec} 秒' if sec else f'{minutes} 分'
    hours, minutes = divmod(minutes, 60)
    return f'{hours}h {minutes}m' if minutes else f'{hours}h'


def find_audio_entry(book: dict, audio_entries: dict):
    return audio_entries.get(book.get('id', ''))


def save_reading(data):
    save_json(READING_FILE, data)


def recent_books(books, days=7):
    cutoff = datetime.now() - timedelta(days=days)
    out = []
    for b in books:
        try:
            dt = datetime.strptime(b.get('added_date', ''), '%Y-%m-%d')
        except Exception:
            continue
        if dt >= cutoff:
            out.append(b)
    return out


def weekly_logs(logs):
    cutoff = datetime.now() - timedelta(days=7)
    out = []
    for log in logs:
        try:
            dt = datetime.strptime(log['date'], '%Y-%m-%d')
        except Exception:
            continue
        if dt >= cutoff:
            out.append(log)
    return out


def category_style(category: str) -> tuple[str, str]:
    palette = {
        '投資/財富': ('#21493d', '#f4efe4'),
        'AI/科技': ('#21354a', '#eef3f7'),
        '人性/心理': ('#6d3b3b', '#f8efea'),
        '生活/心智': ('#5c4b32', '#f5f0e6'),
        '溝通/談判': ('#4c3e63', '#f1ecf8'),
        '商業/創業': ('#7a4c20', '#f7eee4'),
        '其他': ('#3a3a3a', '#f2efe8'),
    }
    return palette.get(category or '其他', palette['其他'])


def render_fallback_cover(book: dict):
    bg, fg = category_style(book.get('category'))
    title = book.get('title', '未命名書籍')
    author = book.get('author') or book.get('category') or '書庫'
    st.markdown(
        f"""
        <div style="background:{bg}; color:{fg}; border-radius:14px; padding:24px 18px; min-height:320px;
                    display:flex; flex-direction:column; justify-content:space-between; box-shadow:0 8px 24px rgba(0,0,0,0.08);">
            <div style="font-size:12px; letter-spacing:0.18em; opacity:0.85;">JIM LIBRARY</div>
            <div style="font-size:30px; font-weight:800; line-height:1.22;">{title[:90]}</div>
            <div>
                <div style="font-size:14px; opacity:0.92;">{author[:60]}</div>
                <div style="font-size:12px; opacity:0.75; margin-top:6px;">{book.get('format','').upper()} · {book.get('source','')}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_cover(book: dict, key: str):
    cover_path = book.get('cover_path') or ''
    if cover_path and Path(cover_path).exists():
        st.image(cover_path, use_container_width=True)
    else:
        render_fallback_cover(book)


def pick_featured_book(books: list[dict]) -> dict | None:
    if not books:
        return None
    sorted_books = sorted(
        books,
        key=lambda b: (
            b.get('exists', False),
            bool(b.get('cover_path')),
            bool(b.get('preview')),
            b.get('mtime', 0),
            b.get('added_date', ''),
        ),
        reverse=True,
    )
    return sorted_books[0]


def book_logs(logs, title: str):
    return [x for x in logs if x.get('title') == title]


def format_minutes(total: int) -> str:
    if total < 60:
        return f'{total} 分'
    h = total // 60
    m = total % 60
    return f'{h}h {m}m' if m else f'{h}h'


def preview_paragraphs(text: str):
    if not text:
        return []
    blocks = [b.strip() for b in text.replace('\r', '\n').split('\n\n') if b.strip()]
    if blocks:
        return blocks[:18]
    text = text.replace('\n', ' ')
    chunks = []
    while text:
        chunks.append(text[:180].strip())
        text = text[180:]
    return [c for c in chunks if c]


def progress_map(logs):
    progress = {}
    for row in logs:
        title = row.get('title', '')
        if not title:
            continue
        item = progress.setdefault(title, {'pages': 0, 'minutes': 0, 'last_date': '', 'notes': []})
        item['pages'] += int(row.get('pages', 0) or 0)
        item['minutes'] += int(row.get('minutes', 0) or 0)
        item['last_date'] = max(item['last_date'], row.get('date', ''))
        note = (row.get('note') or '').strip()
        if note:
            item['notes'].append(note)
    return progress


def build_quote_options(book: dict):
    paragraphs = preview_paragraphs(book.get('preview', ''))
    out = []
    for para in paragraphs[:12]:
        txt = para.strip()
        if len(txt) >= 28:
            out.append(txt[:150])
    return out[:8]


def build_story_svg(book: dict, text: str) -> str:
    bg, fg = category_style(book.get('category'))
    clean_text = escape((text or '').strip())
    title = escape((book.get('title') or '')[:28])
    meta = escape(book.get('author') or book.get('category') or 'Jim Library')
    wrapped = []
    line = ''
    for ch in clean_text:
        line += ch
        if len(line) >= 14:
            wrapped.append(line)
            line = ''
        if len(wrapped) >= 8:
            break
    if line and len(wrapped) < 8:
        wrapped.append(line)
    tspans = ''.join([f"<tspan x='60' dy='44'>{x}</tspan>" for x in wrapped])
    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='1080' height='1920' viewBox='0 0 1080 1920'>
  <rect width='1080' height='1920' fill='{bg}'/>
  <rect x='60' y='60' width='960' height='1800' rx='34' fill='rgba(255,255,255,0.08)' stroke='rgba(255,255,255,0.22)'/>
  <text x='60' y='150' fill='{fg}' font-size='28' font-family='Arial, sans-serif' letter-spacing='8'>JIM LIBRARY</text>
  <text x='60' y='290' fill='{fg}' font-size='76' font-weight='700' font-family='Arial, sans-serif'>閱讀摘句</text>
  <text x='60' y='470' fill='{fg}' font-size='54' font-family='Arial, sans-serif'>{tspans}</text>
  <text x='60' y='1680' fill='{fg}' font-size='40' font-weight='700' font-family='Arial, sans-serif'>{title}</text>
  <text x='60' y='1740' fill='{fg}' font-size='28' font-family='Arial, sans-serif' opacity='0.85'>{meta}</text>
  <text x='60' y='1820' fill='{fg}' font-size='24' font-family='Arial, sans-serif' opacity='0.7'>jim reading center</text>
</svg>"""


st.title('📚 書庫中心')
st.caption('同步本機電子書資料夾、Google Drive 書單，並整理閱讀進度與每週報告')

with st.sidebar:
    st.subheader('同步控制')
    st.write(f'監看資料夾：`{WATCH_DIR}`')
    if st.button('立即同步書庫', type='primary', use_container_width=True):
        ok, out, err = run_sync()
        if ok:
            st.success('同步完成')
            if out.strip():
                st.code(out)
            st.rerun()
        else:
            st.error('同步失敗')
            st.code((out or '') + '\n' + (err or ''))

books = load_library()
meta = load_meta()
audio_entries = audio_map()
reading = load_reading()
logs = reading['logs']
resume = reading['resume']
week = weekly_logs(logs)
progress = progress_map(logs)

c1, c2, c3, c4 = st.columns(4)
c1.metric('總書數', len(books))
c2.metric('本機有檔案', sum(1 for b in books if b.get('exists')))
c3.metric('Drive 書單', sum(1 for b in books if 'Drive' in (b.get('source') or '')))
c4.metric('最近 7 天新書', len(recent_books(books)))

st.caption(
    f"上次同步：{meta.get('updated_at', '尚未同步')} · 本機 {meta.get('local_count', 0)} 本 · "
    f"Drive {meta.get('drive_count', 0)} 本 · 合併 {meta.get('merged_count', 0)} 本 · "
    f"封面 {meta.get('cover_count', 0)} 本 · 預覽 {meta.get('preview_count', 0)} 本"
)

summary_tab, sync_tab, reading_tab, reader_tab, audio_tab = st.tabs(['📖 書庫總覽', '🔄 同步狀態', '📝 每週閱讀報告', '📘 單本閱讀', '🎧 整本語音'])

with summary_tab:
    left, right = st.columns([1, 3])
    with left:
        q = st.text_input('搜尋書名')
        cats = ['全部'] + sorted({b.get('category', '其他') for b in books})
        cat = st.selectbox('分類', cats)
        sources = ['全部', '本機', 'Google Drive', '本機 + Google Drive']
        source = st.selectbox('來源', sources)
        sort_mode = st.selectbox('排序', ['最新加入', '閱讀最多', '頁數最多', '書名 A-Z'])
        show_missing = st.checkbox('只看 Drive 有但本機沒有', value=False)
    filtered = books
    if q.strip():
        filtered = [b for b in filtered if q.strip().lower() in b.get('title', '').lower()]
    if cat != '全部':
        filtered = [b for b in filtered if b.get('category') == cat]
    if source != '全部':
        filtered = [b for b in filtered if b.get('source') == source]
    if show_missing:
        filtered = [b for b in filtered if not b.get('exists')]
    if sort_mode == '最新加入':
        filtered = sorted(filtered, key=lambda b: (b.get('added_date', ''), b.get('mtime', 0)), reverse=True)
    elif sort_mode == '閱讀最多':
        filtered = sorted(
            filtered,
            key=lambda b: (
                progress.get(b.get('title', ''), {}).get('minutes', 0),
                progress.get(b.get('title', ''), {}).get('pages', 0),
                b.get('added_date', ''),
            ),
            reverse=True,
        )
    elif sort_mode == '頁數最多':
        filtered = sorted(filtered, key=lambda b: int(b.get('page_count') or 0), reverse=True)
    else:
        filtered = sorted(filtered, key=lambda b: b.get('title', '').lower())

    rows = []
    for b in filtered:
        book_progress = progress.get(b.get('title', ''), {})
        total_pages = int(b.get('page_count') or 0)
        done_pages = int(book_progress.get('pages', 0))
        pct = min(100, int((done_pages / total_pages) * 100)) if total_pages else 0
        rows.append({
            '書名': b.get('title', ''),
            '作者': b.get('author', ''),
            '分類': b.get('category', ''),
            '來源': b.get('source', ''),
            '格式': b.get('format', ''),
            '頁數/章數': b.get('page_count', '') or '',
            '進度': f'{pct}%',
            '大小(MB)': b.get('size_mb', ''),
            '新增日期': b.get('added_date', ''),
            '本機狀態': '有' if b.get('exists') else '缺',
        })

    selected_key = 'library_selected_book'
    selected_titles = [b.get('title', '') for b in filtered]
    if filtered and st.session_state.get(selected_key) not in selected_titles:
        st.session_state[selected_key] = filtered[0].get('title', '')

    featured = pick_featured_book(filtered)
    preview_col, detail_col = st.columns([1.05, 1.95], gap='large')
    with preview_col:
        st.subheader('本期推薦')
        if featured:
            render_cover(featured, 'featured_cover')
            ft_progress = progress.get(featured.get('title', ''), {})
            ft_pages = int(ft_progress.get('pages', 0))
            ft_total = int(featured.get('page_count') or 0)
            ft_pct = min(100, int((ft_pages / ft_total) * 100)) if ft_total else 0
            st.caption(f"{featured.get('author') or '作者未解析'} · {featured.get('category', '其他')}")
            st.progress(ft_pct / 100 if ft_pct else 0, text=f'進度 {ft_pct}% · {ft_pages} / {ft_total or "?"} 頁')
        else:
            st.info('目前沒有符合條件的書。')

    with detail_col:
        st.subheader('書庫瀏覽')
        view_mode = st.radio('瀏覽模式', ['明細列表', '書架視圖'], horizontal=True, label_visibility='collapsed')

        if view_mode == '明細列表':
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=380)
            if filtered:
                st.selectbox('選一本查看詳情', selected_titles, key=selected_key)
        else:
            st.caption('像書店一樣直接看封面，點選某一本到下方看詳情。')
            shelf_cols = st.columns(4)
            for idx, b in enumerate(filtered[:24]):
                with shelf_cols[idx % 4]:
                    render_cover(b, f'shelf_cover_{idx}')
                    bp = progress.get(b.get('title', ''), {})
                    done_pages = int(bp.get('pages', 0))
                    total_pages = int(b.get('page_count') or 0)
                    pct = min(100, int((done_pages / total_pages) * 100)) if total_pages else 0
                    st.markdown(f"**{b.get('title', '')[:28]}**")
                    st.caption(f"{b.get('category', '其他')} · {(b.get('format') or '—').upper()}")
                    st.progress(pct / 100 if pct else 0, text=f'{pct}%')
                    btn1, btn2 = st.columns(2)
                    with btn1:
                        if st.button('查看詳情', key=f'shelf_pick_{idx}', use_container_width=True):
                            st.session_state[selected_key] = b.get('title', '')
                            st.rerun()
                    with btn2:
                        if st.button('直接閱讀', key=f'shelf_read_{idx}', use_container_width=True):
                            st.session_state[selected_key] = b.get('title', '')
                            st.session_state['reader_book'] = b.get('title', '')
                            st.success('已幫你選好這本書，切到「📘 單本閱讀」就能直接看。')
            if len(filtered) > 24:
                st.caption(f'目前先顯示前 24 本，已篩選到 {len(filtered)} 本。可以縮小篩選條件更快找到書。')

        if filtered:
            selected_title = st.session_state.get(selected_key, filtered[0].get('title', ''))
            selected = next((b for b in filtered if b.get('title') == selected_title), filtered[0])
            st.divider()
            info1, info2 = st.columns([1.2, 1])
            with info1:
                st.markdown(f"### {selected.get('title', '')}")
                st.caption(f"{selected.get('author') or '作者未解析'} · {selected.get('category', '其他')} · {selected.get('source', '')}")
                book_progress = progress.get(selected.get('title', ''), {})
                current_pages = int(book_progress.get('pages', 0))
                total_pages = int(selected.get('page_count') or 0)
                progress_pct = min(100, int((current_pages / total_pages) * 100)) if total_pages else 0
                m1, m2, m3, m4 = st.columns(4)
                m1.metric('格式', (selected.get('format') or '—').upper())
                m2.metric('頁數/章數', selected.get('page_count') or '—')
                m3.metric('大小(MB)', selected.get('size_mb') or '—')
                m4.metric('進度', f'{progress_pct}%')
                st.progress(progress_pct / 100 if progress_pct else 0, text=f'已讀 {current_pages} / {total_pages or "?"} 頁')
                action_col1, action_col2 = st.columns([1, 1])
                with action_col1:
                    if st.button('帶到單本閱讀', key='jump_to_reader', use_container_width=True):
                        st.session_state['reader_book'] = selected.get('title', '')
                        st.success('已幫你選好這本書，切到「單本閱讀」分頁就能直接看。')
                with action_col2:
                    if selected.get('exists'):
                        st.caption('可在下方 `📘 單本閱讀` 直接續讀')
                if selected.get('local_path'):
                    st.code(selected.get('local_path'))
                if selected.get('preview'):
                    st.markdown('**內文預覽**')
                    st.markdown(
                        f"<div style='background:#faf7f2;border:1px solid #e8dfd1;border-radius:12px;padding:16px;line-height:1.9;'>"
                        f"{selected.get('preview', '').replace(chr(10), '<br>')}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.info('這本書目前還沒有抽到可讀預覽。若是 Drive 書單或掃描型 PDF，這是預期行為。')
            with info2:
                st.markdown('**書籍資訊**')
                st.markdown(f"- 新增日期：`{selected.get('added_date', '')}`")
                st.markdown(f"- 來源：`{selected.get('source', '')}`")
                st.markdown(f"- 分類：`{selected.get('category', '其他')}`")
                st.markdown(f"- 資料夾：`{selected.get('folder', '')}`")
                if not selected.get('exists'):
                    st.warning('這本書目前只在 Drive 書單中，尚未出現在本機電子書資料夾。')

    st.divider()
    st.subheader('最近新增')
    latest = recent_books(books, days=14)[:12]
    if latest:
        cols = st.columns(4)
        for idx, b in enumerate(latest):
            with cols[idx % 4]:
                render_cover(b, f'latest_cover_{idx}')
                st.caption(f"NEW · {b.get('added_date', '')}")
                st.markdown(f"**{b.get('title', '')[:30]}**")
                st.caption(f"{b.get('category', '其他')} · {b.get('source', '')}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button('詳情', key=f'latest_pick_{idx}', use_container_width=True):
                        st.session_state[selected_key] = b.get('title', '')
                        st.rerun()
                with c2:
                    if st.button('閱讀', key=f'latest_read_{idx}', use_container_width=True):
                        st.session_state[selected_key] = b.get('title', '')
                        st.session_state['reader_book'] = b.get('title', '')
                        st.success('已幫你選好這本書，切到「📘 單本閱讀」就能直接看。')
    else:
        st.info('最近 14 天沒有新增資料。')

with sync_tab:
    st.subheader('同步狀態檢查')
    st.write(f'- 監看資料夾存在：**{"是" if WATCH_DIR.exists() else "否"}**')
    st.write(f'- 同步腳本存在：**{"是" if SYNC_SCRIPT.exists() else "否"}**')
    st.write(f'- 書庫資料檔存在：**{"是" if LIBRARY_FILE.exists() else "否"}**')
    st.write(f'- 待補抓的書（Drive 有但本機沒有）：**{sum(1 for b in books if not b.get("exists"))} 本**')
    missing = [b for b in books if not b.get('exists')][:30]
    if missing:
        st.markdown('**缺漏樣本**')
        for b in missing:
            st.markdown(f"- {b.get('title', '')} · {b.get('source', '')} · {b.get('category', '其他')}")

with reading_tab:
    st.subheader('新增閱讀記錄')
    titles = [b.get('title', '') for b in books]
    if titles:
        with st.form('reading_log', clear_on_submit=True):
            title = st.selectbox('書名', titles)
            c1, c2 = st.columns(2)
            with c1:
                pages = st.number_input('本次閱讀頁數', min_value=0, value=10, step=1)
            with c2:
                minutes = st.number_input('本次閱讀分鐘', min_value=0, value=20, step=5)
            note = st.text_area('筆記 / 重點')
            submitted = st.form_submit_button('儲存閱讀記錄')
            if submitted:
                book = next((b for b in books if b.get('title') == title), None)
                reading['logs'].append({
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'title': title,
                    'category': book.get('category', '其他') if book else '其他',
                    'pages': int(pages),
                    'minutes': int(minutes),
                    'note': note.strip(),
                })
                save_reading(reading)
                st.success('已儲存閱讀記錄')
                st.rerun()
    else:
        st.info('先同步書庫，才會有可選書單。')

    st.divider()
    st.subheader('本週閱讀報告')
    total_minutes = sum(int(x.get('minutes', 0)) for x in week)
    total_pages = sum(int(x.get('pages', 0)) for x in week)
    active_titles = len({x.get('title') for x in week})
    w1, w2, w3 = st.columns(3)
    w1.metric('本週閱讀時間', f'{total_minutes} 分')
    w2.metric('本週閱讀頁數', total_pages)
    w3.metric('本週閱讀書數', active_titles)
    if week:
        df = pd.DataFrame(week)
        by_book = df.groupby('title', as_index=False).agg({'pages': 'sum', 'minutes': 'sum'}).sort_values(['minutes', 'pages'], ascending=False)
        st.markdown('**本週書籍排行**')
        st.dataframe(by_book, use_container_width=True, hide_index=True)
        notes = [f"- `{x['date']}` {x['title']} · {x['minutes']} 分 / {x['pages']} 頁 · {x['note']}" for x in reversed(week[-20:]) if x.get('note')]
        if notes:
            st.markdown('**本週筆記**')
            for line in notes:
                st.markdown(line)
    else:
        st.info('本週還沒有閱讀記錄。')

with reader_tab:
    st.subheader('單本閱讀')
    readable_books = [b for b in books if b.get('exists') and (b.get('preview') or b.get('local_path'))]
    if not readable_books:
        st.info('目前還沒有可閱讀的本機書。先同步或把書放進電子書資料夾。')
    else:
        selected_title = st.selectbox('選擇要閱讀的書', [b.get('title', '') for b in readable_books], key='reader_book')
        selected = next((b for b in readable_books if b.get('title') == selected_title), readable_books[0])
        book_week_logs = book_logs(logs, selected.get('title', ''))
        total_minutes = sum(int(x.get('minutes', 0)) for x in book_week_logs)
        total_pages_read = sum(int(x.get('pages', 0)) for x in book_week_logs)
        total_book_pages = int(selected.get('page_count') or 0)
        progress_pct = min(100, int((total_pages_read / total_book_pages) * 100)) if total_book_pages else 0
        font_size = st.slider('字體大小', min_value=14, max_value=28, value=18)
        paragraphs = preview_paragraphs(selected.get('preview', ''))
        resume_page = int(resume.get(selected.get('id', ''), 0) or 0)

        top_left, top_right = st.columns([1, 2], gap='large')
        with top_left:
            render_cover(selected, 'reader_cover')
            if selected.get('local_path') and Path(selected['local_path']).exists():
                p = Path(selected['local_path'])
                if p.stat().st_size <= 25 * 1024 * 1024:
                    st.download_button('下載原檔', data=p.read_bytes(), file_name=p.name, use_container_width=True)
                else:
                    st.caption('檔案超過 25MB，保留本機路徑供直接開啟。')
                st.code(str(p))
        with top_right:
            st.markdown(f"### {selected.get('title', '')}")
            st.caption(f"{selected.get('author') or '作者未解析'} · {selected.get('category', '其他')} · {selected.get('format', '').upper()} · {selected.get('source', '')}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric('頁數/章數', selected.get('page_count') or '—')
            m2.metric('大小(MB)', selected.get('size_mb') or '—')
            m3.metric('累積閱讀頁數', total_pages_read)
            m4.metric('累積閱讀時間', format_minutes(total_minutes))
            st.progress(progress_pct / 100 if progress_pct else 0, text=f'閱讀進度 {progress_pct}% · 已讀 {total_pages_read} / {total_book_pages or "?"} 頁')

            if total_book_pages:
                new_resume = st.slider('續讀位置（頁）', min_value=0, max_value=max(total_book_pages, 1), value=min(resume_page, total_book_pages), key='resume_slider')
                if new_resume != resume_page:
                    reading['resume'][selected.get('id', '')] = new_resume
                    save_reading(reading)
                    st.caption(f'已記住這本書的續讀位置：第 {new_resume} 頁')
                elif new_resume:
                    st.caption(f'目前記住的續讀位置：第 {new_resume} 頁')

            st.markdown('**閱讀內容**')
            if paragraphs:
                body = ''.join([
                    f"<p style='font-size:{font_size}px; line-height:1.95; margin:0 0 16px 0; color:#1f1b18;'>{escape(p)}</p>"
                    for p in paragraphs
                ])
                st.markdown(
                    f"<div style='background:#fcfaf6;border:1px solid #e8dfd1;border-radius:14px;padding:22px 24px; max-height:760px; overflow:auto;'>{body}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info('這本書目前沒有可讀預覽。')

            st.divider()
            st.markdown('**快速記錄這本書**')
            with st.form('reader_log', clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    pages = st.number_input('本次閱讀頁數', min_value=0, value=8, step=1, key='reader_pages')
                with c2:
                    minutes = st.number_input('本次閱讀分鐘', min_value=0, value=15, step=5, key='reader_minutes')
                note = st.text_area('本次筆記 / 重點', key='reader_note')
                submitted = st.form_submit_button('儲存這本書的閱讀記錄')
                if submitted:
                    reading['logs'].append({
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'title': selected.get('title', ''),
                        'category': selected.get('category', '其他'),
                        'pages': int(pages),
                        'minutes': int(minutes),
                        'note': note.strip(),
                    })
                    if total_book_pages:
                        reading['resume'][selected.get('id', '')] = min(total_book_pages, total_pages_read + int(pages))
                    save_reading(reading)
                    st.success('已儲存閱讀記錄')
                    st.rerun()

            st.divider()
            st.markdown('**摘句卡片 / 限動卡片**')
            quote_options = build_quote_options(selected)
            if quote_options:
                chosen = st.selectbox('選擇一句做卡片', quote_options, key='quote_card_select')
                svg = build_story_svg(selected, chosen)
                st.markdown(
                    f"<div style='background:#faf7f2;border:1px solid #e8dfd1;border-radius:14px;padding:16px;'><div style='font-size:12px;color:#6f6254;margin-bottom:10px;'>卡片預覽文字</div><div style='font-size:22px;line-height:1.7;color:#1f1b18;'>「{escape(chosen)}」</div></div>",
                    unsafe_allow_html=True,
                )
                st.download_button('下載 SVG 卡片', data=svg.encode('utf-8'), file_name=f"story-card-{selected.get('title', 'book')[:20]}.svg", mime='image/svg+xml')
            else:
                st.info('這本書目前還沒有適合抽成卡片的句子。')

            if book_week_logs:
                st.markdown('**這本書最近的閱讀記錄**')
                for row in reversed(book_week_logs[-8:]):
                    st.markdown(f"- `{row['date']}` {row['minutes']} 分 / {row['pages']} 頁 · {row.get('note', '')}")

with audio_tab:
    st.subheader('整本語音書')
    local_books = [b for b in books if b.get('exists') and b.get('local_path')]
    if not local_books:
        st.info('目前沒有可轉成語音的本機書。先同步，或把電子書放進監看資料夾。')
    else:
        st.caption('使用 macOS 內建語音引擎把整本書切成多段 m4a。適合通勤、散步、睡前收聽。')
        selected_title = st.selectbox('選擇要轉成語音的書', [b.get('title', '') for b in local_books], key='audio_book')
        selected = next((b for b in local_books if b.get('title') == selected_title), local_books[0])
        entry = find_audio_entry(selected, audio_entries)

        top_left, top_right = st.columns([1, 2], gap='large')
        with top_left:
            render_cover(selected, 'audio_cover')
        with top_right:
            st.markdown(f"### {selected.get('title', '')}")
            st.caption(f"{selected.get('author') or '作者未解析'} · {selected.get('category', '其他')} · {(selected.get('format') or '').upper()}")
            if entry:
                m1, m2, m3 = st.columns(3)
                m1.metric('已轉段數', entry.get('chunk_count', 0))
                m2.metric('估計時長', format_audio_time(entry.get('total_seconds_estimate', 0)))
                m3.metric('生成時間', (entry.get('generated_at', '') or '—')[:16])
                st.success('這本書已有完整語音輸出。')
            else:
                st.info('這本書還沒生成語音。')

            btn1, btn2, btn3 = st.columns(3)
            with btn1:
                if st.button('先測 1 段', key='audio_test', use_container_width=True):
                    with st.spinner('正在生成測試音檔...'):
                        ok, out, err = run_audio(selected, limit_chunks=1, force=True)
                    if ok:
                        st.success('測試音檔已生成')
                        if out.strip():
                            st.code(out)
                        st.rerun()
                    else:
                        st.error('生成失敗')
                        st.code((out or '') + '\n' + (err or ''))
            with btn2:
                if st.button('生成整本語音', key='audio_full', type='primary', use_container_width=True):
                    with st.spinner('正在把整本書轉成語音，這可能需要幾分鐘...'):
                        ok, out, err = run_audio(selected, force=True)
                    if ok:
                        st.success('整本語音已生成')
                        if out.strip():
                            st.code(out)
                        st.rerun()
                    else:
                        st.error('生成失敗')
                        st.code((out or '') + '\n' + (err or ''))
            with btn3:
                if st.button('刷新語音索引', key='audio_refresh', use_container_width=True):
                    st.rerun()

            if entry:
                st.markdown('**音檔位置**')
                st.code(entry.get('audio_dir', ''))
                manifest_path = Path(entry.get('manifest_path', ''))
                if manifest_path.exists():
                    manifest = load_json(manifest_path, {})
                    files = manifest.get('files', [])
                    if files:
                        st.markdown('**播放預覽**')
                        pick = st.selectbox(
                            '選一段播放',
                            [f"第 {x.get('index', 0)} 段 · 約 {x.get('seconds_estimate', 0)} 秒" for x in files[:30]],
                            key='audio_chunk_pick',
                        )
                        idx = int(pick.split()[1]) if pick else 1
                        chosen = next((x for x in files if int(x.get('index', 0)) == idx), files[0])
                        audio_path = Path(chosen.get('audio_file', ''))
                        text_path = Path(chosen.get('text_file', ''))
                        if audio_path.exists():
                            st.audio(audio_path.read_bytes(), format='audio/mp4')
                        if text_path.exists():
                            st.markdown('**這段文字**')
                            st.markdown(
                                f"<div style='background:#faf7f2;border:1px solid #e8dfd1;border-radius:12px;padding:16px;line-height:1.9;'>"
                                f"{escape(text_path.read_text(encoding='utf-8')[:5000]).replace(chr(10), '<br>')}"
                                f"</div>",
                                unsafe_allow_html=True,
                            )
                        playlist_path = Path(entry.get('playlist', ''))
                        if playlist_path.exists():
                            st.download_button('下載播放清單 m3u', data=playlist_path.read_bytes(), file_name=playlist_path.name, use_container_width=True)

        st.divider()
        st.markdown('**已生成的有聲書**')
        audio_rows = list(audio_entries.values())
        if audio_rows:
            table = pd.DataFrame([
                {
                    '書名': x.get('title', ''),
                    '分類': x.get('category', ''),
                    '段數': x.get('chunk_count', 0),
                    '估計時長': format_audio_time(x.get('total_seconds_estimate', 0)),
                    '生成時間': x.get('generated_at', ''),
                }
                for x in sorted(audio_rows, key=lambda r: r.get('generated_at', ''), reverse=True)
            ])
            st.dataframe(table, use_container_width=True, hide_index=True)
        else:
            st.info('目前還沒有任何已生成的整本語音。')
