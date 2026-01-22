import streamlit as st
import pandas as pd
import requests
import yfinance as yf

# ==========================
# CONFIG
# ==========================
st.set_page_config(layout="wide")

POLYGON_KEY = st.secrets["POLYGON_API_KEY"]
NASDAQ_CAP = 0.14

# ==========================
# LOAD EXCEL FILES
# ==========================
def load_tickers(file):
    return (
        pd.read_excel(file)["Symbol"]
        .dropna()
        .astype(str)
        .str.replace(".", "-", regex=False)
        .str.upper()
        .unique()
    )

dow_tickers = load_tickers("Dow.xlsx")
nasdaq_tickers = load_tickers("Nasdaq100.xlsx")
sp500_tickers = load_tickers("sp500_constituents.xlsx")

# ==========================
# POLYGON SNAPSHOT LIVE
# ==========================
@st.cache_data(ttl=10, show_spinner=False)
def get_live_snapshot():
    url = (
        "https://api.polygon.io/v2/snapshot/locale/us/"
        f"markets/stocks/tickers?apiKey={POLYGON_KEY}"
    )
    r = requests.get(url, timeout=15).json()

    rows = []
    for item in r.get("tickers", []):
        t = item["ticker"]
        last = item.get("lastTrade", {}).get("p")
        prev = item.get("prevDay", {}).get("c")

        if last and prev and prev > 0:
            rows.append([t, last, (last - prev) / prev * 100])

    return pd.DataFrame(rows, columns=["Ticker", "Price", "Return %"])

# ==========================
# MARKET CAPS — FAST & SAFE
# ==========================
@st.cache_data(ttl=86400, show_spinner=False)
def get_market_caps(tickers):
    caps = {}
    for t in tickers:
        try:
            fi = yf.Ticker(t).fast_info
            caps[t] = fi.get("market_cap")
        except:
            caps[t] = None
    return caps

# ==========================
# NASDAQ CAP
# ==========================
def apply_cap(weights, cap=NASDAQ_CAP):
    w = weights.copy()
    while w.max() > cap:
        excess = (w[w > cap] - cap).sum()
        w[w > cap] = cap
        redistribute = w < cap
        w[redistribute] += (w[redistribute] / w[redistribute].sum()) * excess
    return w / w.sum()

# ==========================
# BUILD INDEX TABLE (% IMPACT)
# ==========================
def build_index_df(tickers, index_type, prices, caps):
    df = prices[prices["Ticker"].isin(tickers)].copy()
    if df.empty:
        return df

    if index_type == "dow":
        total_price = df["Price"].sum()
        df["Weight (%)"] = df["Price"] / total_price * 100
        df["Impact %"] = df["Weight (%)"] * df["Return %"] / 100

    else:
        df["MarketCap"] = df["Ticker"].map(caps)
        df = df.dropna(subset=["MarketCap"])

        df["Weight (%)"] = df["MarketCap"] / df["MarketCap"].sum() * 100
        if index_type == "nasdaq":
            df["Weight (%)"] = apply_cap(df["Weight (%)"] / 100) * 100

        df["Impact %"] = df["Weight (%)"] * df["Return %"] / 100

    df["Impact"] = df["Impact %"].apply(
        lambda x: "🟢 Positif" if x > 0 else "🔴 Négatif"
    )

    return df.sort_values("Impact %", ascending=False)[
        ["Ticker", "Price", "Return %", "Weight (%)", "Impact %", "Impact"]
    ]

# ==========================
# STREAMLIT UI
# ==========================
st.title("📊 Contribution (%) LIVE aux indices")

if st.button("🔄 Calcul live"):
    prices = get_live_snapshot()
    all_tickers = set(dow_tickers) | set(sp500_tickers) | set(nasdaq_tickers)
    caps = get_market_caps(all_tickers)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("🔵 Dow Jones")
        st.dataframe(
            build_index_df(dow_tickers, "dow", prices, caps).head(15),
            width="stretch"
        )

    with col2:
        st.subheader("🟢 S&P 500")
        st.dataframe(
            build_index_df(sp500_tickers, "sp500", prices, caps).head(15),
            width="stretch"
        )

    with col3:
        st.subheader("🟣 Nasdaq 100")
        st.dataframe(
            build_index_df(nasdaq_tickers, "nasdaq", prices, caps).head(15),
            width="stretch"
        )

else:
    st.info("Clique sur **Calcul live**.")
