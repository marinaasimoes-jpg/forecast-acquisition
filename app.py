# -*- coding: utf-8 -*-
"""Monthly Commercial Planning — home leve (refatoração multipage 2026-11-03).

Página raiz do app multipage. As duas lentes de forecast vivem em:
  - pages/1_Potencial_Total.py   (potencial absoluto)
  - pages/2_Potencial_15.py      (15% do potencial, curva reavaliada)

Toda a lógica (cache, filtros, render) está em dashboard.py. Esta home é
intencionalmente leve: título, caption, 1 KPI e orientação — sem filtros
(Modelo B: filtros são por página de lente).

Rodar:  streamlit run app.py
Token:  env HUBSPOT_TOKEN ou secret HUBSPOT_TOKEN no Streamlit Cloud.
"""
import streamlit as st

import dashboard


def main():
    st.set_page_config(page_title="Monthly Commercial Planning", layout="wide",
                       initial_sidebar_state="expanded")
    st.markdown(dashboard._CSS(), unsafe_allow_html=True)

    st.title("Monthly Commercial Planning")
    st.caption(
        "Deals em **Negociação** (etapas 4/5/6), **Ativação** (etapa 7) e "
        "**Rampagem** (stage RAMP UP do pipeline B2B Retention). "
        "Volume de corridas previsto por mês (rampagem)."
    )

    # 1 KPI: total de deals em pipeline (soma das 3 categorias).
    neg, ativ, ramp, inc, meses, fetched_at, hoje, fetched_deals, \
        neg_15, ativ_15, ramp_15 = dashboard.get_data()
    total_deals = len(neg) + len(ativ) + len(ramp)

    k1, k2 = st.columns(2)
    k1.metric("Deals em pipeline", total_deals)
    k2.metric("Última atualização", fetched_at.strftime("%d/%m/%Y %H:%M"))

    st.markdown("---")
    st.markdown(
        "**Use o menu lateral** para acessar as duas lentes de forecast:\n\n"
        "- 📊 **Potencial Total** — forecast sobre o potencial absoluto de "
        "corridas.\n"
        "- 📉 **Potencial Atualizado (15%)** — forecast sobre 15% do "
        "potencial (curva reavaliada pela base 15%).\n\n"
        "_Cada lente tem seus próprios filtros (Pipeline, Proprietário, "
        "Etapa) na sidebar._"
    )


if __name__ == "__main__":
    main()
