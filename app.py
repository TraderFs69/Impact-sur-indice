import streamlit as st
import pandas as pd
import yfinance as yf

# ==================================================
# CONFIG
# ==================================================
st.set_page_config(layout="wide")
NASDAQ_CAP = 0.14

# ==================================================
# NORMALISATION LÉGÈRE (SANS TRANSFORMATION DANGEREUSE)
# ==================================================
def normalize(t):
    return str(t).upper().strip().replace(".", "-")

# ==================================================
# LOAD TICKERS — COLONNE A / SYMBOL
# ==================================================
def load_tickers(file):
    df = pd.read_excel(file, usecols=["Symbol"])
    return (
        df["Symbol"]
        .dropna()
        .astype(str)
        .apply(normalize)
        .unique()
        .tolist()
    )

dow = load_tickers("Dow.xlsx")
nasdaq = load_tickers("Nasdaq100.xlsx")
sp500 = load_tickers("sp500_constituents.xlsx")

ALL_TICKERS = list(set(dow + nasdaq + sp500))

# ==================================================
# PRICES & RETURNS VIA YAHOO (ROBUSTE)
# ==================================================
@st.cache_data(ttl=120)
def get_prices_and_returns(tickers):
    data = yf.download(
        tickers,
        period="2d",
        interval="1d",
        group_by="ticker",
        threads=True,
        progress=False,
    )

    rows = []
    rejected = []

    for t in tickers:
        try:
            df = data[t]
            if len(df) < 2:
                rejected.append(t)
                continue

            prev = df["Close"].iloc[-2]
            last = df["Close"].iloc[-1]

            if pd.isna(prev) or pd.isna(last) or prev == 0:
                rejected.append(t)
                continue

            ret = (last - prev) / prev * 100
            rows.append([t, last, ret])
        except:
            rejected.append(t)

    return (
        pd.DataFrame(rows, columns=["Ticker", "Price", "Return %"]),
        rejected
    )

# ==================================================
# MARKET CAPS VIA YAHOO
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
# NASDAQ CAP
# ==================================================
def apply_cap(weights, cap):
    w = weights.copy()
    while w.max() > cap:
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
        df["Impact %"] = df["Weight (%)"] * df["Return %"] / 100
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
st.title("📊 Impact (%) des actions sur les indices — Yahoo Finance")

st.caption(
    "Lecture directe de la colonne A (Symbol). "
    "Les entrées non reconnues par Yahoo sont ignorées proprement."
)

if st.button("🔄 Calcul"):
    with st.spinner("Chargement des données Yahoo Finance…"):
        prices, rejected = get_prices_and_returns(ALL_TICKERS)
        caps = get_market_caps(prices["Ticker"].tolist())

        st.caption(
            f"Titres valides : {len(prices)} | "
            f"Rejetés (non reconnus) : {len(rejected)}"
        )

        if rejected:
            with st.expander("Voir les Symbol rejetés"):
                st.write(sorted(rejected))

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

else:
    st.info("Clique sur **Calcul** pour afficher les contributions.")
