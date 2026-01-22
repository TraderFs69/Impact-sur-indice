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

ALL_REQUIRED = set(dow_tickers) | set(nasdaq_tickers) | set(sp500_tickers)

# ==========================
# POLYGON SNAPSHOT (SAFE)
# ==========================
@st.cache_data(ttl=10)
def get_live_snapshot():
    url = (
        "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers"
        f"?apiKey={POLYGON_KEY}"
    )
    r = requests.get(url, timeout=20)

    if r.status_code != 200:
        return pd.DataFrame(columns=["Ticker", "Price", "Return %"])

    data = r.json().get("tickers", [])

    rows = []
    for item in data:
        t = item.get("ticker")
        last = item.get("lastTrade", {}).get("p")
        prev = item.get("prevDay", {}).get("c")

        if t and last and prev and prev > 0:
            rows.append([t, last, (last - prev) / prev * 100])

    return pd.DataFrame(rows, columns=["Ticker", "Price", "Return %"])

# ==========================
# MARKET CAPS (STABLE)
# ==========================
@st.cache_data(ttl=86400)
def get_market_caps(tickers):
    caps = {}
    for t in tickers:
        try:
            caps[t] = yf.Ticker(t).fast_info.get("market_cap")
        except:
            caps[t] = None
    return caps

# ==========================
# NASDAQ CAP
# ==========================
def apply_cap(weights, cap=NASDAQ_CAP):
    w = weights.copy()
    while not w.empty and w.max() > cap:
        excess = (w[w > cap] - cap).sum()
        w[w > cap] = cap
        redistribute = w < cap
        if redistribute.sum() == 0:
            break
        w[redistribute] += (w[redistribute] / w[redistribute].sum()) * excess
    return w / w.sum()

# ==========================
# BUILD INDEX TABLE (SAFE)
# ==========================
def build_index_df(tickers, index_type, prices, caps):
    df = prices[prices["Ticker"].isin(tickers)].copy()
    if df.empty:
        return pd.DataFrame()

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

    df["Impact"] = df["Impact %"].apply(lambda x: "🟢 Positif" if x > 0 else "🔴 Négatif")
    return df.sort_values("Impact %", ascending=False)

# ==========================
# UI
# ==========================
st.title("📊 Contribution LIVE (%) aux indices")

if st.button("🔄 Calcul live"):
    prices_df = get_live_snapshot()

    # 🔍 DIAGNOSTIC VISUEL
    st.write("📡 Tickers reçus de Polygon :", len(prices_df))
    st.write("🎯 Tickers attendus :", len(ALL_REQUIRED))

    if prices_df.empty:
        st.error(
            "❌ Aucune donnée live reçue de Polygon.\n\n"
            "Causes possibles :\n"
            "- Marché fermé\n"
            "- Snapshot non inclus dans ton plan Polygon\n"
            "- Limite API atteinte"
        )
        st.stop()

    caps = get_market_caps(ALL_REQUIRED)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("🔵 Dow Jones")
        st.dataframe(build_index_df(dow_tickers, "dow_

