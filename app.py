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
        .tolist()
    )

dow_tickers = load_tickers("Dow.xlsx")
nasdaq_tickers = load_tickers("Nasdaq100.xlsx")
sp500_tickers = load_tickers("sp500_constituents.xlsx")

ALL_TICKERS = list(set(dow_tickers + nasdaq_tickers + sp500_tickers))

# ==========================
# POLYGON — SAFE FUNCTIONS
# ==========================
@st.cache_data(ttl=20)
def get_last_price(ticker):
    try:
        r = requests.get(
            f"https://api.polygon.io/v2/last/trade/{ticker}?apiKey={POLYGON_KEY}",
            timeout=5,
        )
        if r.status_code != 200:
            return None
        return r.json().get("results", {}).get("p")
    except:
        return None


@st.cache_data(ttl=300)
def get_prev_close(ticker):
    try:
        r = requests.get(
            f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={POLYGON_KEY}",
            timeout=5,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        results = data.get("results")
        if not results or len(results) == 0:
            return None
        return results[0].get("c")
    except:
        return None

# ==========================
# MARKET CAPS — STABLE
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
# BUILD INDEX TABLE
# ==========================
def build_index_df(tickers, index_type, caps):
    rows = []

    for t in tickers:
        last = get_last_price(t)
        prev = get_prev_close(t)

        if last is None or prev is None or prev == 0:
            continue

        ret = (last - prev) / prev * 100
        rows.append([t, last, ret])

    if not rows:
        return pd.DataFrame(
            columns=["Ticker", "Price", "Return %", "Weight (%)", "Impact %", "Impact"]
        )

    df = pd.DataFrame(rows, columns=["Ticker", "Price", "Return %"])

    if index_type == "dow":
        total_price = df["Price"].sum()
        df["Weight (%)"] = df["Price"] / total_price * 100
        df["Impact %"] = df["Weight (%)"] * df["Return %"] / 100
    else:
        df["MarketCap"] = df["Ticker"].map(caps)
        df = df.dropna(subset=["MarketCap"])
        if df.empty:
            return df

        df["Weight (%)"] = df["MarketCap"] / df["MarketCap"].sum() * 100

        if index_type == "nasdaq":
            df["Weight (%)"] = apply_cap(df["Weight (%)"] / 100) * 100

        df["Impact %"] = df["Weight (%)"] * df["Return %"] / 100

    df["Impact"] = df["Impact %"].apply(
        lambda x: "🟢 Positif" if x > 0 else "🔴 Négatif"
    )

    return df.sort_values("Impact %", ascending=False)[
        ["Ticker", "Price", "Return %", "Weight (%)", "Impact %", "Impact"]
    ]

# ==========================
# UI
# ==========================
st.title("📊 Contribution LIVE (%) des actions aux indices")

st.markdown(
    """
    - Prix **temps réel Polygon**
    - Impact exprimé en **% de l’indice**
    - Code **robuste** (aucun crash possible)
    """
)

if st.button("🔄 Calcul live"):
    with st.spinner("Calcul en cours…"):
        caps = get_market_caps(ALL_TICKERS)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("🔵 Dow Jones")
            st.dataframe(
                build_index_df(dow_tickers, "dow", caps).head(15),
                width="stretch",
