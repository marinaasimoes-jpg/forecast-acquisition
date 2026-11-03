# Design — Divisão do dashboard em 2 lentes (Potencial Total vs 15%)

**Data:** 2026-11-03
**Autor:** brainstorm Marina + Claude
**Fase:** 1 de 2 (divisão em 2 dashboards). Fase 2 = meta vs. performance (separada).

## Contexto

O dashboard *Monthly Commercial Planning* é hoje um `app.py` monolítico (~870
linhas) com 7 abas numa única página:

1. Negociação (potencial total)
2. Negociação Potencial Atualizado (15%)
3. Ativação (total)
4. Ativação 15%
5. Rampagem (total)
6. Rampagem 15%
7. Consolidado (soma das 3 categorias — **só sobre potencial total hoje**)

A Marina quer **dividir em 2 dashboards**: um com o potencial total, outro com
os 15% do potencial. Cada um deve ter suas próprias categorias
(Negociação/Ativação/Rampagem) + seu próprio consolidado.

A divisão em 2 é a **Fase 1**. A **Fase 2** (separada, outro spec) trará a
acompanhamento de meta vs. performance real de corridas — que exige descobrir
a base transacional de corridas realizadas e fazer match por ID de empresa.
Esta fase **não** toca nisso.

## Decisões de design (validadas com a Marina)

1. **UX: Multipage do Streamlit** — 2 entradas no menu lateral, sensação de 2
   dashboards distintos, 1 codebase/1 deploy. (Alternativas descartadas:
   seletor no mesmo app; 2 apps Cloud separados.)
2. **Filtros: Modelo B** — cada página de lente tem SEUS próprios filtros
   (Pipeline/Proprietário/Etapa) e botões (Atualizar/Recarregar) na sidebar.
   Filtros independentes entre as duas lentes. Home é leve.
   (Modelo A — filtros globais via session_state — descartado pela Marina.)
3. **Implementação: Abordagem 1** — módulo `dashboard.py` compartilhado +
   páginas finas que chamam `render_lente(lente, key_prefix)`. Código escrito
   uma vez, filtros independentes por chave prefixada.
   (Abordagem 2 — lib mínima + páginas gordas com filtros duplicados —
   descartada pelo risco de drift recorrente.)

## Descoberta chave que simplifica o design

`_render_consolidado` e `_stacked_bar_consolidado` (em `app.py`) só somam
`d["total_linha"]` e `d["volumes"].get(m, 0)`. Os deal dicts de 15%
(`neg_15`, `ativ_15`, `ramp_15` — produzidos por `calcular_*_15` em
`calc_forecast.py`) carregam `volumes` e `total_linha` **no mesmo formato**,
só baseados em `potencial_15 = round(potencial × 0.15)`.

**Consequência:** essas funções são agnósticas à lente. Passar as listas de
15% produz o Consolidado 15% **sem código novo de cálculo**. A separação por
lente é 100% apresentação/navegação.

## Estrutura de arquivos (após)

```
app.py                      → home leve (logo, caption, 1 KPI, orientação)
pages/1_Potencial_Total.py  → lente "Total":   Negociação · Ativação · Rampagem · Consolidado
pages/2_Potencial_15.py     → lente "15%":     Negociação 15% · Ativação 15% · Rampagem 15% · Consolidado 15%
dashboard.py                → compartilhado: cache, filtros, render, df, CSS, render_lente()
```

**Inalterados:** `config.py`, `fetch_hubspot.py`, `calc_forecast.py`,
`theme.py`, `selfcheck.py`, `test_calc.py`. Toda a lógica de negócio (curva,
proporcionalidade, proxy `closedate`, `hs_v2_date_entered_*`) fica intocada.

## `dashboard.py` — camada compartilhada (movido de `app.py`)

Migrar de `app.py` para `dashboard.py`:

- **Cache:** `_load_full_v2`, `_load_incremental_v2`, `get_data()` (mantém o
  `fc_cache_busted` — cinto de segurança contra `ValueError` de shape).
- **Helpers:** `fmt_int`, `fmt_data`, `mes_label`.
- **Render:** `_render_negociacao`, `_render_negociacao_15`, `_render_ativacao`,
  `_render_ativacao_15`, `_render_rampagem`, `_render_rampagem_15`,
  `_render_consolidado`.
- **DataFrames:** `_df_negociacao`, `_df_negociacao_15`, `_df_ativacao`,
  `_df_ativacao_15`, `_df_rampagem`, `_df_rampagem_15`.
- **Tabela/visual:** `_zebra_styler`, `_tabela_principal`, `_incompletos_expander`,
  `_stacked_bar_consolidado`, `_sort_padrao`, `_filtrar_paralelo`,
  `aplica_filtros`, `_CSS`, `_linha_total`, `mes_col_is_month`, `_pct_rampa_atual`,
  `_step_label`.

### Nova função: `_render_filtros(key_prefix, ...)`

Extrai o bloco de sidebar de `main()` (linhas ~138-161) numa função. **Todo**
widget usa chave prefixada: `f"{key_prefix}_pipe"`, `f"{key_prefix}_owner"`,
`f"{key_prefix}_step"`, botões Atualizar/Recarregar, e os checkboxes dark e
agrupar (`f"{key_prefix}_dark"`, `f"{key_prefix}_agrupar"`). Devolve
`(f_pipe, f_owner, f_step, dark, agrupar)`.

Resultado: página Total e 15% têm **estado totalmente independente** (Modelo B)
— filtros, modo escuro e agrupamento por pipeline não se propagam entre as
duas lentes — sem duplicar código de widget.

**Nota:** hoje os checkboxes usam chaves sem prefixo (`st.session_state.fc_dark`,
`st.session_state.fc_agrupar`) e `main()` lê de volta. Na refatoração, isso
passa a ser local a `render_lente` (lê do retorno de `_render_filtros`), sem
depender de `session_state` global — mais limpo e alinhado ao Modelo B.

### Nova função orquestradora: `render_lente(lente, key_prefix)`

```python
def render_lente(lente: str, key_prefix: str):
    """lente ∈ {'total', '15'}. Monta filtros (Modelo B), carrega dado,
    aplica filtros, ordena, e renderiza as 4 abas daquela lente + consolidado."""
```

Espelha o corpo de `main()` (linhas ~117-228), parametrizado pela lente:

- `get_data()` → desempacota `neg, ativ, ramp, inc, meses, fetched_at, hoje,
  fetched_deals, neg_15, ativ_15, ramp_15`.
- `selfcheck.run(...)` roda antes das abas (como hoje) — em ambas as lentes.
- Seleciona as listas certas conforme a lente:
  - `lente="total"`: `neg/ativ/ramp` + `_render_consolidado(neg_sel, ativ_sel, ramp_sel, ...)`.
  - `lente="15"`: `neg_15/ativ_15/ramp_15` + `_render_consolidado(neg_15_sel, ativ_15_sel, ramp_15_sel, ...)`.
- `aplica_filtros` + `_filtrar_paralelo` + `_sort_padrao` como hoje.
- `st.tabs` com 4 abas (não 7): as 3 categorias da lente + Consolidado.

### Caption inferior

O caption de fonte (linhas ~219-228) fica dentro de `render_lente`, igual hoje.

## Páginas (wrappers finos)

```python
# pages/1_Potencial_Total.py
import streamlit as st
import dashboard

st.set_page_config(page_title="Potencial Total — Monthly Commercial Planning",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(dashboard._CSS(), unsafe_allow_html=True)
dashboard.render_lente("total", "total")
```

```python
# pages/2_Potencial_15.py
import streamlit as st
import dashboard

st.set_page_config(page_title="Potencial Atualizado (15%) — Monthly Commercial Planning",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(dashboard._CSS(), unsafe_allow_html=True)
dashboard.render_lente("15", "p15")
```

## `app.py` — home leve

`st.set_page_config(page_title="Monthly Commercial Planning", layout="wide",
initial_sidebar_state="expanded")`, `_CSS()`, título, caption (o texto atual
que descreve Negociação/Ativação/Rampagem), 1 KPI (total de deals em pipeline,
via `get_data()`) e orientação: *"Use o menu lateral para acessar Potencial
Total e Potencial Atualizado (15%)."*

A sidebar da home fica vazia de filtros (Modelo B).

## Gotchas conhecidos (da memória do projeto)

- **Reboot no Cloud após mudança de shape:** o `_cache_busted` (limpa cache
  uma vez por sessão) já trata o `ValueError` de desempacotar tupla de tamanho
  errado. Mantido em `get_data()`.
- **`@st.cache_data` em multipage:** o cache é definido em `dashboard.py`
  (módulo importado), não local a cada página → compartilhado entre páginas.
  Cada página chama `get_data()`, que devolve de `session_state["fc_data"]`
  se já carregado. O HubSpot é consultado uma vez por sessão, não por troca
  de página.
- **Prefixo de chave:** as duas páginas usam `key_prefix` distintos
  (`"total"` e `"p15"`) → estado de widget independente. Nenhum widget
  compartilha chave entre páginas.

## Escopo desta fase

- ✅ App multipage com home leve + 2 páginas de lente.
- ✅ Filtros e botões por página (Modelo B), via `_render_filtros` prefixado.
- ✅ `render_lente` orquestradora em `dashboard.py`.
- ✅ Consolidado 15% (reuso de `_render_consolidado`, sem cálculo novo).
- ✅ selfcheck roda em ambas as lentes.

### Fora de escopo (Fase 2 — outro spec)
- ❌ Meta vs. performance real de corridas.
- ❌ Descoberta da base transacional de corridas realizadas.
- ❌ Match por ID de empresa (HubSpot ↔ base de corridas).

## Teste/validação

- `test_calc.py` e `selfcheck.py` seguem intactos (lógica de cálculo não muda).
- Smoke test manual: rodar `streamlit run app.py`, acessar as 3 páginas,
  confirmar filtros independentes (filtrar Pipeline na Total, ir na 15% —
  filtro não propagado) e Consolidado 15% com números coerentes (≈ 15% do
  total, reavaliado por faixa).
- Deploy no Streamlit Cloud: reboot do app após push (cinto de segurança do
  cache).
