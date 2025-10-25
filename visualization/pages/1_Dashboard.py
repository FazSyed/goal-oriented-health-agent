import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from Overview import load_data

st.title("Dehydration Monitoring Dashboard")

df = load_data()

# container = st.container(border=True)
with st.container(border=True):
    st.subheader("TBW Loss % Over Time")
    st.line_chart(df.head(100), x='TIMESTAMP', y='TBW_LOSS%')

with st.container(border=True):
    # cols = st.columns(2)
    # with cols[0]:
        st.subheader("Risk Status Counts")
        st.bar_chart(df['RISK_STATUS'].value_counts(), color='#FF9F36')

    # with cols[1]:
    #     st.subheader("Pie Chart of Risk Status")
    #     plt.pie(df['RISK_STATUS'].value_counts(), labels=df['RISK_STATUS'].value_counts().index, autopct='%1.1f%%')
    #     st.pyplot(plt)