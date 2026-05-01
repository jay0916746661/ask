
import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

# --- 1. 模擬數據獲取 (在實際應用中，這會是您的數據爬蟲或API調用) ---
def get_stock_data():
    # 範例抄底監控名單和模擬數據
    data = {
        "股票代碼": ["MSFT", "GOOG", "AMZN", "TSLA", "NFLX"],
        "當前市價": [400, 160, 180, 170, 550],
        "52週最高價": [420, 180, 200, 280, 600]
    }
    df = pd.DataFrame(data)
    return df

# --- 2. 抄底雷達代理人核心邏輯 ---
def run_bottom_fishing_radar(df, threshold_percent=20):
    df['跌幅 (%)'] = ((df['當前市價'] - df['52週最高價']) / df['52週最高價']) * 100
    
    # 篩選條件：距離 52 週最高點跌幅超過閾值
    bottom_fishing_candidates = df[df['跌幅 (%)'] <= -threshold_percent].copy()
    
    # 格式化跌幅顯示
    bottom_fishing_candidates['跌幅 (%)'] = bottom_fishing_candidates['跌幅 (%)'].map('{:.2f}%'.format)
    
    return bottom_fishing_candidates

# --- Streamlit 應用程式界面 ---
st.title("Jim's AI強化型投資儀表板")
st.subheader("抄底雷達代理人")

st.markdown("""
這個模組會監控您預設的股票清單，並識別出那些**距離52週最高點跌幅超過設定閾值**的潛在抄底標的。
幫助您在市場回調時，快速捕捉到優質資產的再投入機會。
""")

# 獲取模擬數據
stock_data = get_stock_data()

# 用戶可以調整跌幅閾值
threshold = st.slider("設定抄底跌幅閾值 (%)", min_value=10, max_value=50, value=20, step=5)

# 運行抄底雷達
candidates = run_bottom_fishing_radar(stock_data, threshold)

if not candidates.empty:
    st.success(f"發現 {len(candidates)} 個潛在抄底標的 (跌幅超過 {threshold}%)：")
    st.dataframe(candidates[['股票代碼', '當前市價', '52週最高價', '跌幅 (%)']])
else:
    st.info(f"目前沒有股票跌幅超過 {threshold}%，請耐心等待或調整閾值。")

st.markdown("---")
st.subheader("所有監控股票的當前狀態")
st.dataframe(stock_data.style.format({
    '當前市價': '${:.2f}'.format,
    '52週最高價': '${:.2f}'.format,
    '跌幅 (%)': '{:.2f}%'.format
}))

st.markdown("""
**下一步建議：**
1. 將 `get_stock_data()` 替換為連接您實際的股票數據源 (例如金融API或自建爬蟲)。
2. 整合「動態平衡公式」的賣出收回現金邏輯，並將收回的現金引導至此處進行再投入。
""")
