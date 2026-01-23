import streamlit as st
import pandas as pd
import yfinance as yf
import time

# ======================================
# CONFIG
# ======================================
st.set_page_config(layout="wide")
NASDAQ_CAP = 0.14

# ======================================
# LOAD TICKERS — COLONNE A (Symbol)
# ======================================
def load_tickers(file):
    df = pd.read_excel(file, usecols=["Symbol"])
    return (
        df["Symbol"]
        .dropna()
        .astype(str)
        .str.strip()
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
# YAHOO — PRIX + RETURN (TICKER PAR TICKER)
# ======================================
@st.cache_data(ttl=120)
def get_prices_and_returns(tickers):
    rows = []
    failed = []

    for t in tickers:
        try:
            hist = yf.Ticker(t).history(period="2d", interval="1d")
            if len(hist) < 2:
                failed.append(t)
                continue

            prev = hist["Close"].iloc[-2]
            last = hist["Close"].iloc[-1]

            if pd.isna(prev) or pd.isna(last) or prev == 0:
                failed.append(t)
                continue

            ret = (last - prev) / prev * 100
            rows.append([t, last, ret])

            time.sleep(0.02)  # anti rate-limit
        except:
            failed.append(t)

    df = pd.DataFrame(rows, columns=["Ticker", "Price", "Return %"])
    return df, failed

# ======================================
# MARKET CAPS — YAHOO
# ======================================
@st.cache_data(ttl=3600)
def get_market_caps(tickers):
    caps = {}
    for t in tickers:
        try:
            caps[t] = yf.Ticker(t).fast_info.get("market_cap")
        except:
            caps[t] = None
    return caps

# ======================================
# NASDAQ WEIGHT CAP
# ======================================
def apply_cap(weights, cap):
    w = weights.copy()
    while not w.empty and w.max() > cap:
        excess = (w[w > cap] - cap).sum()
        w[w > cap] = cap
        rest = w < cap
        if rest.sum() == 0:
            break
        w[rest] += w[rest] / w[rest].sum() * excess
    return w / w.sum()

# ======================================
# BUILD INDEX TABLE
# ======================================
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
    df["Impact sens"] = df["Impact %"].apply(
        lambda x: "🟢 Positif" if x > 0 else "🔴 Négatif"
    )

    return df.sort_values("Impact %", ascending=False)

# ======================================
# UI
# ======================================
st.title("📊 Impact (%) des actions sur les indices — Yahoo Finance")

if st.button("🔄 Calcul live"):
    with st.spinner("Récupération Yahoo Finance…"):
        prices, failed = get_prices_and_returns(ALL_TICKERS)
        caps = get_market_caps(prices["Ticker"].tolist())

        st.caption(
            f"Chargés : {len(prices)} | "
            f"Dow {len(set(dow)&set(prices['Ticker']))}/{len(dow)} | "
            f"S&P {len(set(sp500)&set(prices['Ticker']))}/{len(sp500)} | "
            f"Nasdaq {len(set(nasdaq)&set(prices['Ticker']))}/{len(nasdaq)}"
        )

        if failed:
            with st.expander("Tickers échoués (Yahoo)"):
                st.write(failed)

        c1, c2, c3 = st.columns(3)

        with c1:
            st.subheader("🔵 Dow Jones (price-weighted)")
            st.dataframe(
                build_index(dow, "dow", prices, caps).head(15),
                width="stretch"
            )

        with c2:
            st.subheader("🟢 S&P 500 (cap-weighted)")
            st.dataframe(
                build_index(sp500, "sp500", prices, caps).head(15),
                width="stretch"
            )

        with c3:
            st.subheader("🟣 Nasdaq 100 (cap-weighted, cap 14 %)")
            st.dataframe(
                build_index(nasdaq, "nasdaq", prices, caps).head(15),
                width="stretch"
            )
else:
    st.info("Clique sur **Calcul live** pour afficher les impacts.")
