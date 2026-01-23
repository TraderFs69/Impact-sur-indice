import streamlit as st
import pandas as pd
import yfinance as yf
import time

st.set_page_config(layout="wide")
NASDAQ_CAP = 0.14

# =========================
# LOAD TICKERS — COLONNE A
# =========================
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

ALL = sorted(set(dow + nasdaq + sp500))

# =========================
# YAHOO — TICKER PAR TICKER
# =========================
@st.cache_data(ttl=300)
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
            rows.append([t, last, ret])

            time.sleep(0.02)  # anti rate-limit
        except:
            failed.append(t)

    return (
        pd.DataFrame(rows, columns=["Ticker", "Price", "Return %"]),
        failed
    )

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
# BUILD INDEX
# =========================
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

# =========================
# UI
# =========================
st.title("📊 Impact (%) des actions sur les indices — Yahoo (robuste)")

if st.button("🔄 Calcul"):
    with st.spinner("Chargement Yahoo Finance…"):
        prices, failed = get_prices_and_returns(ALL)
        caps = get_caps(prices["Ticker"].tolist())

        st.caption(
            f"OK: {len(prices)} | Échoués: {len(failed)}"
        )

        if failed:
            with st.expander("Tickers échoués"):
                st.write(failed)

        c1, c2, c3 = st.columns(3)

        with c1:
            st.subheader("Dow Jones")
            st.dataframe(build_index(dow, "dow", prices, caps).head(15), width="stretch")

        with c2:
            st.subheader("S&P 500")
            st.dataframe(build_index(sp500, "sp500", prices, caps).head(15), width="stretch")

        with c3:
            st.subheader("Nasdaq 100")
            st.dataframe(build_index(nasdaq, "nasdaq", prices, caps).head(15), width="stretch")
