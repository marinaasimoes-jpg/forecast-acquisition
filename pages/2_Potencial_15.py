# -*- coding: utf-8 -*-
"""Lente Potencial Atualizado (15%) — forecast sobre 15% do potencial.

Página multipage do Monthly Commercial Planning (refatoração 2026-11-03).
Wrapper fino: toda a lógica vive em dashboard.render_lente. A curva é
reavaliada pelo potencial_15 (um deal <20k no total pode cair na faixa high).
"""
import streamlit as st

import dashboard

st.set_page_config(page_title="Potencial Atualizado (15%) — Monthly Commercial Planning",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(dashboard._CSS(), unsafe_allow_html=True)
dashboard.render_lente("15", "p15")
