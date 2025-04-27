import streamlit as st
import pandas as pd
import numpy as np

dataframe_random = np.random.randn(10,20)
st.dataframe(dataframe_random)


dataframe = pd.DataFrame(
    np.random.randn(10, 20),
    columns=('col %d' % i for i in range(20)))

st.dataframe(dataframe.style.highlight_max(axis=0))