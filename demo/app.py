import streamlit as st
import pandas as pd
import requests
import yfinance as yf
import feedparser
from google import genai
from urllib.parse import quote

# =====================================
# 1. 網頁基本設定
# =====================================
st.set_page_config(
    page_title="AI與經濟分析儀表板｜第13組",
    page_icon="📊",
    layout="wide"
)

st.title("📊 AI與經濟分析儀表板")
st.write("第13組｜結合經濟數據、金融市場及財經新聞 NLP 情緒分析")

# =====================================
# 2. 從 Secrets 讀取 FRED API Key
# =====================================
try:
    FRED_API_KEY = st.secrets["FRED_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("請先到 Streamlit Secrets 設定 FRED_API_KEY")
    st.stop()

# Gemini Key 可稍後設定；沒有 Key 不影響前三頁。
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")

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
        "observation_start": start,
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data["observations"])
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
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
# 5. 新增：RSS 財經新聞讀取函式
# =====================================
@st.cache_data(ttl=900)
def fetch_google_news(keyword):
    """搜尋近 7 天相關新聞，取前 8 則；不需要新聞 API Key。"""
    encoded_query = quote(f"{keyword.strip()} when:7d")
    url = (
        "https://news.google.com/rss/search?"
        f"q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    )
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Educational Streamlit Dashboard)"},
        timeout=20,
    )
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    if feed.bozo and not feed.entries:
        raise ValueError("RSS 回傳內容無法解析")
    return [
        {
            "title": entry.get("title", "無標題"),
            "link": entry.get("link", ""),
            "published": entry.get("published", "未提供發布時間"),
        }
        for entry in feed.entries[:8]
