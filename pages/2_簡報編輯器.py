import subprocess
import time
import streamlit as st

st.set_page_config(page_title="簡報編輯器", layout="wide")

SLIDE_EDITOR_PATH = "/Users/jimlin/Downloads/slide-editor"
PORT = 8765

st.title("AI 簡報編輯器")
st.markdown("用 Claude Design 產出 HTML 簡報後，在這裡直接點擊修改，**省 90% Token**。")
st.markdown("---")

if "editor_process" not in st.session_state:
    st.session_state.editor_process = None

is_running = (
    st.session_state.editor_process is not None
    and st.session_state.editor_process.poll() is None
)

col1, col2 = st.columns([1, 1])

with col1:
    if st.button("▶️ 啟動編輯器", type="primary", disabled=is_running):
        process = subprocess.Popen(
            ["python3", "main.py"],
            cwd=SLIDE_EDITOR_PATH,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        st.session_state.editor_process = process
        time.sleep(1.5)
        st.rerun()

with col2:
    if st.button("⏹ 停止", disabled=not is_running):
        st.session_state.editor_process.terminate()
        st.session_state.editor_process = None
        st.rerun()

if is_running:
    st.success(f"編輯器執行中 → http://localhost:{PORT}")
    st.components.v1.iframe(f"http://localhost:{PORT}", height=700, scrolling=True)
else:
    st.info("點擊「▶️ 啟動編輯器」開始使用。\n\n**使用流程：**\n1. 先用 Claude Design (claude.ai/design) 建立 HTML 簡報\n2. 下載 HTML 檔案\n3. 啟動編輯器，拖入 HTML 檔案即可點擊修改")
