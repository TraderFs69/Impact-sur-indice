import streamlit as st
import pandas as pd
import yfinance as yf

# =====================================
# CONFIG
# =====================================
st.set_page_config(layout="wide")
NASDAQ_CAP = 0.14

# =====================================
# LOAD TICKERS (COLONNE A / Symbol)
# =====================================
def load_tickers(file):
    df = pd.read_excel(file, usecols=["Symbol"])
    return (
        df["Symbol"]
        .dropna()
        .astype(str)
        .str.upper()
        .unique()
        .tolist()
    )

dow = load_tickers("Dow.xlsx")
nasdaq = load_tickers("Nasdaq100.xlsx")
sp500 = load_tickers("sp500_constituents.xlsx")

ALL_TICKERS = sorted(set(dow + nasdaq + sp500))

# =====================================
# YAHOO PRICES (BATCH, SAFE)
# =====================================
@st.cache_data(ttl=120)
def get_prices_and_returns(tickers):
    data = yf.download(
        tickers,
        period="2d",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
    )

    rows = []

    for t in tickers:
        if t not in data:
            continue

        df = data[t].dropna()
        if len(df) < 2:
            continue

        prev = df["Close"].iloc[-2]
        last = df["Close"].iloc[-1]

        if prev == 0:
            continue

        ret = (last - prev) / prev * 100
        rows.append([t, last, ret])

    return pd.DataFrame(rows, columns=["Ticker", "Price", "Return %"])

# =====================================
# MARKET CAPS
# =====================================
@st.cache_data(ttl=86400)
def get_market_caps(tickers):
    caps = {}
    for t in tickers:
        try:
            caps[t] = yf.Ticker(t).fast_info.get("market_cap")
        except:
            caps[t] = None
    return caps

# =====================================
# NASDAQ CAP
# =====================================
def apply_cap(weights, cap):
    w = weights.copy()
    while w.max() > cap:
        excess = (w[w > cap] - cap).sum()
        w[w > cap] = cap
        rest = w < cap
        w[rest] += w[rest] / w[rest].sum() * excess
    return w / w.sum()

# =====================================
# BUILD INDEX TABLE
# =====================================
def build_index(tickers, kind, prices, caps):
    df = prices[prices["Ticker"].isin(tickers)].copy()
    if df.empty:
        return df

    if kind == "dow":
        total = df["Price"].sum()
        df["Weight (%)"] = df["Price"] / total * 100
    else:
        df["MarketCap"] = df["Ticker"].map(caps)
        df = df.dropna(subset=["MarketCap"])
        df["Weight (%)"] = df["MarketCap"] / df["MarketCap"].sum() * 100

        if kind == "nasdaq":
            df["Weight (%)"] = apply_cap(df["Weight (%)"] / 100, NASDAQ_CAP) * 100

    df["Impact %"] = df["Weight (%)"] * df["Return %"] / 100
    return df.sort_values("Impact %", ascending=False)

# =====================================
# UI
# =====================================
st.title("📊 Impact (%) des actions sur les indices — Yahoo Finance")

if st.button("🔄 Calcul"):
    with st.spinner("Chargement Yahoo Finance…"):
        prices = get_prices_and_returns(ALL_TICKERS)
        caps = get_market_caps(prices["Ticker"].tolist())

        st.caption(
            f"Chargés : {len(prices)} | "
            f"Dow {len(set(dow)&set(prices['Ticker']))}/{len(dow)} | "
            f"S&P {len(set(sp500)&set(prices['Ticker']))}/{len(sp500)} | "
            f"Nasdaq {len(set(nasdaq)&set(prices['Ticker']))}/{len(nasdaq)}"
        )

        c1, c2, c3 = st.columns(3)

        with c1:
            st.subheader("🔵 Dow Jones")
            st.dataframe(build_index(dow, "dow", prices, caps).head(15), width="stretch")

        with c2:
            st.subheader("🟢 S&P 500")
            st.dataframe(build_index(sp500, "sp500", prices, caps).head(15), width="stretch")

        with c3:
            st.subheader("🟣 Nasdaq 100")
            st.dataframe(build_index(nasdaq, "nasdaq", prices, caps).head(15), width="stretch")
