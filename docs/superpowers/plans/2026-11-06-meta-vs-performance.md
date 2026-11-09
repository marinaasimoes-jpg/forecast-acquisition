# Acompanhamento meta vs. realizado (tab Rampagem) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar colunas de `% atingimento` + `Realizado` na tab Rampagem (lentes Total e 15%), com expander de histórico por empresa, lendo o realizado da planilha `data/Acompanhamento_Rampagem.xlsx` via novo módulo `fetch_performance.py`.

**Architecture:** Nova camada isolada `fetch_performance.py` (ler planilha + match por nome + exceções) → helper `meta_de_mes_rampagem` em `calc_forecast.py` (meta de qualquer mês) → `_df_rampagem`/`_render_rampagem` em `dashboard.py` ganham as colunas + expander. Planilha commitada em `data/`. Script `atualizar_performance.py` automatiza o push mensal. Lógica existente intocada (forecast, curva, filtros, multipage).

**Tech Stack:** Streamlit, pandas, openpyxl (ler .xlsx), plotly. Python 3. Token HubSpot via env/secret (inalterado).

## Global Constraints

- **Nome real da coluna de empresa:** `"Nome do negócio"` (não "Empresa"). As colunas novas `% atingimento` e `Realizado` vão logo APÓS `"Nome do negócio"`, antes de `"Pipeline"`... espera — revisar: na ordem pedida pela Marina, `%` e `Realizado` vão antes dos meses mas a posição exata (logo após nome vs. após outras colunas) é decisiva. **Decisão:** logo após `"Nome do negócio"`, antes de `"Pipeline"` — fica no início visível da linha. Ver Task 4.
- **Campo de data-base no deal:** `deal["data_ativacao"]` (entrada no RAMP UP — confirmado em `fetch_hubspot.py:190`, `_build_deal` retorna `data_ativacao`). O `_df_rampagem` hoje referencia `d.get("entrada_rampagem")` — verificar se `entrada_rampagem` é alias ou campo separado. **Ação Task 1:** confirmar o nome do campo e usar o mesmo em `meta_de_mes_rampagem`.
- **Curva reusada:** `config.CURVA_RAMPAGEM` + `config.LIMITE_POTENCIAL_ALTO=20000` via `_curva(potencial)` (calc_forecast.py:124). Não redefinir curva.
- **Proporcionalidade M1:** `_fator_proporcional(ativacao)` (calc_forecast.py:130) → `(fator, dias_ativos, dias_no_mes)`. Reusar no helper.
- **Mês corrente = mês mais recente da planilha inteira** (não por empresa, não mês calendário). Mesmo pra todas as empresas; empresa sem registro naquele mês → `–`.
- **Realizado é o mesmo nas duas lentes; % muda** (meta total vs. meta 15). O helper recebe o deal com o potencial da lente (original ou `potencial_15`).
- **Match por nome normalizado + `EXCECOES_MATCH_NOME`** em `config.py`. Sem fuzzy matching.
- **Planilha em `data/Acompanhamento_Rampagem.xlsx`** (path relativo ao repo). Cache `@st.cache_data(ttl=900)` chaveado por path + mtime.
- **Não alterar:** `app.py`, `pages/*`, `fetch_hubspot.py`, `theme.py` (inalterados). `config.py` e `calc_forecast.py` só aditivo. `dashboard.py` modifica `_df_rampagem*`/`_render_rampagem*`. `selfcheck.py`/`test_calc.py` ganham testes.
- **Estilo:** seguir o do `dashboard.py` (funções `_` iniciais, `# ---- seção ----`, PT-BR, `column_config` com `NumberColumn`/`format="%d"`).

---

## File Structure

| Arquivo | Responsabilidade | Estado |
|---|---|---|
| `fetch_performance.py` | Ler `data/Acompanhamento_Rampagem.xlsx`, achar abas `Acompanhamento Linda *`, extrair `(empresa, mês, meta, realizado)`. Match por nome normalizado + `EXCECOES_MATCH_NOME`. Devolve `{deal_id: {mes: {meta, realizado}}}` + `mes_corrente` + lista de deals sem acompanhamento. Cacheado. | **NOVO** |
| `calc_forecast.py` | Adiciona `meta_de_mes_rampagem(deal, mes_alvo)` — meta de qualquer mês desde a entrada, reusando `_curva`/`_fator_proporcional`. Aditivo, sem alterar existentes. | **MODIFICADO (aditivo)** |
| `config.py` | Adiciona `PATH_PLANILHA_PERFORMANCE` e `EXCECOES_MATCH_NOME`. | **MODIFICADO (aditivo)** |
| `dashboard.py` | `_df_rampagem`/`_df_rampagem_15`: colunas `% atingimento` + `Realizado` após "Nome do negócio". `_render_rampagem`/`_render_rampagem_15`: expander histórico por empresa + expander "Deals sem acompanhamento". `column_config` das rampagens ganha as 2 colunas. | **MODIFICADO** |
| `data/Acompanhamento_Rampagem.xlsx` | A planilha copiada do Drive. | **NOVO** |
| `atualizar_performance.py` | Script: `git add data/ + commit + push` num comando. | **NOVO** |
| `test_calc.py` | Teste de `meta_de_mes_rampagem` + smoke de `fetch_performance` (planilha real). | **MODIFICADO (aditivo)** |

**Assinaturas consumidas do código existente (NÃO redefinir):**
- `_curva(potencial)` → lista de fracs (low/high por 20k). calc_forecast.py:124.
- `_fator_proporcional(ativacao)` → `(fator, dias_ativos, dias_no_mes)`. calc_forecast.py:130.
- `deal["data_ativacao"]` → date de entrada no RAMP UP (fetch_hubspot.py:190). `deal["potencial"]` (original), `deal["potencial_15"]` (variante 15), `deal["dealname"]`, `deal["deal_id"]`.
- `_df_rampagem(sel, meses)` (dashboard.py:485), `_df_rampagem_15(sel, meses)` (dashboard.py:516), `_render_rampagem(sel, incompletos, meses, fetched_at, dark, agrupar)`, `_render_rampagem_15(...)`, `_tabela_principal(df, meses, dark, agrupar, aba)`, `_incompletos_expander(incompletos, aba, dark)`.
- `mes_label(m)` → "out/26". `fmt_int(n)` → "1.234" ou "–".

---

## Task 1: `config.py` — path da planilha + tabela de exceções de match

**Objetivo:** Adicionar constantes de configuração (path da planilha + exceções de match nome↔dealname). Aditivo, sem alterar existentes.

**Files:**
- Modify: `config.py` (acrescentar ao final)

**Interfaces:**
- Produces: `config.PATH_PLANILHA_PERFORMANCE` (str), `config.EXCECOES_MATCH_NOME` (dict).

- [ ] **Step 1: Acrescentar ao final de `config.py`**

```python
# ---- Acompanhamento meta vs. realizado (Fase 2) -------------------------
# Planilha com o realizado mensal por empresa (colado manualmente a cada mês,
# uma aba "Acompanhamento Linda MMaaaa" por mês). Commitada no repo em data/
# pra o Streamlit Cloud ter acesso (o Cloud não enxerga o Drive local).
PATH_PLANILHA_PERFORMANCE = "data/Acompanhamento_Rampagem.xlsx"

# Exceções de match: quando o nome na planilha não casa com o dealname do
# HubSpot por normalização textual, mapeia manualmente aqui.
# Chave = nome na planilha (Company Name); valor = dealname no HubSpot.
# Cresce conforme aparecerem "Deals sem acompanhamento" no dashboard.
EXCECOES_MATCH_NOME = {
    "Voetur": "Grupo Voetur",
    # "Dellys": "Dellys Food Service",  # este casa por normalização, não precisa
}
```

- [ ] **Step 2: Verificar import**

Run: `python -c "import config; print(config.PATH_PLANILHA_PERFORMANCE, type(config.EXCECOES_MATCH_NOME))"`
Expected: `data/Acompanhamento_Rampagem.xlsx <class 'dict'>`

- [ ] **Step 3: Commit**

```bash
git add config.py
git commit -m "feat(perf): config — path planilha performance + exceções match nome

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: `calc_forecast.py` — helper `meta_de_mes_rampagem`

**Objetivo:** Adicionar função que calcula a meta de forecast de rampagem para um mês qualquer (dentro ou fora da janela de 6 meses). Reusa `_curva` + `_fator_proporcional`. Aditivo.

**Files:**
- Modify: `calc_forecast.py` (acrescentar após `volume_por_mes_rampagem`, ~linha 346)
- Test: `test_calc.py` (adicionar seção)

**Interfaces:**
- Consumes: `_curva(potencial)`, `_fator_proporcional(ativacao)`, `deal["data_ativacao"]`, `deal["potencial"]`, `config.LIMITE_POTENCIAL_ALTO`, `config.CURVA_RAMPAGEM`.
- Produces: `meta_de_mes_rampagem(deal, mes_alvo)` → `float` (meta sobre o potencial do deal passado).

- [ ] **Step 1: Confirmar nome do campo de data-base no deal**

Run: `python -c "import fetch_hubspot as fh; import inspect; src=inspect.getsource(fh._build_deal); print('data_ativacao' in src, 'entrada_rampagem' in src)"`
Expected: `True False` (confirma que o campo é `data_ativacao`, e `entrada_rampagem` no `_df_rampagem` é calculado em outro lugar — verificar `_render_rampagem`). Anotar pra Task 4.

Se der `True True` ou outro, parar e reportar — significa que o nome do campo mudou; reajustar o helper.

- [ ] **Step 2: Escrever o teste falhando em `test_calc.py`**

Acrescentar ao final de `test_calc.py`:

```python
# ---- meta_de_mes_rampagem (Fase 2: meta de qualquer mês) ----
print("=" * 70)
print("META_DE_MES_RAMPAGEM:")
print("=" * 70)
import calc_forecast as cf
import datetime as dt

# Deal high (potencial >= 20k): curva [0.25, 0.50, 0.75, 1.00]
deal_high = {"deal_id": "t1", "potencial": 30000,
             "data_ativacao": dt.date(2026, 7, 15)}
# M1 = mês da entrada (jul/2026), proporcional por dia.
# entrada 15/7 → dias_ativos = 31-15+1 = 17, dias_no_mes=31 → fator 17/31.
m1 = cf.meta_de_mes_rampagem(deal_high, dt.date(2026, 7, 1))
esperado_m1 = 30000 * 0.25 * (17 / 31)
print(f"  high M1 (jul/26, entrada 15/7): {m1:.1f}  esperado {esperado_m1:.1f}")
assert abs(m1 - esperado_m1) < 1, f"M1 high: {m1} != {esperado_m1}"

# M2 = ago/2026 → 50% de 30000 = 15000 (sem proporcionalidade).
m2 = cf.meta_de_mes_rampagem(deal_high, dt.date(2026, 8, 1))
assert abs(m2 - 15000) < 1, f"M2 high: {m2} != 15000"
print(f"  high M2 (ago/26): {m2:.1f}  esperado 15000")

# M5+ = após a curva (high tem 4 meses) → 100% = 30000.
m5 = cf.meta_de_mes_rampagem(deal_high, dt.date(2026, 12, 1))
assert abs(m5 - 30000) < 1, f"M5+ high: {m5} != 30000"
print(f"  high M5+ (dez/26): {m5:.1f}  esperado 30000")

# Mês ANTES da entrada → meta 0.
m_antes = cf.meta_de_mes_rampagem(deal_high, dt.date(2026, 6, 1))
assert m_antes == 0, f"antes entrada: {m_antes} != 0"
print(f"  high antes entrada (jun/26): {m_antes}  esperado 0")

# Deal low (potencial < 20k): curva [0.25, 0.50, 1.00] (3 meses)
deal_low = {"deal_id": "t2", "potencial": 500,
            "data_ativacao": dt.date(2026, 8, 11)}
# M3 = out/2026 → 100% de 500 = 500.
m3_low = cf.meta_de_mes_rampagem(deal_low, dt.date(2026, 10, 1))
assert abs(m3_low - 500) < 1, f"M3 low: {m3_low} != 500"
print(f"  low M3 (out/26): {m3_low:.1f}  esperado 500")

# Variante 15%: passa deal com potencial_15.
deal_high_15 = {**deal_high, "potencial": 4500}  # 15% de 30000 = 4500
m2_15 = cf.meta_de_mes_rampagem(deal_high_15, dt.date(2026, 8, 1))
assert abs(m2_15 - 2250) < 1, f"M2 15%: {m2_15} != 2250"
print(f"  15% M2 (ago/26, pot=4500): {m2_15:.1f}  esperado 2250")

# Sem potencial ou sem data_ativacao → 0.
assert cf.meta_de_mes_rampagem({"potencial": None, "data_ativacao": dt.date(2026,1,1)}, dt.date(2026,2,1)) == 0
assert cf.meta_de_mes_rampagem({"potencial": 1000, "data_ativacao": None}, dt.date(2026,2,1)) == 0
print("  sem potencial / sem data: 0  OK")
print("  meta_de_mes_rampagem: 8/8 OK\n")
```

- [ ] **Step 3: Rodar o teste — deve falhar**

Run: `PYTHONUTF8=1 python test_calc.py 2>&1 | grep -A3 "META_DE_MES_RAMPAGEM" | head -10`
Expected: erro `AttributeError: module 'calc_forecast' has no attribute 'meta_de_mes_rampagem'` (ou o teste para na primeira asserção).

- [ ] **Step 4: Implementar `meta_de_mes_rampagem` em `calc_forecast.py`**

Acrescentar após `volume_por_mes_rampagem` (depois da linha 345, `return volumes, entrada, detalhes`):

```python
def meta_de_mes_rampagem(deal, mes_alvo):
    """Meta de forecast de rampagem para um mês qualquer (dentro ou fora da
    janela de 6 meses). Reusa _curva + _fator_proporcional.

    mes_alvo: date (primeiro dia do mês). Retorna float (meta sobre o
    potencial do deal passado — potencial total OU potencial_15, conforme a
    lente: a lente 15% passa um deal cujo "potencial" já é o 15%).

    Casos:
    - Sem potencial / sem data_ativacao → 0.
    - mes_alvo anterior ao mês da entrada → 0 (rampa ainda não começou).
    - M1 (mês da entrada) → potencial * curva[0] * fator_proporcional.
    - M2..N dentro da curva → potencial * curva[offset].
    - Após a curva (carry-forward) → potencial * 1.0 (100%).
    """
    potencial = deal.get("potencial")
    entrada = deal.get("data_ativacao")
    if not potencial or potencial <= 0 or not entrada:
        return 0.0

    curva = _curva(potencial)
    mes_m1 = dt.date(entrada.year, entrada.month, 1)
    mes_alvo_pri = dt.date(mes_alvo.year, mes_alvo.month, 1)

    # offset em meses desde a entrada (mes_alvo - mes_m1).
    delta = (mes_alvo_pri.year - mes_m1.year) * 12 + (mes_alvo_pri.month - mes_m1.month)
    if delta < 0:
        return 0.0  # antes da entrada

    if delta < len(curva):
        frac = curva[delta]
        if delta == 0:
            # M1: proporcional por dia (entrada no meio do mês).
            fator_m1, _, _ = _fator_proporcional(entrada)
            return potencial * frac * fator_m1
        return potencial * frac
    # Após a curva: 100% (carry-forward).
    return potencial * 1.0
```

- [ ] **Step 5: Rodar o teste — deve passar**

Run: `PYTHONUTF8=1 python test_calc.py 2>&1 | grep -A2 "meta_de_mes_rampagem:" | tail -3`
Expected: `meta_de_mes_rampagem: 8/8 OK`

- [ ] **Step 6: Commit**

```bash
git add calc_forecast.py test_calc.py
git commit -m "feat(perf): meta_de_mes_rampagem — meta de forecast p/ qualquer mês

Helper isolado (reusa _curva + _fator_proporcional) que calcula a meta de
rampagem de um mês qualquer, dentro ou fora da janela de 6 meses. Necessário
pra comparar meta vs. realizado no mês do acompanhamento (que pode ser
anterior à janela atual). Não altera volume_por_mes_rampagem.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: `fetch_performance.py` — ler planilha + match por nome

**Objetivo:** Criar o módulo isolado que lê a planilha, extrai `(empresa, mês, meta, realizado)`, casa com os deals do HubSpot por nome normalizado + exceções, e devolve a estrutura pro dashboard. Cacheado.

**Files:**
- Create: `fetch_performance.py`
- Create: `data/` (dir) + copiar `Acompanhamento_Rampagem.xlsx` do Drive.
- Test: `test_calc.py` (adicionar seção de smoke)

**Interfaces:**
- Consumes: `config.PATH_PLANILHA_PERFORMANCE`, `config.EXCECOES_MATCH_NOME` (Task 1). `openpyxl`.
- Produces: `ler_performance()` → lista de `{"empresa_planilha", "mes", "meta_planilha", "realizado"}`; `normalizar_nome(s)` → str; `performance_por_deal(deals_rampagem, registros)` → `(por_deal: {deal_id: {mes: {"meta_planilha", "realizado"}}}, mes_corrente: date|None, sem_acompanhamento: [deal])`.

- [ ] **Step 1: Criar `data/` e copiar a planilha**

Criar o diretório `data/` no repo e copiar a planilha do Drive:
```bash
mkdir -p data
cp "../Acompanhamento_Rampagem - FINAL.xlsx" "data/Acompanhamento_Rampagem.xlsx"
ls -la data/
```
Expected: `data/Acompanhamento_Rampagem.xlsx` presente (~244KB).

- [ ] **Step 2: Criar `fetch_performance.py` com cabeçalho + `normalizar_nome` + `ler_performance`**

```python
# -*- coding: utf-8 -*-
"""Camada de coleta do REALIZADO (corridas feitas) — Fase 2.

Lê a planilha data/Acompanhamento_Rampagem.xlsx (uma aba
"Acompanhamento Linda MMaaaa" por mês), extrai por empresa o
(realizado, meta) daquele mês, e casa com os deals do HubSpot por nome
normalizado (+ tabela de exceções em config.EXCECOES_MATCH_NOME).

ISOLADO: quando o plugin Supabase destravar, troca-se este módulo por um
que faz SELECT no Postgres da 99 — o resto do dashboard não muda. Ver
memória performance-fonte-supabase-pendente.
"""
import datetime as dt
import re
import unicodedata

import openpyxl

import config


def normalizar_nome(s):
    """Normaliza nome pra match textual: lowercase, sem acento, sem
    sufixos 'Food Service'/'LTDA'/'Ltda', trim. 'Dellys Food Service' →
    'dellys'."""
    if not s:
        return ""
    s = str(s).strip().lower()
    # remove acentos
    s = "".join(c for c in unicodedata.normalize("NFKD", s)
                if not unicodedata.combining(c))
    # remove sufixos comuns de razão social / nome comercial
    s = re.sub(r"\b(food service|ltda|sa|s/a|limited|comercio|com eireli)\b",
               "", s)
    return re.sub(r"\s+", " ", s).strip()


def _mes_do_nome_aba(nome_aba):
    """'Acompanhamento Linda 082026' → date(2026, 8, 1). None se não casar."""
    m = re.search(r"(\d{2})(\d{4})", nome_aba or "")
    if not m:
        return None
    mm, aaaa = int(m.group(1)), int(m.group(2))
    if mm < 1 or mm > 12:
        return None
    return dt.date(aaaa, mm, 1)


def ler_performance(path=config.PATH_PLANILHA_PERFORMANCE):
    """Lê a planilha, acha abas 'Acompanhamento Linda *', extrai registros.

    Retorna lista de dicts: {"empresa_planilha": str, "mes": date(1º),
    "meta_planilha": float|None, "realizado": float|None}.

    Estrutura esperada da aba (confirmada em 2026-11-03):
      linha1: headers (Owner=col0, Company Name=col1, Activation Date=col2,
              Potential=col3, Forecast=col4.., Actual <Mês>=col10,
              % Achievement=col11..)
      linha2: sub-headers de mês (August/2026 etc.) nas col4..9
      linha3+: dados por empresa
    'Forecast' daquele mês (a meta) está em col4..9 conforme o mês da aba;
    'Actual' (realizado) está em col10.
    """
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    registros = []
    for nome_aba in wb.sheetnames:
        if not nome_aba.lower().startswith("acompanhamento linda"):
            continue
        mes = _mes_do_nome_aba(nome_aba)
        if mes is None:
            continue
        ws = wb[nome_aba]
        rows = list(ws.iter_rows(values_only=True))
        # linha1 (idx0) = headers; linha2 (idx1) = sub-headers de mês;
        # dados começam em linha3 (idx2).
        for r in rows[2:]:
            if not r or r[1] is None:
                continue
            empresa = str(r[1]).strip()
            # Actual = col10 (índice 10). Pode ser None ou '#VALUE!'.
            actual = r[10] if len(r) > 10 else None
            realizado = None
            if isinstance(actual, (int, float)) and actual == actual:
                realizado = float(actual)
            # Meta planilha = col4 (Forecast do mês da aba). Confiável só
            # como referência cruzada; a meta "oficial" pro dashboard vem
            # do calc_forecast (meta_de_mes_rampagem). Guardamos p/ debug.
            meta_plan = r[4] if len(r) > 4 else None
            meta_val = None
            if isinstance(meta_plan, (int, float)) and meta_plan == meta_plan:
                meta_val = float(meta_plan)
            registros.append({"empresa_planilha": empresa, "mes": mes,
                              "meta_planilha": meta_val,
                              "realizado": realizado})
    return registros
```

- [ ] **Step 3: Acrescentar `performance_por_deal` (match + estrutura por deal)**

Continuar em `fetch_performance.py`:

```python
def _casa_nome(empresa_planilha, deals_rampagem):
    """Casa nome da planilha com um deal do HubSpot. Retorna o deal ou None.

    1. Tenta config.EXCECOES_MATCH_NOME[empresa_planilha] → dealname exato.
    2. Senão, normaliza e casa por igualdade.
    """
    alvo = config.EXCECOES_MATCH_NOME.get(empresa_planilha)
    if alvo:
        for d in deals_rampagem:
            if d["dealname"] == alvo:
                return d
    norm_alvo = normalizar_nome(alvo or empresa_planilha)
    if not norm_alvo:
        return None
    for d in deals_rampagem:
        if normalizar_nome(d["dealname"]) == norm_alvo:
            return d
    return None


def performance_por_deal(deals_rampagem, registros):
    """Casa registros de performance com deals do HubSpot.

    Retorna (por_deal, mes_corrente, sem_acompanhamento):
      por_deal: {deal_id: {mes: {"meta_planilha": x, "realizado": y}}}
      mes_corrente: date (1º do mês) = mês mais recente entre todos os
                    registros, ou None se nenhum registro.
      sem_acompanhamento: lista de deals em rampa que não casaram com
                          nenhuma empresa da planilha.
    """
    # casa cada registro a um deal
    por_deal = {}
    for reg in registros:
        deal = _casa_nome(reg["empresa_planilha"], deals_rampagem)
        if deal is None:
            continue  # empresa da planilha não existe no HubSpot — ignora
        por_deal.setdefault(deal["deal_id"], {})[reg["mes"]] = {
            "meta_planilha": reg["meta_planilha"],
            "realizado": reg["realizado"],
        }
    # mês corrente = mês mais recente entre TODOS os registros
    meses_com_dado = [r["mes"] for r in registros if r["mes"] is not None]
    mes_corrente = max(meses_com_dado) if meses_com_dado else None
    # deals sem acompanhamento = deals em rampa cujo deal_id não está em por_deal
    casados = set(por_deal.keys())
    sem_acompanhamento = [d for d in deals_rampagem if d["deal_id"] not in casados]
    return por_deal, mes_corrente, sem_acompanhamento
```

- [ ] **Step 4: Smoke test em `test_calc.py` — lê a planilha real**

Acrescentar ao final de `test_calc.py`:

```python
# ---- fetch_performance (Fase 2: planilha real) ----
print("=" * 70)
print("FETCH_PERFORMANCE (planilha real data/):")
print("=" * 70)
import fetch_performance as fp

regs = fp.ler_performance()
print(f"  registros lidos: {len(regs)}")
for r in regs[:5]:
    print(f"    {r['empresa_planilha']!r} mes={r['mes'].isoformat()} "
          f"meta={r['meta_planilha']} real={r['realizado']}")
assert len(regs) > 0, "nenhum registro lido da planilha"
# agosto deve estar presente (aba Acompanhamento Linda 082026)
agos = [r for r in regs if r["mes"].month == 8]
assert len(agos) > 0, "nenhum registro de agosto"
print(f"  registros de agosto: {len(agos)}")

# normalizar_nome
assert fp.normalizar_nome("Dellys Food Service") == "dellys"
assert fp.normalizar_nome("  VOETUR ") == "voetur"
print("  normalizar_nome: 2/2 OK")

# performance_por_deal com deals dummy
dummies = [
    {"deal_id": "d1", "dealname": "Dellys Food Service"},
    {"deal_id": "d2", "dealname": "Grupo Voetur"},
    {"deal_id": "d3", "dealname": "Empresa Que Nao Esta Na Planilha"},
]
por_deal, mes_corr, sem = fp.performance_por_deal(dummies, regs)
print(f"  casados: {list(por_deal.keys())}  mes_corrente: {mes_corr}  sem: {[d['dealname'] for d in sem]}")
assert "d1" in por_deal, "Dellys deveria casar por normalização"
assert "d2" in por_deal, "Grupo Voetur deveria casar via EXCECOES_MATCH_NOME"
assert any(d["deal_id"] == "d3" for d in sem), "d3 deveria estar sem acompanhamento"
print("  performance_por_deal: 3/3 OK")
print("  fetch_performance: OK\n")
```

- [ ] **Step 5: Rodar o smoke — deve passar**

Run: `PYTHONUTF8=1 python test_calc.py 2>&1 | grep -A15 "FETCH_PERFORMANCE" | head -20`
Expected: `registros lidos: N` (N≈7, uma aba × 7 empresas), `registros de agosto: N`, `normalizar_nome: 2/2 OK`, `performance_por_deal: 3/3 OK`, `fetch_performance: OK`.

- [ ] **Step 6: Commit**

```bash
git add fetch_performance.py data/Acompanhamento_Rampagem.xlsx test_calc.py
git commit -m "feat(perf): fetch_performance — le planilha + match por nome

ler_performance(): le data/Acompanhamento_Rampagem.xlsx, acha abas
'Acompanhamento Linda MMaaaa', extrai (empresa, mes, meta, realizado).
normalizar_nome(): lowercase/sem acento/sem sufixos p/ match textual.
performance_por_deal(): casa com deals HubSpot (normalizado +
EXCECOES_MATCH_NOME), devolve por_deal + mes_corrente + sem_acompanhamento.
Planilha copiada p/ data/ (acesso no Cloud).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: `dashboard.py` — colunas novas + expander na tab Rampagem

**Objetivo:** Adicionar as colunas `% atingimento` e `Realizado` no `_df_rampagem`/`_df_rampagem_15` (após "Nome do negócio"), o expander de histórico por empresa e o expander "Deals sem acompanhamento" no `_render_rampagem`/`_render_rampagem_15`, e o `column_config` das rampagens.

**Files:**
- Modify: `dashboard.py` (`_df_rampagem`, `_df_rampagem_15`, `_render_rampagem`, `_render_rampagem_15`, `_tabela_principal` column_config)

**Interfaces:**
- Consumes: `fetch_performance.ler_performance`, `fetch_performance.performance_por_deal` (Task 3); `calc_forecast.meta_de_mes_rampagem` (Task 2); `config.PATH_PLANILHA_PERFORMANCE` (Task 1).
- Produces: tab Rampagem (Total e 15%) com colunas novas + 2 expanders.

- [ ] **Step 1: Confirmar como `entrada_rampagem` é populado no deal**

O `_df_rampagem` (dashboard.py:501) usa `d.get("entrada_rampagem")`, mas `fetch_hubspot._build_deal` só seta `data_ativacao`. Verificar onde `entrada_rampagem` é setado (provavelmente em `calcular_todos` ou `calcular_rampagem`).

Run: `grep -rn "entrada_rampagem\|dias_rampagem" calc_forecast.py | head -10`
Expected: linhas mostrando onde esses campos são populados. Anotar — o helper `meta_de_mes_rampagem` usa `deal["data_ativacao"]`, então confirmar que `data_ativacao` está presente no deal que chega em `_render_rampagem` (deve estar, pois vem de `_build_deal`). Se `entrada_rampagem` for só um alias visual, ok.

- [ ] **Step 2: Carregar performance dentro de `render_lente` (disponibilizar pro `_df_rampagem`)**

Em `dashboard.py`, dentro de `render_lente`, após `get_data()` e antes de montar as listas da lente, carregar a performance uma vez (compartilhada entre Total e 15% — o realizado é o mesmo, só a meta muda):

Localizar em `render_lente` (após o desempacotamento de `get_data()`, ~linha 820):
```python
    # ---- acompanhamento (Fase 2): realizado da planilha ----
    # Carrega uma vez; o realizado é o mesmo nas duas lentes (a meta muda).
    try:
        perf_regs = fetch_performance.ler_performance()
        perf_por_deal, perf_mes_corr, perf_sem = fetch_performance.performance_por_deal(
            ramp, perf_regs)
    except Exception as e:
        perf_por_deal, perf_mes_corr, perf_sem = {}, None, []
        st.caption(f"⚠ Acompanhamento indisponível ({type(e).__name__}).")
```

Adicionar `import fetch_performance` no topo do `dashboard.py` (junto aos outros imports, ~linha 27).

**Nota:** `performance_por_deal` casa com a lista `ramp` (base, não a filtrada) — o match é por deal, independe dos filtros. Os filtros aplicam-se depois em `_render_rampagem`. `perf_sem` é sobre `ramp` inteiro; o render filtra visualmente.

- [ ] **Step 3: Passar `perf_por_deal`/`perf_mes_corr`/`perf_sem` pra `_render_rampagem`/`_render_rampagem_15`**

Modificar as assinaturas pra receber performance. Em `render_lente`, na chamada das tabs (localizar `with tab_ramp:`):
```python
    with tab_ramp:
        if lente == "total":
            _render_rampagem(ramp_sel, inc, meses, fetched_at, dark, agrupar,
                             perf_por_deal, perf_mes_corr, perf_sem)
        else:
            _render_rampagem_15(ramp_sel, inc, meses, fetched_at, dark, agrupar,
                                perf_por_deal, perf_mes_corr, perf_sem)
```

- [ ] **Step 4: Adicionar colunas `% atingimento` + `Realizado` em `_df_rampagem`**

Modificar `_df_rampagem` (dashboard.py:485) — assinatura recebe performance:
```python
def _df_rampagem(sel, meses, perf_por_deal, perf_mes_corr):
    """DataFrame da aba 'Rampagem'. Modelo mínimo + 'Data de ativação'
    + colunas de acompanhamento (% atingimento, Realizado) após o nome."""
    import calc_forecast as cf
    data = {
        "Nome do negócio": [], "% atingimento": [], "Realizado": [],
        "Pipeline": [], "Proprietário": [],
        "Data de ativação": [], "Dias em rampagem": [],
        "Potencial": [], "TOTAL 6M": [],
    }
    for m in meses:
        data[mes_label(m)] = []
    for d in sel:
        data["Nome do negócio"].append(d["dealname"])
        # acompanhamento
        pct, real = _acompanhamento_dal(d, perf_por_deal, perf_mes_corr)
        data["% atingimento"].append(pct)
        data["Realizado"].append(real)
        data["Pipeline"].append(d["pipeline_label"])
        data["Proprietário"].append(d["owner_name"])
        data["Data de ativação"].append(d.get("data_ativacao"))
        data["Dias em rampagem"].append(int(d.get("dias_rampagem") or 0))
        data["Potencial"].append(int(d["potencial"] or 0))
        data["TOTAL 6M"].append(int(d["total_linha"]))
        for m in meses:
            data[mes_label(m)].append(int(d["volumes"].get(m, 0)))
    df = pd.DataFrame(data)
    for m in meses:
        df[mes_label(m)] = df[mes_label(m)].astype(int)
    for c in ("Dias em rampagem", "Potencial", "TOTAL 6M"):
        df[c] = df[c].astype(int)
    # Realizado / % podem ser None (deals sem performance) → Int64Dtype (nullable).
    for c in ("% atingimento", "Realizado"):
        df[c] = df[c].astype(pd.Int64Dtype())
    df["Data de ativação"] = pd.to_datetime(df["Data de ativação"], errors="coerce").dt.date
    return df
```

**Atenção:** `d.get("entrada_rampagem")` virou `d.get("data_ativacao")` na coluna "Data de ativação" — confirmar no Step 1 que isso é correto (ou manter `entrada_rampagem` se for o campo populado). Manter consistente com o que existe hoje.

- [ ] **Step 5: Helper `_acompanhamento_dal` — calcula % e realizado do mês corrente**

Acrescentar em `dashboard.py` (antes de `_df_rampagem`):

```python
def _acompanhamento_dal(deal, perf_por_deal, perf_mes_corr):
    """Devolve (pct_int, real_int) do mês corrente para o deal.

    pct = realizado / meta_de_mes_rampagem(deal, perf_mes_corr) * 100.
    Retorna (None, None) quando sem performance/mês corrente → exibidos
    como '–' (NaN via Int64Dtype). (None, int) quando meta=0 (só realizado).
    """
    import calc_forecast as cf
    if perf_mes_corr is None:
        return None, None
    perf = perf_por_deal.get(deal["deal_id"], {})
    reg = perf.get(perf_mes_corr)
    if reg is None or reg["realizado"] is None:
        return None, None
    real = reg["realizado"]
    meta = cf.meta_de_mes_rampagem(deal, perf_mes_corr)
    if meta <= 0:
        return None, int(round(real))
    pct = (real / meta) * 100
    return int(round(pct)), int(round(real))
```

- [ ] **Step 6: Aplicar as mesmas mudanças em `_df_rampagem_15`**

Modificar `_df_rampagem_15` (dashboard.py:516) — mesma estrutura de `_df_rampagem`, mas com a coluna "15% potencial". Acompanhamento igual (o helper usa `deal["potencial"]` que, na variante 15, já é `potencial_15`):

```python
def _df_rampagem_15(sel, meses, perf_por_deal, perf_mes_corr):
    """DataFrame da aba 'Rampagem 15%'. Igual ao _df_rampagem, com '15%
    potencial'. O acompanhamento (% / Realizado) usa meta_de_mes_rampagem
    sobre o potencial_15 (o deal desta variante tem potencial=potencial_15)."""
    data = {
        "Nome do negócio": [], "% atingimento": [], "Realizado": [],
        "Pipeline": [], "Proprietário": [],
        "Data de ativação": [], "Dias em rampagem": [],
        "Potencial": [], "15% potencial": [], "TOTAL 6M": [],
    }
    for m in meses:
        data[mes_label(m)] = []
    for d in sel:
        data["Nome do negócio"].append(d["dealname"])
        pct, real = _acompanhamento_dal(d, perf_por_deal, perf_mes_corr)
        data["% atingimento"].append(pct)
        data["Realizado"].append(real)
        data["Pipeline"].append(d["pipeline_label"])
        data["Proprietário"].append(d["owner_name"])
        data["Data de ativação"].append(d.get("data_ativacao"))
        data["Dias em rampagem"].append(int(d.get("dias_rampagem") or 0))
        data["Potencial"].append(int(d["potencial"] or 0))
        data["15% potencial"].append(int(d["potencial_15"] or 0))
        data["TOTAL 6M"].append(int(d["total_linha"]))
        for m in meses:
            data[mes_label(m)].append(int(d["volumes"].get(m, 0)))
    df = pd.DataFrame(data)
    for m in meses:
        df[mes_label(m)] = df[mes_label(m)].astype(int)
    for c in ("Dias em rampagem", "Potencial", "15% potencial", "TOTAL 6M"):
        df[c] = df[c].astype(int)
    for c in ("% atingimento", "Realizado"):
        df[c] = df[c].astype(pd.Int64Dtype())
    df["Data de ativação"] = pd.to_datetime(df["Data de ativação"], errors="coerce").dt.date
    return df
```

- [ ] **Step 7: `column_config` das rampagens ganha as 2 colunas**

Em `_tabela_principal` (dashboard.py:653-666), nos ramos `rampagem` e `rampagem_15`, adicionar `cc["% atingimento"]` e `cc["Realizado"]` como `NumberColumn`. Como as colunas usam `pd.Int64Dtype()` (nullable), o NaN exibe como célula vazia; se quiser `–`, formatar via `fmt_int` num `Styler` (decidir no smoke Task 6):

```python
    elif aba == "rampagem":
        cc["% atingimento"] = st.column_config.NumberColumn("% atingimento", format="%d %%")
        cc["Realizado"] = st.column_config.NumberColumn("Realizado", format="%d")
        cc["Data de ativação"] = st.column_config.DateColumn("Data de ativação", format="DD/MM/YYYY")
        cc["Dias em rampagem"] = st.column_config.NumberColumn("Dias em rampagem", format="%d")
        cc["Potencial"] = st.column_config.NumberColumn("Potencial", format="%d")
        cc["TOTAL 6M"] = st.column_config.NumberColumn("TOTAL 6M", format="%d")
    elif aba == "rampagem_15":
        cc["% atingimento"] = st.column_config.NumberColumn("% atingimento", format="%d %%")
        cc["Realizado"] = st.column_config.NumberColumn("Realizado", format="%d")
        cc["Data de ativação"] = st.column_config.DateColumn("Data de ativação", format="DD/MM/YYYY")
        cc["Dias em rampagem"] = st.column_config.NumberColumn("Dias em rampagem", format="%d")
        cc["Potencial"] = st.column_config.NumberColumn("Potencial", format="%d")
        cc["15% potencial"] = st.column_config.NumberColumn(
            "15% potencial", format="%d",
            help="15% do Potencial = round(potencial × 0,15). "
                 "O forecast desta aba (TOTAL 6M e meses) é baseado neste valor.")
        cc["TOTAL 6M"] = st.column_config.NumberColumn("TOTAL 6M", format="%d")
```

- [ ] **Step 8: Expander de histórico por empresa + "sem acompanhamento" em `_render_rampagem`**

Modificar `_render_rampagem` (dashboard.py:373) — assinatura recebe performance:

```python
def _render_rampagem(sel, incompletos, meses, fetched_at, dark, agrupar,
                     perf_por_deal, perf_mes_corr, perf_sem):
    inc_ramp = [d for d in incompletos if d.get("origem", "negociacao") == "rampagem"]
    total_6m = sum(d["total_linha"] for d in sel)
    pot_total = sum((d["potencial"] or 0) for d in sel)

    k1, k2, k3 = st.columns(3)
    k1.metric("Total corridas (6 meses)", fmt_int(total_6m))
    k2.metric("Deals em rampagem", len(sel))
    k3.metric("Potencial total", fmt_int(pot_total))

    st.markdown(f"_Mostrando **{len(sel)}** deals em rampagem. Última atualização: "
                f"{fetched_at.strftime('%d/%m/%Y %H:%M')}._")

    df = _df_rampagem(sel, meses, perf_por_deal, perf_mes_corr)
    _linha_total(df, meses, label="TOTAL")
    _tabela_principal(df, meses, dark, agrupar, aba="rampagem")
    _linha_total(df, meses, label="TOTAL")

    _incompletos_expander(inc_ramp, aba="rampagem", dark=dark)
    _historico_rampagem_expander(sel, perf_por_deal, perf_mes_corr, dark)
    _sem_acompanhamento_expander(perf_sem, sel, dark)
```

- [ ] **Step 9: Helpers `_historico_rampagem_expander` + `_sem_acompanhamento_expander`**

Acrescentar em `dashboard.py`:

```python
def _historico_rampagem_expander(sel, perf_por_deal, perf_mes_corr, dark):
    """Expander com histórico mês a mês (meta | realizado | %) por deal."""
    import calc_forecast as cf
    deals_com_hist = [d for d in sel
                      if d["deal_id"] in perf_por_deal and perf_por_deal[d["deal_id"]]]
    if not deals_com_hist:
        return
    with st.expander(f"📈 Histórico de acompanhamento ({len(deals_com_hist)} deals)",
                     expanded=False):
        for d in deals_com_hist:
            perf = perf_por_deal[d["deal_id"]]
            st.markdown(f"**{d['dealname']}**")
            rows = []
            for mes in sorted(perf.keys()):
                reg = perf[mes]
                real = reg["realizado"]
                meta = cf.meta_de_mes_rampagem(d, mes)
                pct = (real / meta * 100) if (real is not None and meta > 0) else None
                rows.append({"Mês": mes_label(mes),
                             "Meta": fmt_int(meta),
                             "Realizado": fmt_int(real),
                             "%": fmt_int(pct) if pct is not None else "–"})
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            st.markdown("")


def _sem_acompanhamento_expander(perf_sem, sel, dark):
    """Expander com deals em rampa que não casaram com a planilha."""
    sel_ids = {d["deal_id"] for d in sel}
    sem = [d for d in perf_sem if d["deal_id"] in sel_ids]
    if not sem:
        return
    with st.expander(f"⚠️ Deals sem acompanhamento na planilha ({len(sem)})",
                     expanded=False):
        st.markdown("_Estes deals estão em rampa no HubSpot mas não casaram com "
                    "nenhuma empresa da planilha. Se devem ter acompanhamento, "
                    "adicionar o mapeamento em `config.EXCECOES_MATCH_NOME`._")
        for d in sem:
            st.markdown(f"- **{d['dealname']}** (deal_id `{d['deal_id']}`)")
```

- [ ] **Step 10: Aplicar o mesmo padrão em `_render_rampagem_15`**

Modificar `_render_rampagem_15` (dashboard.py:401) — mesma estrutura de `_render_rampagem`, chamando `_df_rampagem_15`, `_historico_rampagem_expander` (o histórico usa `meta_de_mes_rampagem(d, mes)` onde `d` é o deal da variante 15, com `potencial=potencial_15` → meta 15%, % 15%), e `_sem_acompanhamento_expander`.

- [ ] **Step 11: Verificar sintaxe**

Run: `python -c "import ast; ast.parse(open('dashboard.py', encoding='utf-8').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 12: Commit**

```bash
git add dashboard.py
git commit -m "feat(perf): colunas %/Realizado + expander histórico na tab Rampagem

_df_rampagem/_df_rampagem_15 ganham colunas '% atingimento' e 'Realizado'
após 'Nome do negócio'. _render_rampagem/_render_rampagem_15 ganham
expander de histórico por empresa (meta|realizado|% mês a mês) + expander
'Deals sem acompanhamento'. render_lente carrega a performance uma vez
(compartilhada entre lentes — realizado igual, meta difere). column_config
das rampagens com as 2 colunas novas.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: `atualizar_performance.py` — script de push mensal

**Objetivo:** Script que a Marina roda depois de colar o Actual na planilha — faz `git add + commit + push` num comando.

**Files:**
- Create: `atualizar_performance.py`

- [ ] **Step 1: Criar `atualizar_performance.py`**

```python
# -*- coding: utf-8 -*-
"""Script de atualização mensal do acompanhamento.

Depois de colar o 'Actual' na planilha data/Acompanhamento_Rampagem.xlsx
(criando/atuando a aba 'Acompanhamento Linda MMaaaa'), rode:

    python atualizar_performance.py

Faz git add + commit + push da planilha, disparando o redeploy do
Streamlit Cloud. Não mexe em código, só no dado da planilha.
"""
import subprocess
import sys

PATH = "data/Acompanhamento_Rampagem.xlsx"


def main():
    msg = input("Mensagem do commit (Enter p/ padrão 'performance: atualizar realizado'): ").strip()
    if not msg:
        msg = "performance: atualizar realizado"
    msg += "\n\nCo-Authored-By: Claude <noreply@anthropic.com>"
    for cmd in (
        ["git", "add", PATH],
        ["git", "commit", "-m", msg],
        ["git", "push"],
    ):
        print(f"$ {' '.join(cmd)}")
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print(f"comando falhou (código {r.returncode}). Pare e verifique.")
            sys.exit(r.returncode)
    print("✓ Planilha atualizada e pushada. O Cloud vai redeployar.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verificar sintaxe**

Run: `python -c "import ast; ast.parse(open('atualizar_performance.py', encoding='utf-8').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 3: Commit**

```bash
git add atualizar_performance.py
git commit -m "feat(perf): atualizar_performance.py — git add+commit+push da planilha

Script que a Marina roda depois de colar o Actual na planilha. Um comando
dispara o redeploy do Cloud.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Smoke test local + ajustes

**Objetivo:** Rodar o app localmente, confirmar a tab Rampagem (Total e 15%) com as colunas novas, expander de histórico, expander de sem-acompanhamento, e que os filtros continuam funcionando.

**Files:**
- Possivelmente adjust: `dashboard.py` (se o smoke revelar algo no `Int64Dtype`/column_config), `config.py` (adicionar exceções de match que aparecerem).

- [ ] **Step 1: Rodar `test_calc.py` completo**

Run: `PYTHONUTF8=1 python test_calc.py 2>&1 | grep -E "META_DE_MES|FETCH_PERF|OK$|AssertionError|Error" | tail -15`
Expected: `meta_de_mes_rampagem: 8/8 OK`, `fetch_performance: OK`, sem AssertionError.

- [ ] **Step 2: Rodar o app localmente**

Run (background):
```bash
streamlit run app.py --server.port 8765 --server.headless true > .superpowers/sdd/streamlit-fase2.log 2>&1 &
sleep 12
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8765/_stcore/health
```
Expected: `HTTP 200`.

- [ ] **Step 3: Validar via Playwright (ou inspeção manual)**

Abrir `http://localhost:8765/Potencial_Total`, ir na tab **Rampagem**:
- Colunas `% atingimento` + `Realizado` presentes após "Nome do negócio".
- `TOTAL 6M` no fim.
- Expander "📈 Histórico de acompanhamento" presente (abrir, verificar histórico de uma empresa — ex.: Milky Moo — com mês/meta/realizado/%).
- Expander "⚠️ Deals sem acompanhamento" — se vazio, todas casaram; se listar deals, anotar pra adicionar em `EXCECOES_MATCH_NOME`.
- Repetir na lente **Potencial 15%** — mesma estrutura, % diferente (realizado igual, meta 15%).

- [ ] **Step 4: Ajustar `EXCECOES_MATCH_NOME` se aparecerem "sem acompanhamento"**

Se o expander listar deals que deveriam casar (ex.: "Grupo Voetur" não casou porque o nome na planilha é "Voetur" — já mapeado; se outro aparecer), adicionar em `config.EXCECOES_MATCH_NOME` e re-testar.

- [ ] **Step 5: Ajustar `Int64Dtype`/`column_config` se NaN mostrar feio**

Se a coluna "Realizado"/"% atingimento" com None mostrar `nan` em vez de `–`, ajustar: ou usar `pd.Int64Dtype()` (nullable) + `NumberColumn`, ou pré-formatar com `fmt_int` num `Styler`. Decidir no momento. Se ajustar, commit.

- [ ] **Step 6: Parar o streamlit e commit final (se houve ajustes)**

```bash
pkill -f "streamlit run app.py"
git add -A
git commit -m "fix(perf): ajustes pós smoke test

Co-Authored-By: Claude <noreply@anthropic.com>"
```

Se não houve ajustes, esta task só valida — anotar no handoff.

---

## Notas de deploy (Fase 2)

- **Push da Fase 2:** todas as tasks juntas num push (ou após a Task 6). O Cloud detecta o novo `data/Acompanhamento_Rampagem.xlsx` e os novos módulos.
- **Reboot + cache limpo:** após o deploy, Reboot no Cloud + abrir em aba anônima (ver memória `streamlit-cloud-deploy-asset-cache` — o gotcha da Fase 1 ainda aplica).
- **Atualização mensal:** depois de colar o Actual na planilha, rodar `python atualizar_performance.py` → push → Cloud redeploya. Não precisa Reboot pra só-planilha (não muda código), mas se o cache do `ler_performance` (ttl=900) estiver quente, o novo dado aparece em até 15 min (ou Reboot pra imediato).
- **Migração Supabase (futura):** quando o plugin Supabase destravar (ver memória `performance-fonte-supabase-pendente`), trocar `fetch_performance.py` por um SELECT no Postgres — `ler_performance()` vira a query, o resto (`performance_por_deal`, `normalizar_nome` talvez dispensável se a 99 tiver ID) não muda.
