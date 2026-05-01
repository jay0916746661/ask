import streamlit as st

st.set_page_config(page_title="CO-STAR 提問框架", layout="wide")

st.title("🎯 AI 高效提問框架 — CO-STAR")
st.caption("每次提問前快速梳理邏輯，讓 AI 給出更精準的回答")

st.markdown("---")

# --- 主要表單區 ---
left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader("📝 填寫你的需求")

    c = st.text_area("C — 背景 (Context)", placeholder="目前的狀況、限制或前情提要。告訴 AI「為什麼」要做這件事。", height=90)
    o = st.text_area("O — 目標 (Objective)", placeholder="你具體想要 AI 達成的結果或完成什麼任務。", height=90)
    s = st.text_area("S — 風格 (Style)", placeholder="AI 的語氣、身份或思維模式（例如：資深工程師、幽默、簡潔）。", height=80)
    t = st.text_area("T — 語調 (Tone)", placeholder="回覆的情感色彩（例如：專業客觀、充滿熱情、批判性思考）。", height=80)
    a = st.text_area("A — 對象 (Audience)", placeholder="這份內容是給誰看的（例如：初學者、資深開發者、5 歲小孩）。", height=80)
    r = st.text_area("R — 格式 (Response)", placeholder="輸出的樣式（例如：Markdown 表格、程式碼區塊、條列清單）。", height=80)

    generate = st.button("✨ 生成提示詞", type="primary", use_container_width=True)

with right:
    st.subheader("📤 生成結果")

    if generate:
        # 萬用句型組合
        parts = []
        if s:
            parts.append(f"你現在是一名 {s}。")
        if c:
            parts.append(f"背景是 {c}，")
        if o:
            parts.append(f"請幫我達成 {o}。")
        if a:
            parts.append(f"這份內容是要給 {a} 看的。")
        if t:
            parts.append(f"請用 {t} 進行說明，")
        if r:
            parts.append(f"並以 {r} 輸出結果。")

        if not any([c, o, s, t, a, r]):
            st.warning("請至少填寫一個欄位再生成。")
        else:
            prompt = "".join(parts)
            st.session_state["last_prompt"] = prompt

    if "last_prompt" in st.session_state and st.session_state["last_prompt"]:
        st.success("提示詞已生成，複製下方內容貼到 AI 對話框：")
        st.code(st.session_state["last_prompt"], language=None)

        st.markdown("---")
        st.markdown("**CO-STAR 完整版（含結構標籤）：**")

        structured = ""
        labels = {"C 背景": c, "O 目標": o, "S 風格": s, "T 語調": t, "A 對象": a, "R 格式": r}
        for label, val in labels.items():
            if val:
                structured += f"【{label}】{val}\n"
        st.code(structured.strip(), language=None)
    else:
        st.info("填寫左側表單後，點「生成提示詞」即可在此看到結果。")

        st.markdown("**萬用句型公式：**")
        st.code(
            "你現在是一名 [S 風格]。背景是 [C 背景]，\n"
            "請幫我達成 [O 目標]。\n"
            "這份內容是要給 [A 對象] 看的。\n"
            "請用 [T 語調] 進行說明，並以 [R 格式] 輸出結果。",
            language=None
        )

st.markdown("---")

# --- Cheat Sheet 摺疊區 ---
with st.expander("📚 進階技巧 Cheat Sheet（點擊展開）"):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**提升理解度（寫在提問最後）**")
        st.markdown("""
- 指定思考路徑：「請一步步思考 (Think step by step) 並列出你的邏輯推導過程。」
- 提供範例：「請參考這個範例：[附上範例]，並依照此格式處理以下資料。」
        """)

        st.markdown("**視覺優化**")
        st.markdown("""
- 「請使用 Markdown 語法，多利用標題、粗體與清單來增加可讀性。」
- 「請直接給出核心建議，省略多餘的開場白與結語。」
        """)

    with col2:
        st.markdown("**迭代與修正（根據 AI 回答追問）**")
        st.markdown("""
- 修正偏差：「這部分太專業了，請用更白話的方式解釋。」
- 挖掘深度：「針對剛才提到的第 X 點，能不能再詳細說明背後的原理？」
- 變換視角：「如果你是我的競爭對手，你會如何反駁這份計劃？」
- 尋找盲點：「關於這個問題，有沒有哪些是我沒考慮到的潛在風險？」
        """)

    st.markdown("---")
    st.markdown("**快捷鍵技巧 💡**")
    st.info("把以下模板存成手機「文字替換」快捷鍵（輸入 `askai` 自動展開）：\n\n背景 (Context)：\n目標 (Objective)：\n身份與風格 (Style/Tone)：\n輸出格式 (Response)：")
