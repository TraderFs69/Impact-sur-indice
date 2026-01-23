import streamlit as st
import pandas as pd
import yfinance as yf
import time

# =====================================
# CONFIG
# =====================================
st.set_page_config(layout="wide")
NASDAQ_CAP = 0.14

# =====================================
# LECTURE EXCEL — COLONNE A RÉELLE
# =====================================
def load_tickers(file):
    """
    Lecture brute de la colonne A d'Excel :
    - ignore les noms de colonnes
    - ignore les headers
    - contourne les fichiers Excel corrompus / exportés
    """
    df = pd.read_excel(
        file,
        usecols=[0],     # colonne A réelle
        header=None      # ignore complètement les headers
    )

    tickers = (
        df.iloc[1:, 0]   # saute la première ligne (titre visible)
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(".", "-", regex=False)
        .unique()
        .tolist()
    )

    return tickers

# =====================================
# LOAD TICKERS
# =====================================
dow = load_tickers("Dow.xlsx")
nasdaq = load_tickers("Nasdaq100.xlsx")
sp500 = load_tickers("sp500_constituents.xlsx")

ALL_TICKERS = sorted(set(dow + nasdaq + sp500))

# =====================================
# DEBUG ABSOLU (NE PAS ENLEVER)
# =====================================
st.write("🔍 DOW (10 premiers):", dow[:10])
st.write("🔍 NASDAQ (10 premiers):", nasdaq[:10])
st.write("🔍 S&P500 (10 premiers):", sp500[:10])

# =====================================
# YAHOO — TICKER PAR TICKER (FIABLE)
# =====================================
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

            if pd.isna(prev) or pd.isna(last) or prev == 0:
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

# =====================================
# MARKET CAPS
# =====================================
@st.cache_data(ttl=86400)
def get_caps(tickers):
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
    while not w.empty and w.max() > cap:
        excess = (w[w > cap] - cap).sum()
        w[w > cap] = cap
        rest = w < cap
        if rest.sum() == 0:
            break
        w[rest] += w[rest] / w[rest].sum() * excess
    return w / w.sum()

# =====================================
# BUILD INDEX
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
st.title("📊 Impact (%) des actions sur les indices — MODE DEBUG ABSOLU")

if st.button("🔄 Calcul"):
    with st.spinner("Chargement Yahoo Finance…"):
        prices, failed = get_prices_and_returns(ALL_TICKERS)
        caps = get_caps(prices["Ticker"].tolist())

        st.caption(
            f"✔ OK : {len(prices)} | ❌ Échoués : {len(failed)}"
        )

        if failed:
            with st.expander("Voir les tickers échoués"):
                st.write(failed)

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
