import streamlit as st
import pandas as pd
import requests
import yfinance as yf

# ==================================================
# CONFIG
# ==================================================
st.set_page_config(layout="wide")
POLYGON_KEY = st.secrets["POLYGON_API_KEY"]
NASDAQ_CAP = 0.14

# ==================================================
# UTILS
# ==================================================
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

def safe_json(url):
    try:
        r = requests.get(url, timeout=6)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

# ==================================================
# LOAD TICKERS
# ==================================================
dow_tickers = load_tickers("Dow.xlsx")
nasdaq_tickers = load_tickers("Nasdaq100.xlsx")
sp500_tickers = load_tickers("sp500_constituents.xlsx")

ALL_TICKERS = list(set(dow_tickers + nasdaq_tickers + sp500_tickers))

# ==================================================
# POLYGON PRICES (PRO LOGIC)
# ==================================================
@st.cache_data(ttl=300)
def get_prev_close(ticker):
    data = safe_json(
        f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={POLYGON_KEY}"
    )
    if not data:
        return None
    res = data.get("results")
    if not res:
        return None
    return res[0].get("c")

@st.cache_data(ttl=15)
def get_last_trade(ticker):
    data = safe_json(
        f"https://api.polygon.io/v2/last/trade/{ticker}?apiKey={POLYGON_KEY}"
    )
    if not data:
        return None
    return data.get("results", {}).get("p")

# ==================================================
# MARKET CAPS (STABLE)
# ==================================================
@st.cache_data(ttl=86400)
def get_market_caps(tickers):
    caps = {}
    for t in tickers:
        try:
            caps[t] = yf.Ticker(t).fast_info.get("market_cap")
        except:
            caps[t] = None
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
        w[rest] += (w[rest] / w[rest].sum()) * excess
    return w / w.sum()

# ==================================================
# BUILD INDEX TABLE (BULLETPROOF)
# ==================================================
def build_index_df(tickers, index_type, caps):
    rows = []

    for t in tickers:
        prev = get_prev_close(t)
        if prev is None or prev == 0:
            continue

        last = get_last_trade(t)
        if last is None:
            last = prev  # marché fermé / limite API

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
            df["Weight (%)"] = apply_cap(df["Weight (%)"] / 100, NASDAQ_CAP) * 100

        df["Impact %"] = df["Weight (%)"] * df["Return %"] / 100

    df["Impact"] = df["Impact %"].apply(
        lambda x: "🟢 Positif" if x > 0 else "🔴 Négatif"
    )

    return df.sort_values("Impact %", ascending=False)

# ==================================================
# UI
# ==================================================
st.title("📊 Impact (%) des actions sur les indices — LIVE")

st.caption(
    "🟢 Marché ouvert : prix en temps réel • 🔵 Marché fermé : clôture précédente"
)

if st.button("🔄 Calcul live"):
    with st.spinner("Calcul en cours…"):
        caps = get_market_caps(ALL_TICKERS)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("🔵 Dow Jones")
            df_dow = build_index_df(dow_tickers, "dow", caps)
            st.dataframe(df_dow.head(15), width="stretch")

        with col2:
            st.subheader("🟢 S&P 500")
            df_sp = build_index_df(sp500_tickers, "sp500", caps)
            st.dataframe(df_sp.head(15), width="stretch")

        with col3:
            st.subheader("🟣 Nasdaq 100")
            df_nas = build_index_df(nasdaq_tickers, "nasdaq", caps)
            st.dataframe(df_nas.head(15), width="stretch")

else:
    st.info("Clique sur **Calcul live** pour afficher les contributions.")
