# -*- coding: utf-8 -*-
"""Lente Potencial Total — forecast sobre o potencial absoluto de corridas.

Página multipage do Monthly Commercial Planning (refatoração 2026-11-03).
Wrapper fino: toda a lógica vive em dashboard.render_lente.
"""
import streamlit as st

import dashboard

st.set_page_config(page_title="Potencial Total — Monthly Commercial Planning",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(dashboard._CSS(), unsafe_allow_html=True)
dashboard.render_lente("total", "total")
