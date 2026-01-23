import streamlit as st
import pandas as pd
import requests
import yfinance as yf

st.set_page_config(layout="wide")
POLYGON_KEY = st.secrets["POLYGON_API_KEY"]
NASDAQ_CAP = 0.14

# =========================
# NORMALISATION UNIQUE
# =========================
def normalize(t):
    return str(t).upper().replace(".", "-").strip()

# =========================
# LOAD TICKERS
# =========================
def load_tickers(file):
    df = pd.read_excel(file)
    return (
        df.iloc[:, 0]
        .dropna()
        .apply(normalize)
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
        ticker = normalize(x["T"])
        close = x["c"]
        open_ = x["o"]

        if open_:
            ret = (close - open_) / open_ * 100
        else:
            ret = 0

        rows.append([ticker, close, ret])

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
# BUILD INDEX
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

    return df.sort_values("Impact %", ascending=False)

# =========================
# UI
# =========================
st.title("📊 Impact (%) des actions sur les indices — PRO")

if st.button("🔄 Calcul"):
    prices = get_grouped_prices()
    caps = get_caps(ALL)

    # 🔍 DEBUG VISUEL (IMPORTANT)
    st.caption(
        f"📊 Prix Polygon chargés : {len(prices)} | "
        f"Dow: {len(set(dow) & set(prices['Ticker']))} / {len(dow)} | "
        f"S&P: {len(set(sp500) & set(prices['Ticker']))} / {len(sp500)} | "
        f"Nasdaq: {len(set(nasdaq) & set(prices['Ticker']))} / {len(nasdaq)}"
    )

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
