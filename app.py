import streamlit as st
import pandas as pd
import requests
import yfinance as yf

st.set_page_config(layout="wide")
POLYGON_KEY = st.secrets["POLYGON_API_KEY"]
NASDAQ_CAP = 0.14

# =========================
# LOAD TICKERS
# =========================
def load_tickers(file):
    df = pd.read_excel(file)
    return (
        df.iloc[:, 0]
        .dropna()
        .astype(str)
        .str.replace(".", "-", regex=False)
        .str.upper()
        .unique()
        .tolist()
    )

dow = load_tickers("Dow.xlsx")
nasdaq = load_tickers("Nasdaq100.xlsx")
sp500 = load_tickers("sp500_constituents.xlsx")
ALL = set(dow + nasdaq + sp500)

# =========================
# POLYGON GROUPED (STABLE)
# =========================
@st.cache_data(ttl=30)
def get_grouped_prices():
    url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/prev?apiKey={POLYGON_KEY}"
    r = requests.get(url, timeout=10).json()

    rows = []
    for x in r.get("results", []):
        rows.append([
            x["T"],
            x["c"],
            (x["c"] - x["o"]) / x["o"] * 100 if x["o"] else 0
        ])

    return pd.DataFrame(rows, columns=["Ticker", "Price", "Return %"])

# =========================
# MARKET CAPS
# =========================
@st.cache_data(ttl=86400)
def get_caps(tickers):
    caps = {}
    for t in tickers:
        try:
            caps[t] = yf.Ticker(t).fast_info.get("market_cap")
        except:
            caps[t] = None
    return caps

# =========================
# NASDAQ CAP
# =========================
def apply_cap(w, cap):
    while w.max() > cap:
        excess = (w[w > cap] - cap).sum()
        w[w > cap] = cap
        rest = w < cap
        w[rest] += w[rest] / w[rest].sum() * excess
    return w / w.sum()

# =========================
# BUILD TABLE
# =========================
def build_index(tickers, kind, prices, caps):
    df = prices[prices["Ticker"].isin(tickers)].copy()
    if df.empty:
        return df

    if kind == "dow":
        total = df["Price"].sum()
        df["Weight (%)"] = df["Price"] / total * 100
        df["Impact %"] = df["Weight (%)"] * df["Return %"] / 100
    else:
        df["MarketCap"] = df["Ticker"].map(caps)
        df = df.dropna(subset=["MarketCap"])
        df["Weight (%)"] = df["MarketCap"] / df["MarketCap"].sum() * 100

        if kind == "nasdaq":
            df["Weight (%)"] = apply_cap(df["Weight (%)"] / 100, NASDAQ_CAP) * 100

        df["Impact %"] = df["Weight (%)"] * df["Return %"] / 100

    df["Impact"] = df["Impact %"].apply(lambda x: "🟢" if x > 0 else "🔴")
    return df.sort_values("Impact %", ascending=False)

# =========================
# UI
# =========================
st.title("📊 Impact (%) des actions sur les indices — PRO")

if st.button("🔄 Calcul"):
    prices = get_grouped_prices()
    caps = get_caps(ALL)

    c1, c2, c3 = st.columns(
