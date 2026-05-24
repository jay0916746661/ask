import json
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Jim's AI 中控台", page_icon="📚", layout="wide")

BASE = Path(__file__).resolve().parent
AUDIO_INDEX = BASE / 'audio_books' / 'audio_index.json'
BATCH_STATUS = BASE / 'audio_books' / 'batch_status.json'
CLOUD_AUDIO_DIR = Path.home() / 'Library' / 'CloudStorage' / 'GoogleDrive-jay0916746661@gmail.com' / '我的雲端硬碟' / 'Jim有聲書'


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def format_time(seconds: int) -> str:
    seconds = int(seconds or 0)
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f'{minutes} 分 {sec} 秒' if sec else f'{minutes} 分'
    hours, minutes = divmod(minutes, 60)
    return f'{hours}h {minutes}m' if minutes else f'{hours}h'


audio_rows = load_json(AUDIO_INDEX, [])
batch = load_json(BATCH_STATUS, {})
cloud_m4a_count = len(list(CLOUD_AUDIO_DIR.rglob('*.m4a'))) if CLOUD_AUDIO_DIR.exists() else 0

st.title("Jim's AI 中控台")
st.caption('書庫、聽書、AI 學習與內容工作流的主控面板。')

hero1, hero2 = st.columns([1.3, 1], gap='large')
with hero1:
    st.markdown(
        """
        ### 目前可用模組
        - `書庫中心`：書庫同步、書封牆、單本閱讀、每週閱讀報告
        - `有聲書中心`：整本語音播放、分段收聽、Google Drive 同步
        - `AI學習中心`：整理你的 AI 使用流程與學習筆記
        - `CO-STAR提問框架`：提問模板與思考輔助
        """
    )
    if batch.get('state') == 'running':
        st.info(f"有聲書背景批次：{batch.get('current_index', '?')} / {batch.get('total', '?')} · {batch.get('title', '')}")
    elif batch.get('state') == 'done':
        st.success(f"有聲書批次已完成 · {batch.get('updated_at', '')}")
    else:
        st.info('左側邊欄可以切換頁面。現在最完整、最推薦你直接進去用的是 `書庫中心` 和 `有聲書中心`。')

with hero2:
    st.markdown(
        """
        <div style="background:#faf7f2;border:1px solid #eadfcd;border-radius:16px;padding:20px 22px;">
            <div style="font-size:12px;letter-spacing:0.14em;color:#6f6254;margin-bottom:10px;">NOW PLAYING WORKFLOW</div>
            <div style="font-size:28px;font-weight:800;line-height:1.3;color:#1f1b18;margin-bottom:10px;">書庫已可轉成有聲書</div>
            <div style="font-size:15px;line-height:1.9;color:#4e463d;">
                已生成的整本語音可以在面板播放，也能同步到 Google Drive，手機端直接聽。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

m1, m2, m3, m4 = st.columns(4)
m1.metric('已生成有聲書', len(audio_rows))
m2.metric('音檔段數', sum(int(x.get('chunk_count') or 0) for x in audio_rows))
m3.metric('估計可聽時間', format_time(sum(int(x.get('total_seconds_estimate') or 0) for x in audio_rows)))
m4.metric('Drive 音檔', cloud_m4a_count)

if audio_rows:
    latest = sorted(audio_rows, key=lambda x: x.get('generated_at', ''), reverse=True)[0]
    st.markdown(f"**最新有聲書**：{latest.get('title', '')} · {latest.get('chunk_count', 0)} 段 · {format_time(latest.get('total_seconds_estimate', 0))}")

st.divider()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.page_link('pages/5_書庫中心.py', label='打開 書庫中心', icon='📚')
with col2:
    st.page_link('pages/6_有聲書中心.py', label='打開 有聲書中心', icon='🎧')
with col3:
    st.page_link('pages/4_AI學習中心.py', label='打開 AI學習中心', icon='🧠')
with col4:
    st.page_link('pages/3_CO-STAR提問框架.py', label='打開 CO-STAR提問框架', icon='🧩')

st.divider()
st.subheader('雲端聽書資料夾')
st.code(str(CLOUD_AUDIO_DIR))
st.caption('Google Drive 會自行同步這個資料夾。面板裡也可以按「同步全部已生成到 Google Drive」。')
