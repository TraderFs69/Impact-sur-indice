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
    )

dow_tickers = load_tickers("Dow.xlsx")
nasdaq_tickers = load_tickers("Nasdaq100.xlsx")
sp500_tickers = load_tickers("sp500_constituents.xlsx")

ALL_REQUIRED_TICKERS = set(dow_tickers) | set(nasdaq_tickers) | set(sp500_tickers)

# ==========================
# POLYGON SNAPSHOT LIVE (PAGINATED + SAFE)
# ==========================
@st.cache_data(ttl=10, show_spinner=False)
def get_live_snapshot(required_tickers):
    collected = {}
    cursor = None

    while True:
        url = (
            "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers"
            f"?apiKey={POLYGON_KEY}"
        )
        if cursor:
            url += f"&cursor={cursor}"

        r = requests.get(url, timeout=20).json()

        for item in r.get("tickers", []):
            t = item.get("ticker")
            if t not in required_tickers or t in collected:
                continue

            last = item.get("lastTrade", {}).get("p")
            prev = item.get("prevDay", {}).get("c")

            if last is not None and prev and prev > 0:
                collected[t] = {
                    "Ticker": t,
                    "Price": last,
                    "Return %": (last - prev) / prev * 100
                }

        if len(collected) == len(required_tickers):
            break

        cursor = r.get("next_url")
        if not cursor:
            break

    # 🔐 IMPORTANT : colonnes garanties
    return pd.DataFrame(
        collected.values(),
        columns=["Ticker", "Price", "Return %"]
    )

# ==========================
# MARKET CAPS — FAST & SAFE
# ==========================
@st.cache_data(ttl=86400, show_spinner=False)
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
    while w.max() > cap:
        excess = (w[w > cap] - cap).sum()
        w[w > cap] = cap
        redistribute = w < cap
        w[redistribute] += (w[redistribute] / w[redistribute].sum()) * excess
    return w / w.sum()

# ==========================
# BUILD INDEX TABLE (SAFE)
# ==========================
def build_index_df(tickers, index_type, prices, caps):

    # 🔐 Sécurité absolue
    if prices.empty or "Ticker" not in prices.columns:
        return pd.DataFrame(
            columns=["Ticker", "Price", "Return %", "Weight (%)", "Impact %", "Impact"]
        )

    df = prices[prices["Ticker"].isin(tickers)].copy()
    if df.empty:
        return df

    if index_type == "dow":
        total_price = df["Price"].sum()
        df["Weight (%)"] = df["Price"] / total_price * 100
        df["Impact %"] = df["Weight (%)"] * df["Return %"] / 100

    else:
        df["MarketCap"] = df["Ticker"].map(caps)
        df = df.dropna(subset=["MarketCap"])

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
# STREAMLIT UI
# ==========================
st.title("📊 Contribution (%) LIVE des actions aux indices")

if st.button("🔄 Calcul live"):
    with st.spinner("Chargement des données LIVE…"):
        prices_df = get_live_snapshot(ALL_REQUIRED_TICKERS)
        caps = get_market_caps(ALL_REQUIRED_TICKERS)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("🔵 Dow Jones")
            st.dataframe(
                build_index_df(dow_tickers, "dow", prices_df, caps).head(15),
                width="stretch"
            )

        with col2:
            st.subheader("🟢 S&P 500")
            st.dataframe(
                build_index_df(sp500_tickers, "sp500", prices_df, caps).head(15),
                width="stretch"
            )

        with col3:
            st.subheader("🟣 Nasdaq 100")
            st.dataframe(
                build_index_df(nasdaq_tickers, "nasdaq", prices_df, caps).head(15),
                width="stretch"
            )

else:
    st.info("Clique sur **Calcul live** pour afficher les contributions.")
