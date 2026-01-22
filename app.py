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
# UTILS
# ==========================
def normalize_ticker(ticker: str) -> str:
    return ticker.replace(".", "-").strip().upper()

# ==========================
# LOAD EXCEL FILES
# ==========================
dow_tickers = (
    pd.read_excel("Dow.xlsx")["Symbol"]
    .dropna()
    .astype(str)
    .apply(normalize_ticker)
    .unique()
)

nasdaq_tickers = (
    pd.read_excel("Nasdaq100.xlsx")["Symbol"]
    .dropna()
    .astype(str)
    .apply(normalize_ticker)
    .unique()
)

sp500_tickers = (
    pd.read_excel("sp500_constituents.xlsx")["Symbol"]
    .dropna()
    .astype(str)
    .apply(normalize_ticker)
    .unique()
)

# ==========================
# POLYGON SNAPSHOT LIVE (1 CALL)
# ==========================
@st.cache_data(ttl=10, show_spinner=False)
def get_live_snapshot():
    url = (
        "https://api.polygon.io/v2/snapshot/locale/us/"
        f"markets/stocks/tickers?apiKey={POLYGON_KEY}"
    )
    r = requests.get(url, timeout=15).json()

    rows = []
    for item in r.get("tickers", []):
        t = item["ticker"]

        last = item.get("lastTrade", {}).get("p")
        prev = item.get("prevDay", {}).get("c")

        if last is None or prev is None or prev == 0:
            continue

        rows.append([
            t,
            last,
            last - prev,
            (last - prev) / prev * 100
        ])

    return pd.DataFrame(
        rows,
        columns=["Ticker", "Price", "Δ Price", "Return %"]
    )

# ==========================
# MARKET CAPS (CACHED 24h)
# ==========================
@st.cache_data(ttl=86400, show_spinner=False)
def get_market_caps(tickers):
    caps = {}
    for t in tickers:
        try:
            caps[t] = yf.Ticker(t).info.get("marketCap", None)
        except:
            caps[t] = None
    return caps

# ==========================
# NASDAQ CAP LOGIC
# ==========================
def apply_cap(weights, cap=NASDAQ_CAP):
    w = weights.copy()
    while w.max() > cap:
        excess = (w[w > cap] - cap).sum()
        w[w > cap] = cap
        redistribute = w < cap
        w[redistribute] += (w[redistribute] / w[redistribute].sum()) * excess
    return w / w.sum()

# ==========================
# BUILD INDEX TABLE (LIVE %)
# ==========================
def build_index_df(tickers, index_type, price_df, market_caps):
    df = price_df[price_df["Ticker"].isin(tickers)].copy()

    if df.empty:
        return df

    # --------------------------
    # DOW (price-weighted → %)
    # --------------------------
    if index_type == "dow":
        total_price = df["Price"].sum()
        df["Weight (%)"] = df["Price"] / total_price * 100
        df["Impact %"] = df["Δ Price"] / total_price * 100

    # --------------------------
    # S&P 500 / NASDAQ 100
    # --------------------------
    else:
        df["MarketCap"] = df["Ticker"].map(market_caps)
        df = df.dropna(subset=["MarketCap"])

        df["Weight (%)"] = df["MarketCap"] / df["MarketCap"].sum() * 100

        if index_type == "nasdaq":
            df["Weight (%)"] = apply_cap(df["Weight (%)"] / 100) * 100

        df["Impact %"] = (df["Weight (%)"] / 100) * df["Return %"]

    df["Impact"] = df["Impact %"].apply(
        lambda x: "🟢 Positif" if x > 0 else "🔴 Négatif"
    )

    return (
        df.sort_values("Impact %", ascending=False)
        [["Ticker", "Price", "Return %", "Weight (%)", "Impact %", "Impact"]]
    )

# ==========================
# STREAMLIT UI
# ==========================
st.title("📊 Contribution (%) LIVE des actions aux indices")

st.markdown(
    """
    🔴 **Prix temps réel Polygon (snapshot)**  
    🔵 Contribution exprimée en **% de l’indice**  
    """
)

if st.button("🔄 Calcul live"):
    with st.spinner("Récupération des prix LIVE…"):
        prices_df = get_live_snapshot()

        all_tickers = set(dow_tickers) | set(sp500_tickers) | set(nasdaq_tickers)
        market_caps = get_market_caps(all_tickers)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("🔵 Dow Jones")
            st.dataframe(
                build_index_df(dow_tickers, "dow", prices_df, market_caps).head(15),
                use_container_width=True
            )

        with col2:
            st.subheader("🟢 S&P 500")
            st.dataframe(
                build_index_df(sp500_tickers, "sp500", prices_df, market_caps).head(15),
                use_container_width=True
            )

        with col3:
            st.subheader("🟣 Nasdaq 100 (cap réaliste)")
            st.dataframe(
                build_index_df(nasdaq_tickers, "nasdaq", prices_df, market_caps).head(15),
                use_container_width=True
            )

else:
    st.info("Clique sur **Calcul live** pour afficher les contributions en temps réel.")

