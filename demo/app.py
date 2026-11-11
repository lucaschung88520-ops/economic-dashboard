
import streamlit as st
import pandas as pd
import requests
import yfinance as yf

# =====================================
# 1. 網頁基本設定
# =====================================
st.set_page_config(
    page_title="AI與經濟分析儀表板",
    page_icon="📊",
    layout="wide"
)

st.title("📊 AI與經濟分析儀表板")
st.write("透過 API 自動取得最新經濟數據，觀察總體經濟與金融市場。")

# =====================================
# 2. 讀取 FRED API Key
# =====================================
try:
    FRED_API_KEY = st.secrets["FRED_API_KEY"]
except Exception:
    st.error("請先到 Streamlit Secrets 設定 FRED_API_KEY")
    st.stop()

# =====================================
# 3. FRED API 資料讀取函式
# =====================================
@st.cache_data(ttl=3600)
def get_fred_data(series_id, start="2020-01-01"):
    url = "https://api.stlouisfed.org/fred/series/observations"

    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    df = pd.DataFrame(data["observations"])

    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(
        df["value"], errors="coerce"
    )

    df = df.dropna(subset=["value"])
    df = df.set_index("date").sort_index()

    if df.empty:
        raise ValueError("找不到有效數據：" + series_id)

    return df["value"]


# =====================================
# 4. 黃金期貨價格
# =====================================
@st.cache_data(ttl=3600)
def get_gold_data():
    gold = yf.Ticker("GC=F")
    df = gold.history(period="5y")

    if df.empty:
        return pd.Series(dtype=float)

    result = df["Close"].dropna()
    result.index = result.index.tz_localize(None)

    return result


# =====================================
# 5. 取得經濟數據
# =====================================
with st.spinner("正在取得最新經濟數據..."):
    try:
        cpi = get_fred_data("CPIAUCSL")
        unemployment = get_fred_data("UNRATE")
        us_10y = get_fred_data("DGS10")
        us_2y = get_fred_data("DGS2")
        japan_10y = get_fred_data("IRLTLT01JPM156N")

    except Exception:
        st.error("FRED 資料讀取失敗，請檢查 API Key 與網路連線。")
        st.stop()

    try:
        gold = get_gold_data()
    except Exception:
        gold = pd.Series(dtype=float)

# =====================================
# 6. 分頁設計
# =====================================
tab1, tab2, tab3 = st.tabs([
    "📈 美國總體經濟",
    "🌍 黃金與日本公債",
    "🚦 美債倒掛警示"
])

# =====================================
# 第一頁：美國總體經濟
# =====================================
with tab1:

    st.header("🇺🇸 美國總體經濟指標")

    cpi_yoy = cpi.pct_change(12).dropna()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "美國 CPI 年增率",
            f"{cpi_yoy.iloc[-1]:.2f}%"
        )
        st.caption(
            f"資料月份：{cpi_yoy.index[-1]:%Y-%m}"
        )

    with col2:
        st.metric(
            "美國失業率",
            f"{unemployment.iloc[-1]:.2f}%"
        )
        st.caption(
            f"資料月份：{unemployment.index[-1]:%Y-%m}"
        )

    with col3:
        st.metric(
            "美國10年期公債殖利率",
            f"{us_10y.iloc[-1]:.2f}%"
        )
        st.caption(
            f"觀測日期：{us_10y.index[-1]:%Y-%m-%d}"
        )

    st.subheader("美國 CPI 年增率走勢")
    st.line_chart(cpi_yoy)

    st.subheader("美國失業率走勢")
    st.line_chart(unemployment)

    st.subheader("美國10年期公債殖利率")
    st.line_chart(us_10y)


# =====================================
# 第二頁：黃金與日本10年期公債
# =====================================
with tab2:

    st.header("🌍 國際金融市場")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🥇 黃金期貨價格")

        if not gold.empty:
            st.metric(
                "最新黃金期貨收盤價",
                f"US$ {gold.iloc[-1]:,.2f}"
            )

            st.caption(
                f"資料日期：{gold.index[-1]:%Y-%m-%d}"
            )

            st.line_chart(gold)

            st.caption(
                "資料來源：Yahoo Finance（GC=F），"
                "單位為美元／金衡盎司。"
                "此為黃金期貨，非黃金現貨。"
            )
        else:
            st.warning("目前無法取得黃金期貨數據。")

    with col2:
        st.subheader("🇯🇵 日本10年期公債殖利率")

        st.metric(
            "最新公債殖利率",
            f"{japan_10y.iloc[-1]:.2f}%"
        )

        st.caption(
            f"資料月份：{japan_10y.index[-1]:%Y-%m}"
        )

        st.line_chart(japan_10y)

        st.caption(
            "資料來源：FRED / OECD，"
            "單位為百分比，資料頻率為每月。"
        )


# =====================================
# 第三頁：美債殖利率倒掛
# =====================================
with tab3:

    st.header("🚦 美國公債殖利率倒掛警示")

    st.write(
        "殖利率利差 = 10年期公債殖利率 - 2年期公債殖利率"
    )

    # 對齊相同觀測日期
    rates = pd.concat(
        [
            us_10y.rename("10年期"),
            us_2y.rename("2年期")
        ],
        axis=1
    ).dropna()

    rates["利差"] = rates["10年期"] - rates["2年期"]

    latest = rates.iloc[-1]
    latest_date = rates.index[-1]

    yield_10y = latest["10年期"]
    yield_2y = latest["2年期"]
    spread = latest["利差"]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "10年期公債殖利率",
            f"{yield_10y:.2f}%"
        )

    with col2:
        st.metric(
            "2年期公債殖利率",
            f"{yield_2y:.2f}%"
        )

    with col3:
        st.metric(
            "10Y - 2Y 利差",
            f"{spread:.2f} 個百分點"
        )

    st.caption(
        f"共同觀測日期：{latest_date:%Y-%m-%d}"
    )

    st.divider()

    # 紅黃綠警示燈
    if spread < 0:
        st.error("🔴 紅燈：殖利率曲線倒掛！")
        st.write(
            "短期公債殖利率高於長期公債殖利率，"
            "可能反映市場對未來經濟成長的擔憂。"
        )

    elif spread <= 0.5:
        st.warning("🟡 黃燈：殖利率利差偏小")
        st.write(
            "殖利率曲線仍為正斜率，"
            "但長短期殖利率差距較小。"
        )

    else:
        st.success("🟢 綠燈：殖利率曲線為正斜率")
        st.write(
            "長期公債殖利率高於短期公債殖利率。"
        )

    st.caption(
        "燈號門檻為課堂示範設定，"
        "不代表官方景氣預測。"
    )

    st.subheader("10年期與2年期殖利率比較")
    st.line_chart(rates[["10年期", "2年期"]])

    st.subheader("殖利率利差歷史走勢")
    st.line_chart(rates["利差"])

    st.info(
        "當利差小於0時，表示殖利率曲線倒掛。"
        "倒掛是常見的景氣風險指標，"
        "但不代表經濟衰退一定發生。"
    )


# =====================================
# 7. 頁面底部
# =====================================
st.divider()

st.caption(
    "資料來源：FRED、OECD、Yahoo Finance。"
    "資料依各來源發布時間更新，"
    "不代表所有指標均為即時報價。"
)

st.caption("AI與經濟分析｜課堂 API 自動化實作")
