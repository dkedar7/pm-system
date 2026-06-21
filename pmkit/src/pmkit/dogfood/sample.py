"""Sample-app synthesis.

When a product's documented scenario needs an app to act on (streamlit-mcp serves a
Streamlit app), pm-dogfood synthesizes a minimal representative one rather than requiring
the operator to supply it. Kept tiny and deterministic so the same scenario reruns cleanly.
"""

from __future__ import annotations

SAMPLE_STREAMLIT_APP = '''import streamlit as st

if "saves" not in st.session_state:
    st.session_state.saves = 0

name = st.text_input("Name", value="world", key="name")
if st.button("Save", key="save"):
    st.session_state.saves += 1

st.markdown(f"Hello, {name}!")
st.markdown(f"saves = {st.session_state.saves}")
'''


def sample_streamlit_source() -> str:
    return SAMPLE_STREAMLIT_APP


def synth_streamlit_app(path: str) -> str:
    """Write the sample Streamlit app to ``path`` and return the path."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(SAMPLE_STREAMLIT_APP)
    return path
