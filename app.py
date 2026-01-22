import streamlit as st
import pandas as pd
import requests
import yfinance as yf

# ==========================
# CONFIG
# ==========================
st.set_page_config(layout="wide")

DOW_DIVISOR = 0.151987
NASDAQ_CAP = 0.14
POLYGON_KEY = st.secrets["POLYGON_API_KEY"]

# ==========================
# LOAD EXCEL FILES
# ==========================
dow_tickers = pd.read_excel("Dow.xlsx")["Symbol"].dropna().unique().tolist()
nasdaq_tickers = pd.read_excel("Nasdaq100.xlsx")["Ticker"].dropna().unique().tolist()
sp500_tickers = pd.read_excel("sp500_constituents.xlsx")["Symbol"].dropna().unique().tolist()

# ==========================
# DATA FETCH (CACHED)
# ==========================
@st.cache_data(ttl=30, show_spinner=False)
def get_polygon_price(ticker):
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=5).json()
        if "results" not in r:
            return None, None
        close = r["results"][0]["c"]
        open_ = r["results"][0]["o"]
        return close, close - open_
    except:
        return None, None


@st.cache_data(ttl=3600, show_spinner=False)
def get_market_cap(ticker):
    try:
        return yf.Ticker(ticker).info.get("marketCap", None)
    except:
        return None

# ==========================
# NASDAQ CAP LOGIC
# ==========================
def apply_cap(weights, cap=NASDAQ_CAP):
    weights = weights.copy()
    while weights.max() > cap:
        excess = (weights[weights > cap] - cap).sum()
        weights[weights > cap] = cap
        redistribute = weights < cap
        weights[redistribute] += (
            weights[redistribute] / weights[redistribute].sum()
        ) * excess
    return weights / weights.sum()

# ==========================
# BUILD INDEX TABLE
# ==========================
def build_index_df(tickers, index_type):
    rows = []

    for t in tickers:
        price, delta = get_polygon_price(t)
        if price is None or delta is None:
            continue

        mcap = get_market_cap(t)
        rows.append([t, price, delta, mcap])

    df = pd.DataFrame(rows, columns=["Ticker", "Price", "Δ Price", "MarketCap"])
    if df.empty:
        return df

    if index_type == "dow":
        df["Weight (%)"] = df["Price"] / df["Price"].sum() * 100
        df["Impact (pts)"] = df["Δ Price"] / DOW_DIVISOR

    else:
        df = df.dropna(subset=["MarketCap"])
        df["Weight (%)"] = df["MarketCap"] / df["MarketCap"].sum() * 100

        if index_type == "nasdaq":
            df["Weight (%)"] = apply_cap(df["Weight (%)"] / 100) * 100

        INDEX_LEVEL = 100  # échelle visuelle
        df["Impact (pts)"] = (df["Weight (%)"] / 100) * df["Δ Price"] * INDEX_LEVEL

    # Impact direction
    df["Impact"] = df["Impact (pts)"].apply(
        lambda x: "🟢 Positif" if x > 0 else "🔴 Négatif"
    )

    df = df.sort_values("Impact (pts)", ascending=False)
    return df[
        ["Ticker", "Price", "Δ Price", "Weight (%)", "Impact (pts)", "Impact"]
    ]

# ==========================
# STREAMLIT UI
# ==========================
st.title("📊 Impact des actions sur les indices (Live)")
st.markdown(
    """
    **Méthodologie**
    - 🔵 Dow Jones : price-weighted  
    - 🟢 S&P 500 : market-cap weighted  
    - 🟣 Nasdaq 100 : market-cap weighted avec cap réaliste  
    """
)

if st.button("🔄 Calcul live"):
    with st.spinner("Calcul en cours…"):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("🔵 Dow Jones")
            dow_df = build_index_df(dow_tickers, "dow")
            st.dataframe(dow_df.head(15), use_container_width=True)

        with col2:
            st.subheader("🟢 S&P 500")
            sp_df = build_index_df(sp500_tickers, "sp500")
            st.dataframe(sp_df.head(15), use_container_width=True)

        with col3:
            st.subheader("🟣 Nasdaq 100 (cap réaliste)")
            nasdaq_df = build_index_df(nasdaq_tickers, "nasdaq")
            st.dataframe(nasdaq_df.head(15), use_container_width=True)

else:
    st.info("Clique sur **Calcul live** pour lancer le calcul.")
