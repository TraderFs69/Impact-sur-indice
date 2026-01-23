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
# YAHOO — PRICES + RETURNS
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

            time.sleep(0.015)
        except:
            failed.append(t)

    return pd.DataFrame(rows, columns=["Ticker", "Price", "Return %"]), failed

# ======================================
# MARKET CAPS — ROBUSTE (FAST + FALLBACK)
# ======================================
@st.cache_data(ttl=3600)
def get_market_caps(tickers):
    caps = {}

    for t in tickers:
        try:
            tk = yf.Ticker(t)

            # 1️⃣ fast_info
            cap = tk.fast_info.get("market_cap")

            # 2️⃣ fallback info
            if cap is None:
                cap = tk.info.get("marketCap")

            caps[t] = cap
            time.sleep(0.01)

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
# BUILD INDEX
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
        df = df[df["MarketCap"].notna() & (df["MarketCap"] > 0)]

        if df.empty:
            return df

        df["Weight (%)"] = df["MarketCap"] / df["MarketCap"].sum() * 100

        if kind == "nasdaq":
            df["Weight (%)"] = apply_cap(df["Weight (%)"] / 100, NASDAQ_CAP) * 100

    # 👉 impact en % x 100 (visuel rapide)
    df["Impact x100"] = df["Weight (%)"] * df["Return %"]
    df["Sens"] = df["Impact x100"].apply(lambda x: "🟢" if x > 0 else "🔴")

    return df.sort_values("Impact x100", ascending=False)

# ======================================
# UI
# ======================================
st.title("📊 Impact des actions sur les indices — Yahoo Finance")

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
            st.subheader("🔵 Dow Jones")
            st.dataframe(
                build_index(dow, "dow", prices, caps).head(15),
                width="stretch"
            )

        with c2:
            st.subheader("🟢 S&P 500")
            st.dataframe(
                build_index(sp500, "sp500", prices, caps).head(15),
                width="stretch"
            )

        with c3:
            st.subheader("🟣 Nasdaq 100")
            st.dataframe(
                build_index(nasdaq, "nasdaq", prices, caps).head(15),
                width="stretch"
            )
else:
    st.info("Clique sur **Calcul live** pour afficher les impacts.")
