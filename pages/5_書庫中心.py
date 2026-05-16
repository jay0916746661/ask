import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title='書庫中心', layout='wide')

BASE = Path(os.path.dirname(os.path.dirname(__file__)))
LIBRARY_FILE = BASE / 'book_library.json'
META_FILE = BASE / 'book_sync_meta.json'
READING_FILE = BASE / 'book_reading_state.json'
SYNC_SCRIPT = BASE / 'book_sync.py'
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


def load_library():
    return load_json(LIBRARY_FILE, [])


def load_meta():
    return load_json(META_FILE, {})


def load_reading():
    data = load_json(READING_FILE, {'logs': []})
    data.setdefault('logs', [])
    return data


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


def render_cover(book: dict):
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


def pick_featured_book(books: list[dict]) -> dict | None:
    if not books:
        return None
    sorted_books = sorted(
        books,
        key=lambda b: (
            b.get('exists', False),
            bool(b.get('preview')),
            b.get('mtime', 0),
            b.get('added_date', ''),
        ),
        reverse=True,
    )
    return sorted_books[0]


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
reading = load_reading()
logs = reading['logs']
week = weekly_logs(logs)

c1, c2, c3, c4 = st.columns(4)
c1.metric('總書數', len(books))
c2.metric('本機有檔案', sum(1 for b in books if b.get('exists')))
c3.metric('Drive 書單', sum(1 for b in books if 'Drive' in (b.get('source') or '')))
c4.metric('最近 7 天新書', len(recent_books(books)))

st.caption(f"上次同步：{meta.get('updated_at', '尚未同步')} · 本機 {meta.get('local_count', 0)} 本 · Drive {meta.get('drive_count', 0)} 本 · 合併 {meta.get('merged_count', 0)} 本")

summary_tab, sync_tab, reading_tab = st.tabs(['📖 書庫總覽', '🔄 同步狀態', '📝 每週閱讀報告'])

with summary_tab:
    left, right = st.columns([1, 3])
    with left:
        q = st.text_input('搜尋書名')
        cats = ['全部'] + sorted({b.get('category', '其他') for b in books})
        cat = st.selectbox('分類', cats)
        sources = ['全部', '本機', 'Google Drive', '本機 + Google Drive']
        source = st.selectbox('來源', sources)
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
    rows = []
    for b in filtered:
        rows.append({
            '書名': b.get('title',''),
            '作者': b.get('author',''),
            '分類': b.get('category',''),
            '來源': b.get('source',''),
            '格式': b.get('format',''),
            '頁數/章數': b.get('page_count','') or '',
            '大小(MB)': b.get('size_mb',''),
            '新增日期': b.get('added_date',''),
            '本機狀態': '有' if b.get('exists') else '缺',
        })
    featured = pick_featured_book(filtered)
    preview_col, detail_col = st.columns([1.05, 1.95], gap='large')
    with preview_col:
        st.subheader('本期推薦')
        if featured:
            render_cover(featured)
        else:
            st.info('目前沒有符合條件的書。')
    with detail_col:
        st.subheader('書庫明細')
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=380)
        if filtered:
            selected_title = st.selectbox('選一本查看詳情', [b.get('title','') for b in filtered], key='selected_book')
            selected = next((b for b in filtered if b.get('title') == selected_title), filtered[0])
            info1, info2 = st.columns([1.2, 1])
            with info1:
                st.markdown(f"### {selected.get('title','')}")
                st.caption(f"{selected.get('author') or '作者未解析'} · {selected.get('category','其他')} · {selected.get('source','')}")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric('格式', (selected.get('format') or '—').upper())
                m2.metric('頁數/章數', selected.get('page_count') or '—')
                m3.metric('大小(MB)', selected.get('size_mb') or '—')
                m4.metric('本機', '有' if selected.get('exists') else '缺')
                if selected.get('local_path'):
                    st.code(selected.get('local_path'))
                if selected.get('preview'):
                    st.markdown('**內文預覽**')
                    st.markdown(
                        f"<div style='background:#faf7f2;border:1px solid #e8dfd1;border-radius:12px;padding:16px;line-height:1.9;'>"
                        f"{selected.get('preview','').replace(chr(10), '<br>')}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.info('這本書目前還沒有抽到可讀預覽。若是 Drive 書單或掃描型 PDF，這是預期行為。')
            with info2:
                st.markdown('**書籍資訊**')
                st.markdown(f"- 新增日期：`{selected.get('added_date','')}`")
                st.markdown(f"- 來源：`{selected.get('source','')}`")
                st.markdown(f"- 分類：`{selected.get('category','其他')}`")
                st.markdown(f"- 資料夾：`{selected.get('folder','')}`")
                if not selected.get('exists'):
                    st.warning('這本書目前只在 Drive 書單中，尚未出現在本機電子書資料夾。')
    st.divider()
    st.subheader('最近新增')
    latest = recent_books(books, days=14)[:12]
    if latest:
        cols = st.columns(3)
        for idx, b in enumerate(latest):
            with cols[idx % 3]:
                bg, fg = category_style(b.get('category'))
                st.markdown(
                    f"""
                    <div style="background:{fg}; border:1px solid #eadfcd; border-radius:12px; padding:14px 14px 12px; min-height:150px; margin-bottom:12px;">
                        <div style="font-size:11px; letter-spacing:0.14em; color:#6f6254;">NEW ARRIVAL · {b.get('added_date','')}</div>
                        <div style="font-size:18px; font-weight:700; line-height:1.35; margin:10px 0 8px; color:#1f1b18;">{b.get('title','')[:80]}</div>
                        <div style="font-size:12px; color:#665b50;">{b.get('category','其他')} · {b.get('source','')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
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
            st.markdown(f"- {b.get('title','')} · {b.get('source','')} · {b.get('category','其他')}")

with reading_tab:
    st.subheader('新增閱讀記錄')
    titles = [b.get('title','') for b in books]
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
                    'category': book.get('category','其他') if book else '其他',
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
        by_book = df.groupby('title', as_index=False).agg({'pages':'sum','minutes':'sum'}).sort_values(['minutes','pages'], ascending=False)
        st.markdown('**本週書籍排行**')
        st.dataframe(by_book, use_container_width=True, hide_index=True)
        notes = [f"- `{x['date']}` {x['title']} · {x['minutes']} 分 / {x['pages']} 頁 · {x['note']}" for x in reversed(week[-20:]) if x.get('note')]
        if notes:
            st.markdown('**本週筆記**')
            for line in notes:
                st.markdown(line)
    else:
        st.info('本週還沒有閱讀記錄。')
