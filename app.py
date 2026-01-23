import streamlit as st
import pandas as pd
import requests

# ==================================================
# CONFIG
# ==================================================
st.set_page_config(layout="wide")
POLYGON_KEY = st.secrets["POLYGON_API_KEY"]
NASDAQ_CAP = 0.14

# ==================================================
# LOAD TICKERS (COLONNE A / Symbol)
# ==================================================
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

ALL_TICKERS = set(dow + nasdaq + sp500)

# ==================================================
# POLYGON SNAPSHOT (1 CALL)
# ==================================================
@st.cache_data(ttl=15)
def get_snapshot():
    url = (
        "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers"
        f"?apiKey={POLYGON_KEY}"
    )
    r = requests.get(url, timeout=10).json()

    rows = []
    for x in r.get("tickers", []):
        t = x.get("ticker")
        if t not in ALL_TICKERS:
            continue

        last = x.get("lastTrade", {}).get("p")
        prev = x.get("prevDay", {}).get("c")

        if last is None or prev is None or prev == 0:
            continue

        ret = (last - prev) / prev * 100
        rows.append([t, last, ret])

    return pd.DataFrame(rows, columns=["Ticker", "Price", "Return %"])

# ==================================================
# MARKET CAPS (POLYGON SNAPSHOT)
# ==================================================
@st.cache_data(ttl=300)
def get_market_caps():
    url = (
        "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers"
        f"?apiKey={POLYGON_KEY}"
    )
    r = requests.get(url, timeout=10).json()

    caps = {}
    for x in r.get("tickers", []):
        t = x.get("ticker")
        cap = x.get("marketCap")
        if t in ALL_TICKERS and cap:
            caps[t] = cap

    return caps

# ==================================================
# NASDAQ CAP FUNCTION
# ==================================================
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

# ==================================================
# BUILD INDEX TABLE
# ==================================================
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

    df["Impact"] = df["Impact %"].apply(
        lambda x: "🟢 Positif" if x > 0 else "🔴 Négatif"
    )

    return df.sort_values("Impact %", ascending=False)

# ==================================================
# UI
# ==================================================
st.title("📊 Impact LIVE (%) des actions sur les indices — Polygon")

if st.button("🔄 Calcul live"):
    with st.spinner("Récupération des données Polygon…"):
        prices = get_snapshot()
        caps = get_market_caps()

        st.caption(
            f"Chargés : {len(prices)} | "
            f"Dow {len(set(dow)&set(prices['Ticker']))}/{len(dow)} | "
            f"S&P {len(set(sp500)&set(prices['Ticker']))}/{len(sp500)} | "
            f"Nasdaq {len(set(nasdaq)&set(prices['Ticker']))}/{len(nasdaq)}"
        )

        c1, c2, c3 = st.columns(3)

        with c1:
            st.subheader("🔵 Dow Jones (price-weighted)")
            st.dataframe(build_index(dow, "dow", prices, caps).head(15), width="stretch")

        with c2:
            st.subheader("🟢 S&P 500 (cap-weighted)")
            st.dataframe(build_index(sp500, "sp500", prices, caps).head(15), width="stretch")

        with c3:
            st.subheader("🟣 Nasdaq 100 (cap-weighted + cap 14%)")
            st.dataframe(build_index(nasdaq, "nasdaq", prices, caps).head(15), width="stretch")

else:
    st.info("Clique sur **Calcul live** pour afficher les contributions.")
