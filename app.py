import streamlit as st
import pandas as pd

st.title("TEST LECTURE EXCEL – COLONNE A")

files = ["Dow.xlsx", "Nasdaq100.xlsx", "sp500_constituents.xlsx"]

for f in files:
    st.subheader(f)

    # lecture brute, sans aucune interprétation
    df = pd.read_excel(
        f,
        header=None,
        usecols=[0]   # colonne A réelle
    )

    st.write("Forme du DataFrame :", df.shape)
    st.write("10 premières cellules colonne A :")
    st.write(df.iloc[:10, 0].tolist())
