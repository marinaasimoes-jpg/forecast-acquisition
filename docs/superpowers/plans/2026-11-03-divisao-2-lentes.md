# Divisão do Dashboard em 2 Lentes (Total vs 15%) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o `app.py` monolítico (7 abas) num app Streamlit multipage com home leve + 2 páginas de lente (Potencial Total / Potencial 15%), cada uma com filtros próprios na sidebar, compartilhando código via `dashboard.py`.

**Architecture:** Extrair todo código reutilizável de `app.py` para `dashboard.py` (cache, filtros, render, df, CSS). Nova função `render_lente(lente, key_prefix)` orquestra uma lente inteira. Páginas em `pages/` são wrappers de ~6 linhas. `app.py` vira home leve. O Consolidado 15% é reuso puro (as funções já operam sobre qualquer deal dict com `volumes`/`total_linha`). Lógica de negócio (`config`, `fetch_hubspot`, `calc_forecast`, `theme`, `selfcheck`) intocada.

**Tech Stack:** Streamlit (multipage via diretório `pages/`), pandas, plotly. Python 3. Token via env `HUBSPOT_TOKEN` / Streamlit Cloud secret.

## Global Constraints

- **Lint/estilo:** seguir o estilo do `app.py` atual (funções `_render_*`/`_df_*` com `_` inicial, comentários `# ---- seção ----`, docstrings curtas, PT-BR nos textos de UI).
- **Cache:** `@st.cache_data(ttl=900)` definido em `dashboard.py` (módulo), nunca local a uma página. Cinto de segurança `fc_cache_busted` mantido em `get_data()`.
- **Filtros Modelo B:** TODO widget de sidebar usa `key=f"{key_prefix}_..."` — estado totalmente independente entre a página Total (`key_prefix="total"`) e a 15% (`key_prefix="p15"`). Nenhuma chave compartilhada.
- **Lentes:** `lente="total"` usa `neg/ativ/ramp`; `lente="15"` usa `neg_15/ativ_15/ramp_15` (já devolvidos por `get_data()`). Consolidado via `_render_consolidado(<listas da lente>, ...)` — sem nova função de cálculo.
- **`set_page_config`** em CADA arquivo de página (Streamlit exige). `app.py` (home) também.
- **Não alterar:** `config.py`, `fetch_hubspot.py`, `calc_forecast.py`, `theme.py`, `selfcheck.py`, `test_calc.py`.
- **Token:** nunca no fonte. Já respeitado pelo `config._load_hubspot_token()`.
- **Deploy gotcha (memória):** após push no Streamlit Cloud, Reboot do app — o `fc_cache_busted` limpa cache uma vez por sessão para evitar `ValueError` de shape de tupla.

---

## File Structure

| Arquivo | Responsabilidade | Estado |
|---|---|---|
| `dashboard.py` | Camada compartilhada: cache (`get_data`, `_load_*_v2`), helpers (`fmt_int`, `fmt_data`, `mes_label`), `_render_filtros`, `render_lente`, todos `_render_*`, `_df_*`, `_zebra_styler`, `_tabela_principal`, `_incompletos_expander`, `_stacked_bar_consolidado`, `_sort_padrao`, `_filtrar_paralelo`, `aplica_filtros`, `_CSS`, `_linha_total`, `mes_col_is_month`, `_pct_rampa_atual`, `_step_label`. | **NOVO** (movido de `app.py`) |
| `pages/1_Potencial_Total.py` | Wrapper fino: `set_page_config` + `_CSS` + `render_lente("total", "total")`. | **NOVO** |
| `pages/2_Potencial_15.py` | Wrapper fino: `set_page_config` + `_CSS` + `render_lente("15", "p15")`. | **NOVO** |
| `app.py` | Home leve: `set_page_config` + `_CSS` + título + caption + 1 KPI + orientação. | **REESCRITO** (home leve) |
| `config.py` / `fetch_hubspot.py` / `calc_forecast.py` / `theme.py` / `selfcheck.py` / `test_calc.py` | Lógica de negócio. | **INALTERADOS** |

**Assinaturas-chave consumidas do código existente (NÃO redefinir):**
- `cf.calcular_todos(deals, hoje=None)` → `(negociacao, ativacao, rampagem, incompletos, meses)` (calc_forecast.py:355).
- `cf._calc_negociacao_15_safe(neg, meses, hoje)` → lista de deals 15% com `potencial_15`, `volumes`, `total_linha`, `potencial` (original).
- `cf._calc_ativacao_15_safe(ativ, meses, hoje)`, `cf._calc_rampagem_15_safe(ramp, meses, hoje)` — análogos.
- `fh.fetch_deals(log=, modified_since=, hoje_date=)` → `(deals, owners, fetched_at)`.
- `sc.run(neg, ativ, ramp, inc, meses, fetched_deals, hoje)` → lista de `(cid, status, msg, deals_inv)`; `sc.summary(checks)` → str.
- Cada deal dict tem: `deal_id`, `dealname`, `pipeline_label`, `owner_name`, `step`, `potencial`, `total_linha`, `volumes` (dict mês→float), `atrasado`, `origem`, `dias_ativacao` (Ativação), `data_ativacao` (Rampagem).
- `_render_consolidado(neg_sel, ativ_sel, ramp_sel, meses, dark)` (app.py:432) — agnóstica à lente.
- `_stacked_bar_consolidado(neg_sel, ativ_sel, ramp_sel, meses)` (app.py:846) — agnóstica à lente.

---

## Task 1: Criar `dashboard.py` com código migrado de `app.py`

**Objetivo:** Mover todo código reutilizável de `app.py` para `dashboard.py`, **sem** ainda adicionar `render_lente`/`_render_filtros` (essas vêm na Task 2). Ao fim desta task, `dashboard.py` é uma cópia fiel das funções de `app.py` (linhas 37-870) importáveis, mas `app.py` ainda funciona como antes (não o tocamos aqui).

**Files:**
- Create: `dashboard.py`

**Interfaces:**
- Consumes: `config`, `fetch_hubspot as fh`, `calc_forecast as cf`, `selfcheck as sc`, `theme`, `streamlit as st`, `pandas as pd`, `numpy as np`, `plotly.graph_objects as go`, `datetime as dt`.
- Produces: módulo `dashboard` com `_load_full_v2`, `_load_incremental_v2`, `get_data`, `fmt_int`, `fmt_data`, `mes_label`, `_render_negociacao`, `_render_negociacao_15`, `_render_ativacao`, `_render_ativacao_15`, `_render_rampagem`, `_render_rampagem_15`, `_render_consolidado`, `_filtrar_paralelo`, `_df_negociacao`, `_df_negociacao_15`, `_df_ativacao`, `_df_ativacao_15`, `_df_rampagem`, `_df_rampagem_15`, `_pct_rampa_atual`, `_step_label`, `_linha_total`, `mes_col_is_month`, `_zebra_styler`, `_tabela_principal`, `_incompletos_expander`, `_stacked_bar_consolidado`, `_sort_padrao`, `_CSS`.

- [ ] **Step 1: Criar `dashboard.py` com o cabeçalho e imports**

Crie `dashboard.py` com este conteúdo inicial (header + imports + helpers, copiados de `app.py:1-58`):

```python
# -*- coding: utf-8 -*-
"""Camada compartilhada do Monthly Commercial Planning — UI + cache.

Movido de app.py na refatoração multipage (2026-11-03). As páginas em
pages/1_Potencial_Total.py e pages/2_Potencial_15.py chamam render_lente();
app.py virou uma home leve.

Três camadas independentes (spec 4.1): coleta (fetch_hubspot) → cálculo
(calc_forecast) → renderização (aqui). Filtros/ordenação só mexem aqui.
"""
import datetime as dt

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import fetch_hubspot as fh
import calc_forecast as cf
import selfcheck as sc
import theme


def fmt_int(n):
    if n is None or (isinstance(n, float) and n != n):
        return "–"
    try:
        return f"{int(round(n)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "–"


def fmt_data(d):
    if d is None:
        return "–"
    if isinstance(d, dt.datetime):
        d = d.date()
    return d.strftime("%d/%m/%Y")


def mes_label(m):
    """out/26, nov/26..."""
    nomes = ["jan", "fev", "mar", "abr", "mai", "jun",
             "jul", "ago", "set", "out", "nov", "dez"]
    return f"{nomes[m.month - 1]}/{str(m.year)[-2:]}"
```

- [ ] **Step 2: Acrescentar o bloco de cache (de `app.py:61-100`)**

Cole ao final de `dashboard.py`:

```python
# ---- camadas 1+2 (cache) -------------------------------------------------
# Funções nomeadas _v2 p/ invalidar caches obsoletos do deploy anterior: a
# chave do st.cache_data inclui a identidade da função, então renomear busta
# qualquer entrada antiga (o deploy pré-v2 cacheava um 6-tupla; o novo código
# devolve 11 — desempacotar 11 de 6 levantava ValueError no Cloud).
@st.cache_data(ttl=900, show_spinner=False)
def _load_full_v2():
    """Carga COMPLETA: fetch + cálculo. Cache de 15 min."""
    deals, owners, fetched_at = fh.fetch_deals(log=lambda *a, **k: None)
    hoje = dt.date.today()
    neg, ativ, ramp, inc, meses = cf.calcular_todos(deals, hoje=hoje)
    neg_15 = cf._calc_negociacao_15_safe(neg, meses, hoje)
    ativ_15 = cf._calc_ativacao_15_safe(ativ, meses, hoje)
    ramp_15 = cf._calc_rampagem_15_safe(ramp, meses, hoje)
    return neg, ativ, ramp, inc, meses, fetched_at, hoje, deals, neg_15, ativ_15, ramp_15


@st.cache_data(ttl=900, show_spinner=False)
def _load_incremental_v2(last_fetched_iso):
    """Carga incremental: só deals modificados desde last_fetched, mesclados.
    Na prática, para simplicidade e robustez (conjunto pequeno), faz um refresh
    leve mas confirma elegíveis (remove quem saiu de 4/5/6/7). Spec 4.4."""
    deals, owners, fetched_at = fh.fetch_deals(log=lambda *a, **k: None)
    hoje = dt.date.today()
    neg, ativ, ramp, inc, meses = cf.calcular_todos(deals, hoje=hoje)
    neg_15 = cf._calc_negociacao_15_safe(neg, meses, hoje)
    ativ_15 = cf._calc_ativacao_15_safe(ativ, meses, hoje)
    ramp_15 = cf._calc_rampagem_15_safe(ramp, meses, hoje)
    return neg, ativ, ramp, inc, meses, fetched_at, hoje, deals, neg_15, ativ_15, ramp_15


def get_data():
    """Garante a base no session_state; default = carga completa.
    Limpa o cache uma vez por sessão (cinto de segurança p/ mudança de shape)."""
    if not st.session_state.get("fc_cache_busted"):
        st.cache_data.clear()
        st.session_state.fc_cache_busted = True
    if "fc_data" not in st.session_state:
        st.session_state.fc_data = _load_full_v2()
    return st.session_state.fc_data
```

- [ ] **Step 3: Acrescentar `_sort_padrao`, `_filtrar_paralelo`, `aplica_filtros`**

Cole ao final de `dashboard.py`. Observação: `aplica_filtros` aqui é uma versão que recebe `f_pipe`/`f_owner` como parâmetro (hoje é um closure dentro de `main()`); isso é necessário porque em `render_lente` os filtros vêm de `_render_filtros`, não de um closure.

```python
def _sort_padrao(sel):
    """Ordenação padrão (quando nada clicado): pipeline > etapa (6,5,4) >
    fechamento. Espelha app.py:231."""
    sel.sort(key=lambda d: (
        d.get("pipeline_label", ""),
        -(d.get("step") or 0),
        d.get("previsao_fechamento") or dt.date(9999, 12, 31),
    ))


def _filtrar_paralelo(lista_paralela, lista_filtrada):
    """Filtra `lista_paralela` (neg_15) mantendo só os deals cujo deal_id está
    em `lista_filtrada` (neg_sel), preservando a ordem de lista_paralela."""
    ids = {d["deal_id"] for d in lista_filtrada}
    return [d for d in lista_paralela if d["deal_id"] in ids]


def aplica_filtros(lista, f_pipe, f_owner):
    """Aplica filtros de pipeline e proprietário sobre `lista`.
    f_pipe/f_owner: listas de labels selecionados (vazio = sem filtro)."""
    sel = list(lista)
    if f_pipe:
        sel = [d for d in sel if d["pipeline_label"] in f_pipe]
    if f_owner:
        sel = [d for d in sel if d["owner_name"] in f_owner]
    return sel
```

- [ ] **Step 4: Copiar TODAS as funções `_render_*` e `_df_*` e helpers de `app.py`**

Abra `app.py` e copie, **verbatim** (sem alterar uma linha), estas funções para o final de `dashboard.py`:

- `_render_negociacao` (app.py:238)
- `_render_negociacao_15` (app.py:272)
- `_render_ativacao` (app.py:306)
- `_render_ativacao_15` (app.py:333)
- `_render_rampagem` (app.py:373)
- `_render_rampagem_15` (app.py:401)
- `_render_consolidado` (app.py:432)
- `_df_negociacao` (app.py:473)
- `_df_negociacao_15` (app.py:504)
- `_df_ativacao` (app.py:541)
- `_df_ativacao_15` (app.py:572)
- `_df_rampagem` (app.py:612)
- `_df_rampagem_15` (app.py:643)
- `_pct_rampa_atual` (app.py:675)
- `_step_label` (app.py:683)
- `_linha_total` (app.py:689)
- `mes_col_is_month` (app.py:713)
- `_zebra_styler` (app.py:723)
- `_tabela_principal` (app.py:739)
- `_incompletos_expander` (app.py:819)
- `_stacked_bar_consolidado` (app.py:846)
- `_CSS` (app.py:873)

Copie o corpo de cada função exatamente como está — incluindo comentários `# ---- seção ----` acima de cada bloco se houver. Não renomeie nada.

- [ ] **Step 5: Verificar que `dashboard.py` importa sem erro**

Run: `python -c "import dashboard; print('ok', hasattr(dashboard, 'get_data'), hasattr(dashboard, '_render_consolidado'))"`
Expected: `ok True True`

Se der `ModuleNotFoundError: streamlit` no ambiente local, alternativa: `python -c "import ast; ast.parse(open('dashboard.py', encoding='utf-8').read()); print('syntax ok')"` → `syntax ok`.

- [ ] **Step 6: Commit**

```bash
git add dashboard.py
git commit -m "refactor: criar dashboard.py com código migrado de app.py

Move cache (get_data, _load_*_v2), helpers (fmt_int, fmt_data, mes_label),
render (_render_*), dataframes (_df_*), tabela/visual (_zebra_styler,
_tabela_principal, _stacked_bar_consolidado, _CSS) de app.py para
dashboard.py. Versão de aplica_filtros recebe f_pipe/f_owner como params
(necessário para render_lente). app.py ainda intocado nesta task.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Adicionar `_render_filtros` e `render_lente` em `dashboard.py`

**Objetivo:** Criar as duas funções novas que orquestram uma lente inteira. `_render_filtros` é o bloco de sidebar parametrizado por `key_prefix`; `render_lente` é o equivalente ao corpo de `main()` (linhas 117-228) parametrizado por `lente`.

**Files:**
- Modify: `dashboard.py` (acrescentar ao final)

**Interfaces:**
- Consumes: `get_data()` (Task 1), `aplica_filtros`, `_filtrar_paralelo`, `_sort_padrao`, `_render_negociacao`, `_render_negociacao_15`, `_render_ativacao`, `_render_ativacao_15`, `_render_rampagem`, `_render_rampagem_15`, `_render_consolidado` (Task 1), `sc.run`, `sc.summary`, `config.PROP_POTENCIAL_LABEL`.
- Produces: `_render_filtros(key_prefix, todos_deals, todos_owners, todos_pipes, todos_steps, fetched_at)` → `(f_pipe, f_owner, f_step, dark, agrupar)`; `render_lente(lente, key_prefix)` (sem retorno; renderiza a página toda).

- [ ] **Step 1: Acrescentar `_render_filtros` ao final de `dashboard.py`**

Esta função extrai o bloco `with st.sidebar:` de `main()` (app.py:138-161), com TODO widget usando `key=f"{key_prefix}_..."`. Devolve os filtros + dark/agrupar.

```python
def _render_filtros(key_prefix, todos_deals, todos_owners, todos_pipes,
                    todos_steps, fetched_at):
    """Sidebar de filtros + botões + checkboxes, parametrizada por key_prefix.

    Modelo B: cada página de lente chama com key_prefix distinto ("total" /
    "p15") → estado de widget totalmente independente entre as duas lentes.

    Retorna (f_pipe, f_owner, f_step, dark, agrupar).
    """
    with st.sidebar:
        st.header("Filtros")
        f_pipe = st.multiselect("Pipeline", todos_pipes,
                                key=f"{key_prefix}_pipe")
        f_owner = st.multiselect("Proprietário", todos_owners,
                                 key=f"{key_prefix}_owner")
        f_step = st.multiselect("Etapa (só Negociação)",
                                [f"Etapa {s}" for s in todos_steps],
                                key=f"{key_prefix}_step")
        if st.button("🧹 Limpar filtros", key=f"{key_prefix}_limpar"):
            for k in (f"{key_prefix}_pipe", f"{key_prefix}_owner",
                      f"{key_prefix}_step"):
                st.session_state.pop(k, None)
            st.rerun()
        st.divider()
        col_btn1, col_btn2 = st.columns(2)
        if col_btn1.button("🔄 Atualizar agora",
                           help="Atualização incremental (spec 4.4)",
                           key=f"{key_prefix}_atualizar"):
            st.session_state.fc_data = _load_incremental_v2(fetched_at.isoformat())
            st.rerun()
        if col_btn2.button("♻️ Recarregar tudo", help="Carga completa",
                           key=f"{key_prefix}_recarregar"):
            st.cache_data.clear()
            st.session_state.pop("fc_data", None)
            st.rerun()
        st.divider()
        agrupar = st.checkbox(
            "Agrupar por pipeline", value=False,
            help="Quando desligado (padrão), a ordenação por clique é global.",
            key=f"{key_prefix}_agrupar")
        dark = st.checkbox("Modo escuro", value=False,
                           key=f"{key_prefix}_dark")
    return f_pipe, f_owner, f_step, dark, agrupar
```

- [ ] **Step 2: Acrescentar `render_lente` ao final de `dashboard.py`**

Esta função espelha o corpo de `main()` (app.py:117-228), parametrizado por `lente`. Seleciona as listas certas conforme a lente e renderiza 4 abas (3 categorias + Consolidado).

```python
def render_lente(lente, key_prefix):
    """Renderiza uma lente inteira (Total ou 15%).

    lente: "total" → usa neg/ativ/ramp + _render_consolidado(total).
           "15"   → usa neg_15/ativ_15/ramp_15 + _render_consolidado(15)
                    (reuso puro — _render_consolidado é agnóstica à lente).
    key_prefix: prefixo das chaves de widget ("total" / "p15") — Modelo B,
                estado de filtro independente entre as duas páginas.
    """
    if lente not in ("total", "15"):
        raise ValueError(f"lente deve ser 'total' ou '15', veio {lente!r}")

    neg, ativ, ramp, inc, meses, fetched_at, hoje, fetched_deals, \
        neg_15, ativ_15, ramp_15 = get_data()

    # ---- self-check (spec 5) ---- roda antes de exibir
    checks = sc.run(neg, ativ, ramp, inc, meses, fetched_deals, hoje)
    st.markdown(f"**Verificação:** {sc.summary(checks)}")
    with st.expander("Verificação dos dados (detalhado)", expanded=False):
        for cid, status, msg, deals_inv in checks:
            icon = "✓" if status == "ok" else "⚠"
            st.markdown(f"- **{icon}** [{cid}] {msg}" +
                        (f"  \n  _Deals:_ {', '.join(d['dealname'] for d in deals_inv[:5])}"
                         + (f" … (+{len(deals_inv)-5})" if len(deals_inv) > 5 else "")
                         if deals_inv else ""))

    # ---- filtros (spec A) — só camada 3, sobre o cache ----
    todos_deals = neg + ativ + ramp
    todos_owners = sorted({d["owner_name"] for d in todos_deals
                           if d["owner_name"] != "(sem proprietário)"})
    todos_pipes = sorted({d["pipeline_label"] for d in todos_deals})
    todos_steps = sorted({d["step"] for d in neg if d["step"]})

    f_pipe, f_owner, f_step, dark, agrupar = _render_filtros(
        key_prefix, todos_deals, todos_owners, todos_pipes, todos_steps,
        fetched_at)

    # ---- seleciona as listas da lente ----
    if lente == "total":
        L_neg, L_ativ, L_ramp = neg, ativ, ramp
    else:  # lente == "15"
        L_neg, L_ativ, L_ramp = neg_15, ativ_15, ramp_15

    # ---- aplica filtros (igual ao main atual) ----
    neg_sel_base = aplica_filtros(neg, f_pipe, f_owner)
    if f_step:
        nums = [int(s.split()[-1]) for s in f_step]
        neg_sel_base = [d for d in neg_sel_base if d["step"] in nums]
    ativ_sel_base = aplica_filtros(ativ, f_pipe, f_owner)
    ramp_sel_base = aplica_filtros(ramp, f_pipe, f_owner)

    # A lente 15% espelha os mesmos deals filtrados da lente total
    # (mesmos deal_ids sob os filtros), via _filtrar_paralelo.
    if lente == "total":
        neg_sel, ativ_sel, ramp_sel = neg_sel_base, ativ_sel_base, ramp_sel_base
    else:
        neg_sel = _filtrar_paralelo(neg_15, neg_sel_base)
        ativ_sel = _filtrar_paralelo(ativ_15, ativ_sel_base)
        ramp_sel = _filtrar_paralelo(ramp_15, ramp_sel_base)

    _sort_padrao(neg_sel)
    _sort_padrao(ativ_sel)
    _sort_padrao(ramp_sel)

    # ---- abas: 4 (3 categorias da lente + Consolidado) ----
    if lente == "total":
        nomes = ["Negociação", "Ativação", "Rampagem", "Consolidado"]
    else:
        nomes = ["Negociação 15%", "Ativação 15%", "Rampagem 15%",
                 "Consolidado 15%"]
    tab_neg, tab_ativ, tab_ramp, tab_cons = st.tabs(nomes)

    with tab_neg:
        if lente == "total":
            _render_negociacao(neg_sel, inc, meses, fetched_at, dark, agrupar)
        else:
            _render_negociacao_15(neg_sel, inc, meses, fetched_at, dark, agrupar)
    with tab_ativ:
        if lente == "total":
            _render_ativacao(ativ_sel, inc, meses, fetched_at, dark, agrupar)
        else:
            _render_ativacao_15(ativ_sel, inc, meses, fetched_at, dark, agrupar)
    with tab_ramp:
        if lente == "total":
            _render_rampagem(ramp_sel, inc, meses, fetched_at, dark, agrupar)
        else:
            _render_rampagem_15(ramp_sel, inc, meses, fetched_at, dark, agrupar)
    with tab_cons:
        # _render_consolidado é agnóstica à lente: opera sobre volumes/
        # total_linha, que existem nos dicts 15% no mesmo formato.
        _render_consolidado(neg_sel, ativ_sel, ramp_sel, meses, dark)

    base_15 = " (forecast sobre 15% do potencial)" if lente == "15" else ""
    st.caption(
        f"Fonte: HubSpot (pipelines B2B Outbound/Website Table/CSM Acquisition). "
        f"Potencial: `{config.PROP_POTENCIAL_LABEL}`{base_15}. "
        f"Negociação: ativação = fechamento + 5 dias úteis (feriados BR). "
        f"Ativação: rampa desde o fechamento real (`closedate`). "
        f"Rampagem: rampa desde a entrada no stage RAMP UP (`hs_v2_date_entered_*`). "
        f"Curva <20k: 25/50/100 · ≥20k: 25/50/75/100. "
        f"Probabilidade 100% (não pondera etapa). "
        f"Última atualização: {fetched_at.strftime('%d/%m/%Y %H:%M')}."
    )
```

- [ ] **Step 3: Verificar sintaxe**

Run: `python -c "import ast; ast.parse(open('dashboard.py', encoding='utf-8').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 4: Commit**

```bash
git add dashboard.py
git commit -m "feat: _render_filtros (sidebar prefixada) + render_lente em dashboard.py

_render_filtros: bloco de sidebar parametrizado por key_prefix — TODO widget
usa chave prefixada (Modelo B: estado independente entre Total e 15%).
render_lente(lente, key_prefix): orquestra uma lente inteira — get_data,
selfcheck, filtros, aplica_filtros, _sort_padrao, e 4 abas (3 categorias
da lente + Consolidado). Consolidado 15% é reuso (_render_consolidado
agnóstica à lente).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Criar as 2 páginas em `pages/`

**Objetivo:** Criar os wrappers finos que o Streamlit multipage usa como entradas no menu lateral.

**Files:**
- Create: `pages/1_Potencial_Total.py`
- Create: `pages/2_Potencial_15.py`

**Interfaces:**
- Consumes: `dashboard.render_lente`, `dashboard._CSS` (Task 2, Task 1).
- Produces: duas páginas navegáveis no menu lateral do Streamlit.

- [ ] **Step 1: Criar `pages/1_Potencial_Total.py`**

```python
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
```

- [ ] **Step 2: Criar `pages/2_Potencial_15.py`**

```python
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
```

- [ ] **Step 3: Verificar sintaxe dos dois arquivos**

Run: `python -c "import ast; ast.parse(open('pages/1_Potencial_Total.py', encoding='utf-8').read()); ast.parse(open('pages/2_Potencial_15.py', encoding='utf-8').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 4: Commit**

```bash
git add pages/1_Potencial_Total.py pages/2_Potencial_15.py
git commit -m "feat: pages/1_Potencial_Total + pages/2_Potencial_15 (wrappers finos)

Duas entradas do menu lateral (multipage). Cada uma chama
dashboard.render_lente com sua lente e key_prefix próprio. Filtros
independentes entre as duas (Modelo B).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Reescrever `app.py` como home leve

**Objetivo:** Transformar `app.py` (hoje monolito com `main()`) numa home leve: logo + caption + 1 KPI + orientação. Sem filtros na sidebar da home (Modelo B). Ao fim, o `main()` monolítico e as funções duplicadas (que já foram pra `dashboard.py`) somem de `app.py`.

**Files:**
- Modify (reescrever): `app.py`

**Interfaces:**
- Consumes: `dashboard.get_data`, `dashboard._CSS`, `dashboard.fmt_int` (Tasks 1-2).
- Produces: `app.py` = home leve (página raiz do multipage).

- [ ] **Step 1: Reescrever `app.py` por inteiro**

Substitua TODO o conteúdo de `app.py` por:

```python
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
```

- [ ] **Step 2: Verificar sintaxe**

Run: `python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 3: Verificar que `app.py` não referenceia funções que sumiram**

Run (procura por resquícios do monolito): use a ferramenta de busca por `def main` em `app.py` — deve haver exatamente uma ocorrência (a nova). E procure por `_render_negociacao` em `app.py` — deve retornar **zero** ocorrências (essas funções agora só existem em `dashboard.py`).

Expected: `def main` aparece 1×; `_render_negociacao` aparece 0× em `app.py`.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "refactor: app.py vira home leve (multipage raiz)

Remove o main() monolítico (código já migrado p/ dashboard.py em tasks 1-2).
Home leve: set_page_config + CSS + título/caption + 2 KPIs (deals em pipeline,
última atualização) + orientação para as 2 lentes. Sem filtros na sidebar
(Modelo B: filtros são por página de lente).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Smoke test manual + ajustes do selfcheck/caption

**Objetivo:** Rodar o app localmente (ou ao menos validar o que dá sem token), rodar os testes existentes e o selfcheck, e confirmar que a estrutura multipage funciona. Esta task não tem código novo de produção — é verificação e ajuste fino.

**Files:**
- Possivelmente adjust: `dashboard.py` (se o smoke test revelar algo), `selfcheck.py` (só se um check quebrar com a nova estrutura — não esperado).

- [ ] **Step 1: Rodar os testes de cálculo (não dependem de token/Streamlit)**

Run: `python -m pytest test_calc.py -q`
Expected: todos passam (a lógica de cálculo não foi tocada).

Se algum teste quebrar, **parar** — significa que a migração alterou algo além da apresentação. Revisar `dashboard.py` contra `app.py` original.

- [ ] **Step 2: Rodar o selfcheck (pode depender de token)**

Run: `python selfcheck.py`
Expected: roda e reporta os checks. Se `HUBSPOT_TOKEN` não estiver no env local, esperado: erro de token (não é falha da refatoração — é ambiente). Nesse caso, anotar e seguir para o Step 3 (que valida a estrutura sem precisar do HubSpot).

- [ ] **Step 3: Validar a estrutura multipage sem token (import smoke)**

Run:
```bash
python -c "
import ast
for f in ['app.py', 'dashboard.py', 'pages/1_Potencial_Total.py', 'pages/2_Potencial_15.py']:
    ast.parse(open(f, encoding='utf-8').read())
    print(f, 'syntax ok')
"
```
Expected: 4× `syntax ok`.

Depois, rodar `streamlit run app.py` (mesmo sem token) e confirmar:
- A home carrega com título, caption e os 2 KPIs (ou erro de token, se não houver token — mas a **estrutura** da página deve renderizar até o ponto do `get_data()`).
- O menu lateral mostra as 3 entradas: `Monthly Commercial Planning` (home), `1_Potencial_Total`, `2_Potencial_15`.

- [ ] **Step 4: Smoke test com token (se disponível localmente)**

Se `HUBSPOT_TOKEN` estiver no env: rodar `streamlit run app.py` e validar manualmente:
- Home mostra o total de deals e a última atualização.
- Página **Potencial Total**: 4 abas (Negociação, Ativação, Rampagem, Consolidado) com tabelas e TOTAL 6M. Filtros funcionam. Botão "Limpar filtros" funciona.
- Página **Potencial 15%**: 4 abas (15%) + Consolidado 15%. **Crítico:** os números do Consolidado 15% devem ser coerentes com a soma das 3 categorias 15% (≈ 15% do total, reavaliado por faixa).
- **Modelo B:** filtrar Pipeline = "B2B Outbound" na página Total, ir para a página 15% — o filtro **não** deve estar aplicado lá (filtros independentes).

- [ ] **Step 5: Ajustar o caption da home ou das lentes se necessário**

Se o smoke test revelar texto desatualizado (ex.: a home ainda menciona "7 abas"), ajustar em `app.py` ou `dashboard.render_lente`. Como o design já previu o caption correto, esperado: sem ajuste. Se ajustar, commit junto com a validação.

- [ ] **Step 6: Commit final da fase (se houve ajustes)**

Se houve ajustes em `dashboard.py` ou `app.py` no Step 5:

```bash
git add -A
git commit -m "fix: ajustes pós smoke test da refatoração multipage

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Se não houve ajustes, esta task não produz commit — apenas validação. Anotar no handoff que o smoke test passou.

---

## Notas de deploy (Fase 1 pronta para ir ao ar)

- **Ordem de push:** todas as tasks juntas num push (ou PR). O Streamlit Cloud detecta o multipage automaticamente pelo diretório `pages/`.
- **Reboot:** após o deploy, **Reboot** do app no Streamlit Cloud (Settings → Reboot). O `fc_cache_busted` em `get_data()` limpa o cache obsoleto uma vez por sessão, evitando o `ValueError` de desempacotar tupla de tamanho errado (memória do projeto: esse erro já aconteceu em deploy anterior).
- **URLs:** a home fica na URL raiz; as lentes em `/Potencial_Total` e `/Potencial_15` (Streamlit deriva o slug do nome do arquivo, ignorando o prefixo numérico).
