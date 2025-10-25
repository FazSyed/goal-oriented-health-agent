import streamlit as st
import pandas as pd
from Overview import load_data

df = load_data()

st.title("Dehydration Monitoring Data")
st.write(df)

filter = st.selectbox("Select Risk Status", ("-", "Euhydrated", "Mild", "Moderate", "Severe", "Unknown"))

if filter != "-":
    filtered_df = df[df['RISK_STATUS'] == filter]
    st.subheader(f"{filter} Risk Status")
    st.write(filtered_df)
    st.write(f"Number of Records: {len(filtered_df)}")