import streamlit as st
import pandas as pd
import yfinance as yf
import time

# ======================================
# CONFIG
# ======================================
st.set_page_config(layout="wide")

NASDAQ_CAP = 0.14
DOW_DIVISOR = 0.151987

SP500_LEVEL = 5000     # approximation (modifiable)
NASDAQ_LEVEL = 17000  # approximation (modifiable)

# ======================================
# LOAD TICKERS
# ======================================
def load_tickers(file):
    df = pd.read_excel(file, usecols=["Symbol"])
    return (
        df["Symbol"]
        .dropna()
        .astype(str)
        .str.upper()
        .str.replace(".", "-", regex=False)
        .unique()
        .tolist()
    )

dow = load_tickers("Dow.xlsx")
nasdaq = load_tickers("Nasdaq100.xlsx")
sp500 = load_tickers("sp500_constituents.xlsx")

ALL_TICKERS = sorted(set(dow + nasdaq + sp500))

# ======================================
# PRICES + RETURNS
# ======================================
@st.cache_data(ttl=120)
def get_prices_and_returns(tickers):
    rows = []
    failed = []

    for t in tickers:
        try:
            hist = yf.Ticker(t).history(period="2d")
            if len(hist) < 2:
                failed.append(t)
                continue

            prev = hist["Close"].iloc[-2]
            last = hist["Close"].iloc[-1]

            if prev == 0 or pd.isna(prev) or pd.isna(last):
                failed.append(t)
                continue

            ret = (last - prev) / prev * 100
            delta = last - prev

            rows.append([t, last, ret, delta])
            time.sleep(0.015)

        except:
            failed.append(t)

    return pd.DataFrame(
        rows,
        columns=["Ticker", "Price", "Return %", "Delta $"]
    ), failed

# ======================================
# MARKET CAPS
# ======================================
@st.cache_data(ttl=3600)
def get_market_caps(tickers):
    caps = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            cap = tk.fast_info.get("market_cap")
            if cap is None:
                cap = tk.info.get("marketCap")
            caps[t] = cap
            time.sleep(0.01)
        except:
            caps[t] = None
    return caps

# ======================================
# NASDAQ CAP
# ======================================
def apply_cap(weights, cap):
    w = weights.copy()
    while not w.empty and w.max() > cap:
        excess = (w[w > cap] - cap).sum()
        w[w > cap] = cap
        rest = w < cap
        w[rest] += w[rest] / w[rest].sum() * excess
    return w / w.sum()

# ======================================
# BUILD INDEX
# ======================================
def build_index(tickers, kind, prices, caps):
    df = prices[prices["Ticker"].isin(tickers)].copy()
    if df.empty:
        return df, 0

    if kind == "dow":
        total_price = df["Price"].sum()
        df["Weight %"] = df["Price"] / total_price * 100
        df["Impact x100"] = df["Weight %"] * df["Return %"]

        total_points = df["Delta $"].sum() / DOW_DIVISOR

    else:
        df["MarketCap"] = df["Ticker"].map(caps)
        df = df[df["MarketCap"].notna() & (df["MarketCap"] > 0)]

        df["Weight %"] = df["MarketCap"] / df["MarketCap"].sum() * 100

        if kind == "nasdaq":
            df["Weight %"] = apply_cap(df["Weight %"] / 100, NASDAQ_CAP) * 100

        df["Impact x100"] = df["Weight %"] * df["Return %"]
        total_impact_pct = df["Impact x100"].sum() / 100

        if kind == "sp500":
            total_points = SP500_LEVEL * total_impact_pct
        else:
            total_points = NASDAQ_LEVEL * total_impact_pct

    df["Sens"] = df["Impact x100"].apply(lambda x: "🟢" if x > 0 else "🔴")

    df = df.drop(columns=["Ticker", "MarketCap"], errors="ignore")

    return df.sort_values("Impact x100", ascending=False), total_points

# ======================================
# UI
# ======================================
st.title("📊 Impact des actions sur les indices — Yahoo Finance")

if st.button("🔄 Calcul live"):
    with st.spinner("Calcul en cours…"):
        prices, failed = get_prices_and_returns(ALL_TICKERS)
        caps = get_market_caps(prices["Ticker"].tolist())

        col1, col2, col3 = st.columns(3)

        dow_df, dow_pts = build_index(dow, "dow", prices, caps)
        sp_df, sp_pts = build_index(sp500, "sp500", prices, caps)
        nas_df, nas_pts = build_index(nasdaq, "nasdaq", prices, caps)

        with col1:
            st.subheader("🔵 Dow Jones")
            st.metric("Impact total", f"{dow_pts:+.2f} points")
            st.dataframe(dow_df.head(15), width="stretch")

        with col2:
            st.subheader("🟢 S&P 500")
            st.metric("Impact estimé", f"{sp_pts:+.2f} points")
            st.dataframe(sp_df.head(15), width="stretch")

        with col3:
            st.subheader("🟣 Nasdaq 100")
            st.metric("Impact estimé", f"{nas_pts:+.2f} points")
            st.dataframe(nas_df.head(15), width="stretch")

        if failed:
            with st.expander("Tickers échoués"):
                st.write(failed)
