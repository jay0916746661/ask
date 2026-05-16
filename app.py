
import streamlit as st

st.set_page_config(page_title="Jim's AI 中控台", page_icon="📚", layout="wide")

st.title("Jim's AI 中控台")
st.caption("目前這個專案已經整理成以書庫中心為主的多頁 Streamlit 工具站。")

hero1, hero2 = st.columns([1.3, 1], gap="large")
with hero1:
    st.markdown(
        """
        ### 目前可用模組
        - `書庫中心`：書庫同步、書封牆、單本閱讀、每週閱讀報告
        - `AI學習中心`：整理你的 AI 使用流程與學習筆記
        - `簡報編輯器`：簡報與內容產出工作區
        - `CO-STAR提問框架`：提問模板與思考輔助
        """
    )
    st.info("左側邊欄可以切換頁面。現在最完整、最推薦你直接進去用的是 `書庫中心`。")

with hero2:
    st.markdown(
        """
        <div style="background:#faf7f2;border:1px solid #eadfcd;border-radius:16px;padding:20px 22px;">
            <div style="font-size:12px;letter-spacing:0.14em;color:#6f6254;margin-bottom:10px;">RECOMMENDED</div>
            <div style="font-size:28px;font-weight:800;line-height:1.3;color:#1f1b18;margin-bottom:10px;">先從書庫中心開始</div>
            <div style="font-size:15px;line-height:1.9;color:#4e463d;">
                這裡已經串好本機電子書、Google Drive 書單、閱讀進度、書封牆與單本閱讀。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

col1, col2, col3 = st.columns(3)
with col1:
    st.page_link("pages/5_書庫中心.py", label="打開 書庫中心", icon="📚")
with col2:
    st.page_link("pages/4_AI學習中心.py", label="打開 AI學習中心", icon="🧠")
with col3:
    st.page_link("pages/3_CO-STAR提問框架.py", label="打開 CO-STAR提問框架", icon="🧩")

st.divider()
st.subheader("上線說明")
st.markdown(
    """
    這個 repo 已經補上 `requirements.txt`，適合直接部署到 Streamlit Cloud。

    如果你要外網網址：
    1. 到 Streamlit Cloud 連接 GitHub repo `jay0916746661/ask`
    2. Main file path 選 `app.py`
    3. Deploy 後就會拿到固定網址
    """
)
