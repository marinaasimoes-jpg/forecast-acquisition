# Aba Rampagem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the "Rampagem" forecast category (pipeline B2B Retention, stage RAMP UP) to the dashboard as 2 new tabs (total potencial + 15%), with Consolidado summing all 3 categories.

**Architecture:** Mirrors the existing "Ativação" tab pattern exactly. New fetch query for stage RAMP UP of the Retention pipeline; new `volume_por_mes_rampagem()` that reuses `_curva`/`_fator_proporcional` with data-base = `hs_v2_date_entered_1412072536`; thin `calcular_rampagem_15()` wrapper; 2 new render functions + dataframe builders; Consolidado gains a 4th column. Data-base is the entry-timestamp into RAMP UP (returned by CRM API v3 as `hs_v2_date_entered_*`, populated 6/6 — validated).

**Tech Stack:** Python, Streamlit, pandas, requests (HubSpot CRM API v3). No new deps.

## Global Constraints

- **Token:** `HUBSPOT_TOKEN` via env var or Streamlit Cloud secret ONLY. Never hardcoded. Run `git grep -n "pat-na1"` (and `pat-na1-<redacted>`) before every commit — only allowed match is the placeholder `pat-na1-seu-token-aqui` in `config.py:56`.
- **IDs are discovered, never assumed:** `PIPELINE_B2B_RETENTION = "922791528"`, `STAGE_RAMP_UP = "1412072536"`, `PROP_DATA_ATIVACAO_RAMPAGEM = "hs_v2_date_entered_1412072536"`. All validated against the HubSpot API on 2026-10-26.
- **Run all Python with `PYTHONUTF8=1`** on Windows (BR-locale data with accents).
- **Curva is fixed:** `<20k → [0.25, 0.5, 1.0]`; `≥20k → [0.25, 0.5, 0.75, 1.0]` (`config.CURVA_RAMPAGEM`, cutoff `LIMITE_POTENCIAL_ALTO = 20000`). Reuse `_curva`, do not redefine.
- **Probabilidade 100%** — never weight by stage (ignore HubSpot's `probability: 0.9` on RAMP UP).
- **Janela = 6 months** from current month inclusive (`config.MESES_JANELA`).
- **Conventions:** `step = 8` marks rampagem deals (7 = Ativação, 4/5/6 = Negociação). `origem = "rampagem"` on the partitioned deal dict.
- **DRY:** every rampagem function mirrors its Ativação twin — do not invent new patterns.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `config.py` | Modify | Add 3 constants for Retention pipeline / RAMP UP stage / data-ativação prop. Extend `DEAL_PROPERTIES`, `STAGE_BY_ID`, add `STAGES_RAMPAGEM`. |
| `fetch_hubspot.py` | Modify | Add `_fetch_rampagem()` query (stage RAMP UP of Retention). Parse `hs_v2_date_entered_1412072536` into `deal["data_ativacao"]`. `fetch_deals()` calls it and merges. |
| `calc_forecast.py` | Modify | Add `volume_por_mes_rampagem()` (mirrors `volume_por_mes_ativacao` with data-base = `data_ativacao`). Add `calcular_rampagem_15()` + `_calc_rampagem_15_safe()`. Extend `calcular_todos()` partition + `_motivo_incompleto()`. Add `sanity_test_rampagem()`. |
| `app.py` | Modify | 2 new tabs in `st.tabs`. Add `_render_rampagem()`, `_render_rampagem_15()`, `_df_rampagem()`, `_df_rampagem_15()`. Extend `_tabela_principal()` column_config (2 new `aba` values), `_incompletos_expander()` (rampagem branch), `_render_consolidado()` (4th column + KPI). Wire filters + sort. |
| `test_calc.py` | Modify | Add rampagem section (mirror Ativação block) + sanity print. |
| `selfcheck.py` | Modify | Extend `run()` signature with `rampagem`; add 5.10 checks (Rampagem found, no overlap with Ativação, Consolidado sums 3). |

---

## Task 1: config.py — add Retention/RAMP UP constants

**Files:**
- Modify: `config.py` (after line 97 `STAGES_ATIVACAO` block, and extend `DEAL_PROPERTIES`/`STAGE_BY_ID`)

**Interfaces:**
- Produces: `config.PIPELINE_B2B_RETENTION`, `config.STAGES_RAMPAGEM`, `config.STAGE_RAMP_UP`, `config.PROP_DATA_ATIVACAO_RAMPAGEM`. Later tasks read these.

- [ ] **Step 1: Add the Retention pipeline + RAMP UP stage + prop constants**

In `config.py`, immediately after the `STAGES_ATIVACAO = {...}` block (after line 97), insert:

```python
# ---- Aba Rampagem: pipeline B2B Retention, stage RAMP UP (spec aba Rampagem)
# Descoberto em 2026-10-26 pelo label exato (discover_schema + probe direto).
# Clientes JÁ em rampa (ativaram, subindo a curva). Fronteira: o deal migra do
# stage 7 "Ativação" (aquisição) p/ o stage RAMP UP (Retention) ao iniciar a rampa.
# hs_v2_date_entered_<stage_id> É retornável pela CRM API v3 (diferente do
# hs_date_entered_<id> v1, que NÃO é) — populado em 6/6 deals em 2026-10-26.
PIPELINE_B2B_RETENTION = "922791528"
STAGES_RAMPAGEM = {
    "922791528": ("1412072536", 8, "RAMP UP"),
}
STAGE_RAMP_UP = "1412072536"   # stage id do RAMP UP no B2B Retention
PROP_DATA_ATIVACAO_RAMPAGEM = "hs_v2_date_entered_1412072536"
PROP_DATA_ATIVACAO_RAMPAGEM_LABEL = "Data de entrada no Ramp Up"
```

- [ ] **Step 2: Add RAMP UP to `STAGE_BY_ID` so `_build_deal` resolves `step=8`**

Find the `STAGE_BY_ID.update(...)` line (line 109) and add after it:

```python
STAGE_BY_ID.update({s[0]: (s[1], s[2]) for s in STAGES_RAMPAGEM.values()})
```

- [ ] **Step 3: Extend `DEAL_PROPERTIES` to include the data-ativação prop**

Find the `DEAL_PROPERTIES = [...]` list (line 134) and append the rampagem prop. Replace the list with:

```python
DEAL_PROPERTIES = [
    "dealname", "dealstage", "pipeline", "hubspot_owner_id",
    PROP_PREVISAO, PROP_POTENCIAL, "closedate", "hs_lastmodifieddate",
    PROP_DATA_ATIVACAO_RAMPAGEM,
]
```

- [ ] **Step 4: Verify config loads and the new constants resolve**

Run:
```bash
cd "G:/Drives compartilhados/B2B Planning (Sales Ops & Intelligence)/4. Planning/Marina/Rampagem/dash forecast acquisition" && PYTHONUTF8=1 python -c "import config as c; print(c.PIPELINE_B2B_RETENTION, c.STAGE_RAMP_UP, c.PROP_DATA_ATIVACAO_RAMPAGEM); print('STAGE_BY_ID[ramp]:', c.STAGE_BY_ID.get('1412072536')); print('props:', c.PROP_DATA_ATIVACAO_RAMPAGEM in c.DEAL_PROPERTIES)"
```
Expected output:
```
922791528 1412072536 hs_v2_date_entered_1412072536
STAGE_BY_ID[ramp]: (8, 'RAMP UP')
props: True
```

- [ ] **Step 5: Commit**

```bash
git add config.py
git commit -m "feat(rampagem): config — Retention pipeline + RAMP UP stage + data-ativação prop

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: fetch_hubspot.py — fetch RAMP UP deals and parse data_ativacao

**Files:**
- Modify: `fetch_hubspot.py` (add `_fetch_rampagem`, extend `_build_deal`, extend `fetch_deals`)

**Interfaces:**
- Consumes: `config.PIPELINE_B2B_RETENTION`, `config.STAGE_RAMP_UP`, `config.PROP_DATA_ATIVACAO_RAMPAGEM`, `config.PIPELINES` (NOT extended — Retention is fetched separately, not via the 3-pipeline dict).
- Produces: deals with `step == 8`, `data_ativacao: dt.date | None`, `stage_label == "RAMP UP"`, `pipeline_label == "B2B Retention"`. `fetch_deals()` returns these merged into the `deals` list.

- [ ] **Step 1: Extend `_build_deal` to parse `data_ativacao`**

In `fetch_hubspot.py`, inside `_build_deal(d, owners, plabel_default, hoje_date)` (around line 145), after the `closedate = _parse_hs_date(...)` line (line 156), add:

```python
    # Data de ativação = entrada no stage RAMP UP (hs_v2_date_entered_*).
    # Só populado p/ deals do Retention/RAMP UP; None nos demais.
    data_ativacao = _parse_hs_date(_val(p.get(config.PROP_DATA_ATIVACAO_RAMPAGEM)))
```

Then in the returned dict (after `"closedate": closedate,` line 170), add the key:

```python
        "data_ativacao": data_ativacao,
```

- [ ] **Step 2: Add `_fetch_rampagem()` — single-pipeline query for RAMP UP**

After the `_fetch_pipeline` function (line 142), add:

```python
def _fetch_rampagem(modified_since=None):
    """Busca TODOS os deals do stage RAMP UP do pipeline B2B Retention.
    Espelha _fetch_pipeline, mas com filtro direto no stage_id (sem o
    dict PIPELINES, que é só dos 3 de aquisição). Retorna lista de deals raw."""
    filters = [
        {"value": config.PIPELINE_B2B_RETENTION,
         "propertyName": "pipeline", "operator": "EQ"},
        {"values": [config.STAGE_RAMP_UP],
         "propertyName": "dealstage", "operator": "IN"},
    ]
    if modified_since is not None:
        filters.append({"value": str(modified_since),
                        "propertyName": config.PROP_LASTMOD, "operator": "GTE"})
    body = {
        "filterGroups": [{"filters": filters}],
        "properties": config.DEAL_PROPERTIES,
        "limit": config.PAGE_SIZE,
    }
    raw, after = [], None
    while True:
        if after is not None:
            body["after"] = int(after)
        for _ in range(5):
            r = requests.post(f"{config.BASE}/crm/v3/objects/deals/search",
                              headers=_headers(), json=body, timeout=60)
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", "10")) + 1)
                continue
            r.raise_for_status()
            page = r.json()
            break
        raw.extend(page.get("results", []))
        after = page.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
        time.sleep(0.2)
    return raw
```

- [ ] **Step 3: Wire `_fetch_rampagem` into `fetch_deals()`**

In `fetch_deals()` (around line 198–204), after the `ThreadPoolExecutor` block that builds `deals` from the 3 acquisition pipelines, and before `fetched_at = dt.datetime.now()`, add:

```python
    # ---- Aba Rampagem: RAMP UP do B2B Retention (pipeline separado) ----
    raw_ramp = _fetch_rampagem(ms)
    for d in raw_ramp:
        deals.append(_build_deal(d, owners, "B2B Retention", hoje_date))
    log(f"  B2B Retention (RAMP UP): {len(raw_ramp)} deals.")
```

- [ ] **Step 4: Verify the fetch returns the 6 RAMP UP deals with data_ativacao**

Run:
```bash
cd "G:/Drives compartilhados/B2B Planning (Sales Ops & Intelligence)/4. Planning/Marina/Rampagem/dash forecast acquisition" && PYTHONUTF8=1 python -c "
import fetch_hubspot as fh
deals, owners, fa = fh.fetch_deals(log=lambda m: None)
ramp = [d for d in deals if d['step'] == 8]
print('total deals:', len(deals), '| rampagem (step 8):', len(ramp))
for d in ramp:
    print(f\"  {d['dealname'][:28]:30} step={d['step']} stage={d['stage_label']!r} pipe={d['pipeline_label']!r} data_ativ={d['data_ativacao']} pot={d['potencial']}\")
"
```
Expected: `rampagem (step 8): 6`, each deal has `stage_label='RAMP UP'`, `pipeline_label='B2B Retention'`, `data_ativacao` = a `datetime.date` (not None), `potencial` populated.

- [ ] **Step 5: Commit**

```bash
git add fetch_hubspot.py
git commit -m "feat(rampagem): fetch RAMP UP deals do B2B Retention + parse data_ativacao

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: calc_forecast.py — volume_por_mes_rampagem + partition + motivo_incompleto

**Files:**
- Modify: `calc_forecast.py` (add `volume_por_mes_rampagem`, extend `calcular_todos`, extend `_motivo_incompleto`)

**Interfaces:**
- Consumes: `deal["data_ativacao"]` (from fetch), `deal["potencial"]`, `config` curve/window helpers.
- Produces: `volume_por_mes_rampagem(deal, meses, hoje) -> (volumes, entrada, detalhes)`; `calcular_todos()` now returns `(negociacao, ativacao, rampagem, incompletos, meses)`.

- [ ] **Step 1: Add `volume_por_mes_rampagem` (mirror of `volume_por_mes_ativacao`)**

In `calc_forecast.py`, after `volume_por_mes_ativacao` (line 270), add:

```python
# ---- Rampagem (aba Rampagem) ---------------------------------------------
# Cliente JÁ em rampa (stage RAMP UP do B2B Retention). A rampa começa na
# data de entrada no stage = hs_v2_date_entered_1412072536 (prop
# data_ativacao, populada no fetch). Espelha volume_por_mes_ativacao: mesma
# curva, mesma proporcionalidade de M1 por dia, mesmo carry-forward de meses
# anteriores à janela. Única diferença: a data-base é data_ativacao, NÃO
# closedate (fechamento ≠ entrada na rampa — um deal pode ficar semanas no
# stage 7 "Ativação" antes de migrar p/ RAMP UP).
def volume_por_mes_rampagem(deal, meses, hoje):
    """Calcula volumes + metadados por mês da janela p/ um deal em Rampagem.

    Retorna (volumes, entrada, detalhes). entrada = data_ativacao (início da
    rampa = entrada no stage RAMP UP).
    """
    detalhes = {m: {"texto": "–", "rampa_idx": None, "frac": 0.0, "fator": None}
                for m in meses}
    volumes = {m: 0.0 for m in meses}

    potencial = deal["potencial"]
    entrada = deal.get("data_ativacao")   # data de entrada no RAMP UP
    if not potencial or potencial <= 0 or not entrada:
        return volumes, None, detalhes

    curva = _curva(potencial)
    fator_m1, dias_ativos, dias_no_mes = _fator_proporcional(entrada)
    mes_m1 = dt.date(entrada.year, entrada.month, 1)

    # Se o M1 (mês da entrada) está ANTES da janela, a rampa já começou no
    # passado: descobrir qual offset da curva cai no primeiro mês da janela.
    if mes_m1 not in volumes:
        delta_meses = (meses[0].year - mes_m1.year) * 12 + (meses[0].month - mes_m1.month)
        if delta_meses < 0:
            # entrada futura além da janela -> nada a exibir ainda
            return volumes, entrada, detalhes
        idx_m1 = 0
        offset_inicial = delta_meses   # já estamos offset meses adentro da rampa
    else:
        idx_m1 = meses.index(mes_m1)
        offset_inicial = 0

    for i in range(idx_m1, len(meses)):
        offset = offset_inicial + (i - idx_m1)
        mes = meses[i]
        if offset < len(curva):
            frac = curva[offset]
            if offset == 0:
                # M1 cai DENTRO da janela -> proporcional por dia
                vol = potencial * frac * fator_m1
                texto = (f"Mês 1 (entrada) · 25% de {potencial:,} × "
                         f"{dias_ativos}/{dias_no_mes} (fator {fator_m1:.3f}) "
                         f"= {int(round(vol)):,}")
            else:
                vol = potencial * frac
                nome_mes = {1: "Mês 1", 2: "Mês 2", 3: "Mês 3",
                            4: "Mês 4"}.get(offset + 1, f"Mês {offset+1}")
                texto = f"{nome_mes} · {int(frac*100)}% de {potencial:,} = {int(round(vol)):,}"
            volumes[mes] += vol
            detalhes[mes] = {"texto": texto, "rampa_idx": offset, "frac": frac,
                             "fator": fator_m1 if offset == 0 else None}
        else:
            vol = potencial * 1.0
            texto = f"Mês {len(curva)+1}+ (100%) · 100% de {potencial:,} = {int(round(vol)):,}"
            volumes[mes] += vol
            detalhes[mes] = {"texto": texto, "rampa_idx": len(curva),
                             "frac": 1.0, "fator": None}
    return volumes, entrada, detalhes


def dias_em_rampagem(data_ativacao, hoje):
    """Dias decorridos desde a entrada no RAMP UP. >=0."""
    if not data_ativacao:
        return None
    return max(0, (hoje - data_ativacao).days)
```

- [ ] **Step 2: Extend `calcular_todos` to partition rampagem and return 5-tuple**

Replace the entire `calcular_todos` function (lines 280–324) with:

```python
def calcular_todos(deals, hoje=None):
    """Particiona deals em (negociacao, ativacao, rampagem, incompletos) e
    calcula volumes.

    - negociacao: deals nas etapas 4/5/6 (rampa desde a ativação = fechamento+5dúteis).
    - ativacao:   deals na etapa 7 Ativação (rampa desde o closedate, sem +5dúteis).
    - rampagem:   deals no stage RAMP UP do B2B Retention (rampa desde a
                  data_ativacao = entrada no RAMP UP, sem +5dúteis).
    - incompletos: faltando potencial ou a data base da sua aba.

    Camada 2 (cálculo) — independente da renderização (spec 4.1).
    Retorna (negociacao, ativacao, rampagem, incompletos, meses).
    """
    if hoje is None:
        hoje = dt.date.today()
    meses = meses_janela(hoje)

    negociacao, ativacao, rampagem, incompletos = [], [], [], []
    for d in deals:
        step = d.get("step")
        eh_ativacao = step == 7
        eh_rampagem = step == 8
        tem_pot = d["potencial"] is not None and d["potencial"] > 0
        # data base de cada aba:
        #   closedate p/ Ativação; data_ativacao p/ Rampagem;
        #   previsao_fechamento p/ Negociação.
        if eh_rampagem:
            tem_data_base = d.get("data_ativacao") is not None
        elif eh_ativacao:
            tem_data_base = d.get("closedate") is not None
        else:
            tem_data_base = d.get("previsao_fechamento") is not None
        if not (tem_pot and tem_data_base):
            origem = ("rampagem" if eh_rampagem
                      else ("ativacao" if eh_ativacao else "negociacao"))
            incompletos.append({**d, "ativacao": None, "base_fechamento": None,
                                "atrasado": False, "volumes": {m: 0.0 for m in meses},
                                "detalhes": {}, "total_linha": 0,
                                "origem": origem,
                                "motivo_incompleto": _motivo_incompleto(d, eh_ativacao, eh_rampagem)})
            continue
        if eh_rampagem:
            vols, entrada, det = volume_por_mes_rampagem(d, meses, hoje)
            total_linha = sum(vols.values())
            rampagem.append({**d, "entrada_rampagem": entrada,
                             "ativacao": None, "base_fechamento": None,
                             "atrasado": False, "volumes": vols, "detalhes": det,
                             "total_linha": total_linha, "origem": "rampagem",
                             "dias_rampagem": dias_em_rampagem(entrada, hoje)})
        elif eh_ativacao:
            vols, entrada, det = volume_por_mes_ativacao(d, meses, hoje)
            total_linha = sum(vols.values())
            ativacao.append({**d, "entrada_ativacao": entrada,
                             "ativacao": None, "base_fechamento": None,
                             "atrasado": False, "volumes": vols, "detalhes": det,
                             "total_linha": total_linha, "origem": "ativacao",
                             "dias_ativacao": dias_em_ativacao(entrada, hoje)})
        else:
            vols, ativ, base, atrasado, det = volume_por_mes(d, meses, hoje)
            total_linha = sum(vols.values())
            negociacao.append({**d, "ativacao": ativ, "base_fechamento": base,
                               "atrasado": atrasado, "volumes": vols, "detalhes": det,
                               "total_linha": total_linha, "origem": "negociacao",
                               "dias_atraso": dias_atraso(d["previsao_fechamento"], hoje) if atrasado else 0})
    return negociacao, ativacao, rampagem, incompletos, meses
```

- [ ] **Step 3: Extend `_motivo_incompleto` with the rampagem branch**

Replace `_motivo_incompleto` (lines 327–337) with:

```python
def _motivo_incompleto(d, eh_ativacao=False, eh_rampagem=False):
    faltam = []
    if eh_rampagem:
        if not d.get("data_ativacao"):
            faltam.append("data de ativação (entrada no Ramp Up)")
    elif eh_ativacao:
        if not d.get("closedate"):
            faltam.append("data de fechamento (entrada na Ativação)")
    else:
        if not d.get("previsao_fechamento"):
            faltam.append("previsão de fechamento")
    if not (d.get("potencial") and d["potencial"] > 0):
        faltam.append("potencial mês")
    return "Faltando: " + " e ".join(faltam)
```

- [ ] **Step 4: Verify the 5-tuple partition works with real deals**

Run:
```bash
cd "G:/Drives compartilhados/B2B Planning (Sales Ops & Intelligence)/4. Planning/Marina/Rampagem/dash forecast acquisition" && PYTHONUTF8=1 python -c "
import datetime as dt, fetch_hubspot as fh, calc_forecast as cf
HOJE = dt.date(2026, 10, 26)
deals, owners, fa = fh.fetch_deals(log=lambda m: None)
neg, ativ, ramp, inc, meses = cf.calcular_todos(deals, hoje=HOJE)
print(f'neg={len(neg)} ativ={len(ativ)} ramp={len(ramp)} inc={len(inc)} meses={[m.strftime(\"%b/%y\") for m in meses]}')
for d in ramp:
    v = [int(d['volumes'][m]) for m in meses]
    print(f\"  {d['dealname'][:28]:30} entrada={d['entrada_rampagem']} pot={d['potencial']} total6m={int(d['total_linha'])}\")
    print(f'    meses: {v}')
"
```
Expected: `ramp=6`, each with `entrada_rampagem` = a date, `potencial` and `total_linha` populated, `meses` = 6 months `[Oct/26 .. Mar/27]`.

- [ ] **Step 5: Commit**

```bash
git add calc_forecast.py
git commit -m "feat(rampagem): volume_por_mes_rampagem + partition step 8 + motivo_incompleto

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: calc_forecast.py — calcular_rampagem_15 + _safe wrapper + sanity_test_rampagem

**Files:**
- Modify: `calc_forecast.py` (after `calcular_ativacao_15` block, after `_calc_ativacao_15_safe`)

**Interfaces:**
- Consumes: `rampagem` list (from `calcular_todos`), `volume_por_mes_rampagem`.
- Produces: `calcular_rampagem_15(rampagem, meses, hoje) -> list` (parallel, same order), `_calc_rampagem_15_safe(...)`, `sanity_test_rampagem(hoje) -> list`.

- [ ] **Step 1: Add `calcular_rampagem_15` (mirror of `calcular_ativacao_15`)**

After `_calc_ativacao_15_safe` (line 482), add:

```python
# ---- Rampagem Potencial Atualizado (aba: forecast sobre 15% do potencial) --
# Espelha calcular_ativacao_15, mas usa volume_por_mes_rampagem (rampa desde a
# data_ativacao = entrada no RAMP UP). Mesma reavaliação de curva pelo pot15.
def calcular_rampagem_15(rampagem, meses, hoje):
    """Variante de Rampagem com forecast baseado em 15% do potencial.

    Mesma rampa desde a data_ativacao (entrada no RAMP UP), mesma
    proporcionalidade de M1 por dia e mesmo carry-forward de meses anteriores
    à janela. Só a BASE de volume muda: potencial_15 = round(potencial*0.15).
    Curva REAVALIADA por potencial_15 (corte 20k agora se aplica a potencial*0.15).
    potencial ORIGINAL preservado em d["potencial"]; dias_rampagem preservado
    (depende só da data_ativacao, inalterado).
    """
    out = []
    for d in rampagem:
        pot_original = d["potencial"] or 0
        pot15 = int(round(pot_original * 0.15))
        # volume_por_mes_rampagem lê deal["potencial"] + deal["data_ativacao"];
        # sobrescrever potencial força a curva/_curva a usar pot15.
        deal_15 = {**d, "potencial": pot15}
        vols, entrada, det = volume_por_mes_rampagem(deal_15, meses, hoje)
        total_linha = sum(vols.values())
        out.append({**d,                      # preserva potencial ORIGINAL + dias_rampagem
                    "potencial_15": pot15,
                    "entrada_rampagem": entrada,
                    "volumes": vols,
                    "detalhes": det,
                    "total_linha": total_linha})
    return out


def _calc_rampagem_15_safe(rampagem, meses, hoje):
    """Wrapper de diagnóstico para calcular_rampagem_15 (espelha o de Ativação).

    O Streamlit Cloud redacta a msg de exceção no traceback público; este
    wrapper captura, acha o deal ofensor e re-lança RuntimeError com msg
    DESCritiva (nome do deal + campos + tipo do erro original) — sem token,
    legível no UI do Cloud. Em caminho feliz = idêntico a calcular_rampagem_15.
    """
    try:
        return calcular_rampagem_15(rampagem, meses, hoje)
    except Exception as e:
        offenders = []
        for d in rampagem:
            try:
                pot = d["potencial"] or 0
                pot15 = int(round(pot * 0.15))
                deal_15 = {**d, "potencial": pot15}
                volume_por_mes_rampagem(deal_15, meses, hoje)
            except Exception as e2:
                offenders.append(
                    f"deal {d.get('dealname')!r} "
                    f"(deal_id={d.get('deal_id')!r}, step={d.get('step')!r}, "
                    f"potencial={d.get('potencial')!r}, "
                    f"data_ativacao={d.get('data_ativacao')!r}) -> "
                    f"{type(e2).__name__}: {e2}")
        msg = (f"[diag calcular_rampagem_15] erro original: "
               f"{type(e).__name__}: {e}. ")
        if offenders:
            msg += "Deal(s) ofensor(es): " + " | ".join(offenders[:3])
        else:
            msg += ("Nenhum deal individual quebrou (erro coletivo ou na "
                    "serialização/cache).")
        raise RuntimeError(msg) from e


# ---- Teste de sanidade: Rampagem (spec aba Rampagem) ---------------------
def sanity_test_rampagem(hoje=None):
    """Valida a rampa de Rampagem (espelha sanity_test_ativacao).

    Cenários (deal fictício em Rampagem, entrada = data_ativacao):
      1) 10k entrando HOJE (no mês atual) -> M1 = 10000*0.25*fator, M2=5000, M3+=10000.
      2) 10k entrou há 3 meses -> mês atual já em 100% (offset >= 2 => 100%).
      3) 30k entrando hoje -> curva 4 meses: M1=25%*fator, M2=15000, M3=22500, M4=30000.

    Retorna lista de (descricao, esperado, volumes_calculados_por_mes, ok).
    """
    if hoje is None:
        hoje = dt.date.today()
    meses = meses_janela(hoje)

    def run(potencial, data_ativacao):
        d = {"potencial": potencial, "data_ativacao": data_ativacao,
             "step": 8, "dealname": "fictício"}
        vols, entrada, det = volume_por_mes_rampagem(d, meses, hoje)
        return [vols[m] for m in meses], entrada

    dm_atual = calendar.monthrange(hoje.year, hoje.month)[1]
    dias_ativos = dm_atual - hoje.day + 1
    fator = dias_ativos / dm_atual

    out = []
    # 1) 10k entrando HOJE
    v, _ = run(10000, hoje)
    esp_m1 = 10000 * 0.25 * fator
    out.append(("10k entrada hoje (mês atual)",
                {"m1": esp_m1, "m2": 5000, "m3": 10000},
                v, abs(v[0] - esp_m1) < 1 and abs(v[1] - 5000) < 1))
    # 2) 10k entrou há 3 meses -> 100% hoje
    tres_meses_atras = _add_meses(hoje, -3)
    v2, _ = run(10000, tres_meses_atras)
    out.append(("10k entrada há 3 meses (100% hoje)",
                {"m0": 10000}, v2, abs(v2[0] - 10000) < 1))
    # 3) 30k entrando hoje -> curva 4 meses
    v3, _ = run(30000, hoje)
    esp_m1b = 30000 * 0.25 * fator
    out.append(("30k entrada hoje (curva 4 meses)",
                {"m1": esp_m1b, "m2": 15000, "m3": 22500, "m4": 30000},
                v3, abs(v[0] - esp_m1b) < 1 and abs(v[1] - 15000) < 1))
    return out
```

- [ ] **Step 2: Verify `calcular_rampagem_15` and `sanity_test_rampagem` work**

Run:
```bash
cd "G:/Drives compartilhados/B2B Planning (Sales Ops & Intelligence)/4. Planning/Marina/Rampagem/dash forecast acquisition" && PYTHONUTF8=1 python -c "
import datetime as dt, fetch_hubspot as fh, calc_forecast as cf
HOJE = dt.date(2026, 10, 26)
deals, owners, fa = fh.fetch_deals(log=lambda m: None)
neg, ativ, ramp, inc, meses = cf.calcular_todos(deals, hoje=HOJE)
ramp15 = cf._calc_rampagem_15_safe(ramp, meses, HOJE)
print('ramp15 deals:', len(ramp15))
for d in ramp15:
    print(f\"  {d['dealname'][:28]:30} pot={d['potencial']:>7,} -> 15%={d['potencial_15']:>6,} total6m={int(d['total_linha']):>8,}\")
print()
print('SANITY rampagem:')
for desc, esp, v, ok in cf.sanity_test_rampagem(HOJE):
    print(f'  {desc}: {[int(x) for x in v]} -> {\"OK\" if ok else \"FALHOU\"}')
"
```
Expected: 6 ramp15 deals with `potencial_15 = round(potencial*0.15)`; all 3 sanity tests `OK`.

- [ ] **Step 3: Commit**

```bash
git add calc_forecast.py
git commit -m "feat(rampagem): calcular_rampagem_15 + _safe wrapper + sanity_test_rampagem

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: selfcheck.py — extend run() with rampagem + 5.10 checks

**Files:**
- Modify: `selfcheck.py` (extend `run` signature + body)

**Interfaces:**
- Consumes: `rampagem` list, `config.STAGES_RAMPAGEM`, `config.PIPELINE_B2B_RETENTION`.
- Produces: `run(negociacao, ativacao, rampagem, incompletos, meses, fetched_deals, hoje)` returns checks including 5.10 series. **Callers must update to the new 7-arg signature.**

- [ ] **Step 1: Extend `run()` signature and add rampagem to `todos`**

In `selfcheck.py`, change the `run` signature (line 28) from:
```python
def run(negociacao, ativacao, incompletos, meses, fetched_deals, hoje=None):
```
to:
```python
def run(negociacao, ativacao, rampagem, incompletos, meses, fetched_deals, hoje=None):
```
And in the docstring (line 29–30), update to note rampagem. Then change line 34:
```python
    todos = negociacao + ativacao + incompletos
```
to:
```python
    todos = negociacao + ativacao + rampagem + incompletos
```

- [ ] **Step 2: Add 5.10 checks (Rampagem found, no overlap, consolidado sums 3)**

Find the end of the `run` function (before `return checks`). Add, immediately before `return checks`:

```python
    # ---- 5.10 Rampagem (spec aba Rampagem / verif. v3) ----
    checks.append(("5.10",) +
                  _ok(f"Pipeline B2B Retention (id {config.PIPELINE_B2B_RETENTION}) "
                      f"configurado p/ Rampagem."))
    sid_ramp = config.STAGES_RAMPAGEM[config.PIPELINE_B2B_RETENTION][0]
    tem_ramp = any(d["stage_id"] == sid_ramp for d in fetched_deals)
    if tem_ramp:
        checks.append(("5.10",) +
                      _ok(f"Rampagem: {len(rampagem)} deal(s) no stage RAMP UP "
                          f"({sid_ramp})."))
    else:
        checks.append(("5.10",) +
                      _warn("Nenhum deal no stage RAMP UP (pode estar vazio)."))
    # 5.10b nenhum deal em Rampagem E Ativação ao mesmo tempo
    ids_ramp = {d["deal_id"] for d in rampagem}
    ids_ativ = {d["deal_id"] for d in ativacao}
    dup_ra = ids_ramp & ids_ativ
    if not dup_ra:
        checks.append(("5.10",) +
                      _ok("Nenhum deal aparece ao mesmo tempo em Ativação e Rampagem."))
    else:
        checks.append(("5.10",) +
                      _warn(f"{len(dup_ra)} deal(s) em Ativação E Rampagem "
                            f"(deveriam migrar, não duplicar).",
                            [d for d in fetched_deals if d["deal_id"] in dup_ra]))
    # 5.10c Consolidado = soma das três abas, mês a mês
    for m in meses:
        vn = sum(d["volumes"].get(m, 0) for d in negociacao)
        va = sum(d["volumes"].get(m, 0) for d in ativacao)
        vr = sum(d["volumes"].get(m, 0) for d in rampagem)
        checks.append(("5.10",) +
                      _ok(f"Consolidado {m.strftime('%b/%y')}: "
                          f"neg={int(vn)} + ativ={int(va)} + ramp={int(vr)} "
                          f"= {int(vn+va+vr)}."))

    return checks
```

(Make sure there is only ONE `return checks` at the end — if the original had `return checks` as the last line, the new block's `return checks` replaces it; do not leave two.)

- [ ] **Step 3: Verify selfcheck runs with the new signature (will fail at callers until Task 6/7 update them — that's expected here; verify the module imports and `run` accepts 7 args)**

Run:
```bash
cd "G:/Drives compartilhados/B2B Planning (Sales Ops & Intelligence)/4. Planning/Marina/Rampagem/dash forecast acquisition" && PYTHONUTF8=1 python -c "
import datetime as dt, fetch_hubspot as fh, calc_forecast as cf, selfcheck as sc
HOJE = dt.date(2026, 10, 26)
deals, owners, fa = fh.fetch_deals(log=lambda m: None)
neg, ativ, ramp, inc, meses = cf.calcular_todos(deals, hoje=HOJE)
checks = sc.run(neg, ativ, ramp, inc, meses, deals, hoje=HOJE)
print(sc.summary(checks))
for cid, st, msg, dl in checks:
    if st == 'warn':
        print(f'  WARN [{cid}] {msg} ({len(dl)} deals)')
"
```
Expected: `summary` shows mostly `ok`, with `5.10` checks present. (Existing `5.6`/`5.7`/`5.8` Ativação checks may now warn about consolidation expecting 2 — that's fine, Task 7 fixes the consolidated check fully. Focus: 5.10 series is `ok` and 0 duplicates Ativação↔Rampagem.)

- [ ] **Step 4: Commit**

```bash
git add selfcheck.py
git commit -m "feat(rampagem): selfcheck 5.10 — Rampagem found, no overlap, consolidado 3 abas

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: test_calc.py — add rampagem section + sanity

**Files:**
- Modify: `test_calc.py`

**Interfaces:**
- Consumes: `cf.calcular_todos` (5-tuple), `cf.calcular_rampagem_15`, `cf.sanity_test_rampagem`, `sc.run` (7-arg).

- [ ] **Step 1: Update the unpacking to the 5-tuple**

In `test_calc.py`, change line 20 from:
```python
neg, ativ, inc, meses = cf.calcular_todos(deals, hoje=HOJE)
```
to:
```python
neg, ativ, ramp, inc, meses = cf.calcular_todos(deals, hoje=HOJE)
```
And update the print on line 21 from:
```python
print(f"Negociacao: {len(neg)} | Ativacao: {len(ativ)} | Incompletos: {len(inc)}")
```
to:
```python
print(f"Negociacao: {len(neg)} | Ativacao: {len(ativ)} | Rampagem: {len(ramp)} | Incompletos: {len(inc)}")
```

- [ ] **Step 2: Update the selfcheck call to the 7-arg signature**

Change line 147 from:
```python
checks = sc.run(neg, ativ, inc, meses, deals, hoje=HOJE)
```
to:
```python
checks = sc.run(neg, ativ, ramp, inc, meses, deals, hoje=HOJE)
```

- [ ] **Step 3: Add the Rampagem + Rampagem 15% + sanity sections**

Before the `# ---- self-check ----` block (line 143), insert:

```python
# ---- RAMPAGEM (stage RAMP UP do B2B Retention) ----
print("\n" + "=" * 70)
print("RAMPAGEM (rampa desde data_ativacao = entrada no RAMP UP):")
print("=" * 70)
for d in ramp:
    v = [int(d["volumes"][m]) for m in meses]
    print(f"  {d['dealname'][:28]!r:30s} pipe={d['pipeline_label'][:18]:18s} "
          f"entrada={d['entrada_rampagem']} dias={d['dias_rampagem']} "
          f"pot={d['potencial']} total6m={int(d['total_linha'])}")
    print(f"     meses: {v}")
print(f"  ... total em rampagem: {len(ramp)}\n")

# ---- sanity test Rampagem ----
print("=" * 70)
print("SANITY TEST Rampagem (deals fictícios):")
print("=" * 70)
for desc, esp, v, ok in cf.sanity_test_rampagem(hoje=HOJE):
    print(f"  {desc}: {[int(x) for x in v]} -> {'OK' if ok else 'FALHOU'}")

# ---- duplicidade Ativação x Rampagem (esperado 0) ----
print()
print("=" * 70)
print("DUPLICIDADE Ativação x Rampagem (esperado 0):")
print("=" * 70)
ids_ativ = {d["deal_id"] for d in ativ}
ids_ramp = {d["deal_id"] for d in ramp}
dup_ar = ids_ativ & ids_ramp
print(f"  {len(dup_ar)} deal(s) em ambas as abas.")

# ---- aba Rampagem Potencial Atualizado (forecast sobre 15%) ----
print("\n" + "=" * 70)
print("RAMPAGEM POTENCIAL ATUALIZADO (forecast sobre 15%):")
print("=" * 70)
ramp_15 = cf._calc_rampagem_15_safe(ramp, meses, HOJE)
pot_orig_r = sum((d["potencial"] or 0) for d in ramp_15)
pot15_r = sum(d["potencial_15"] for d in ramp_15)
print(f"  Deals: {len(ramp_15)} | potencial original: {pot_orig_r:,} -> "
      f"15%: {pot15_r:,} | total 6m: {int(sum(d['total_linha'] for d in ramp_15)):,}")
for d in ramp_15:
    v = [int(d["volumes"][m]) for m in meses]
    print(f"  {d['dealname'][:28]!r:30s} pot={d['potencial']:>7,} "
          f"-> 15%={d['potencial_15']:>6,} dias={d.get('dias_rampagem',0):>3} "
          f"total6m={int(d['total_linha']):>8,}")
    print(f"     meses: {v}")
print(f"  ... total deals 15% ramp: {len(ramp_15)}\n")
print("  TOTAL por mês (aba Rampagem 15%):")
for m in meses:
    t = sum(d["volumes"][m] for d in ramp_15)
    print(f"  {m.strftime('%b/%y'):8s} 15%={int(t):>10,}")
t6r = sum(d["total_linha"] for d in ramp_15)
print(f"  {'TOTAL':8s} 15%={int(t6r):>10,}")

```

- [ ] **Step 4: Update the consolidated total block to sum 3 categories**

Replace the final consolidated block (lines 153–162) with:

```python
# ---- total consolidado (Negociação + Ativação + Rampagem) ----
print("\n" + "=" * 70)
print("TOTAL por mês (Negociação + Ativação + Rampagem):")
print("=" * 70)
for m in meses:
    tn = sum(d['volumes'][m] for d in neg)
    ta = sum(d['volumes'][m] for d in ativ)
    tr = sum(d['volumes'][m] for d in ramp)
    print(f"  {m.strftime('%b/%y'):8s} neg={int(tn):>10,} ativ={int(ta):>8,} ramp={int(tr):>10,} soma={int(tn+ta+tr):>10,}")
tn6 = sum(d['total_linha'] for d in neg)
ta6 = sum(d['total_linha'] for d in ativ)
tr6 = sum(d['total_linha'] for d in ramp)
print(f"  {'TOTAL':8s} neg={int(tn6):>10,} ativ={int(ta6):>8,} ramp={int(tr6):>10,} soma={int(tn6+ta6+tr6):>10,}")
```

- [ ] **Step 5: Run the full test_calc.py end-to-end**

Run:
```bash
cd "G:/Drives compartilhados/B2B Planning (Sales Ops & Intelligence)/4. Planning/Marina/Rampagem/dash forecast acquisition" && PYTHONUTF8=1 python test_calc.py 2>&1 | tail -50
```
Expected: 0 exceptions; `Rampagem: 6`; all 3 sanity tests `OK`; `DUPLICIDADE Ativação x Rampagem: 0`; consolidated table has a `ramp=` column; selfcheck summary shows `ok` with `5.10` series present.

- [ ] **Step 6: Commit**

```bash
git add test_calc.py
git commit -m "test(rampagem): test_calc.py — rampagem + 15% + sanity + consolidado 3 abas

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: app.py — 2 new tabs, render + df functions, column_config, consolidado, filters

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: `cf.calcular_todos` (5-tuple), `cf._calc_rampagem_15_safe`, `sc.run` (7-arg), all existing helpers (`_linha_total`, `_tabela_principal`, `_incompletos_expander`, `_zebra_styler`, `_filtrar_paralelo`, `_sort_padrao`, `fmt_int`, `mes_label`).

**CRITICAL — two call sites of `calcular_todos` must both update to the 5-tuple:**
1. `_load_full_v2()` (line 71) and `_load_incremental_v2()` (line 84) — both currently `neg, ativ, inc, meses = cf.calcular_todos(...)`. Both also compute `neg_15`/`ativ_15` and return a 9-tuple.
2. `main()` (line 115) unpacks the 9-tuple from `get_data()`, NOT `calcular_todos` directly.

So the change propagates: `calcular_todos` 5-tuple → `_load_*_v2` compute `ramp_15` and return a **10-tuple** → `main()` unpacks 10 values.

- [ ] **Step 1: Update `_load_full_v2` to the 5-tuple + ramp_15 + 10-tuple return**

In `_load_full_v2` (lines 67–74), replace lines 71–74:
```python
    neg, ativ, inc, meses = cf.calcular_todos(deals, hoje=hoje)
    neg_15 = cf._calc_negociacao_15_safe(neg, meses, hoje)
    ativ_15 = cf._calc_ativacao_15_safe(ativ, meses, hoje)
    return neg, ativ, inc, meses, fetched_at, hoje, deals, neg_15, ativ_15
```
with:
```python
    neg, ativ, ramp, inc, meses = cf.calcular_todos(deals, hoje=hoje)
    neg_15 = cf._calc_negociacao_15_safe(neg, meses, hoje)
    ativ_15 = cf._calc_ativacao_15_safe(ativ, meses, hoje)
    ramp_15 = cf._calc_rampagem_15_safe(ramp, meses, hoje)
    return neg, ativ, ramp, inc, meses, fetched_at, hoje, deals, neg_15, ativ_15, ramp_15
```

- [ ] **Step 2: Update `_load_incremental_v2` identically (lines 84–87)**

Replace:
```python
    neg, ativ, inc, meses = cf.calcular_todos(deals, hoje=hoje)
    neg_15 = cf._calc_negociacao_15_safe(neg, meses, hoje)
    ativ_15 = cf._calc_ativacao_15_safe(ativ, meses, hoje)
    return neg, ativ, inc, meses, fetched_at, hoje, deals, neg_15, ativ_15
```
with:
```python
    neg, ativ, ramp, inc, meses = cf.calcular_todos(deals, hoje=hoje)
    neg_15 = cf._calc_negociacao_15_safe(neg, meses, hoje)
    ativ_15 = cf._calc_ativacao_15_safe(ativ, meses, hoje)
    ramp_15 = cf._calc_rampagem_15_safe(ramp, meses, hoje)
    return neg, ativ, ramp, inc, meses, fetched_at, hoje, deals, neg_15, ativ_15, ramp_15
```

- [ ] **Step 3: Update `main()` to unpack the 10-tuple**

In `main()`, replace line 115:
```python
    neg, ativ, inc, meses, fetched_at, hoje, fetched_deals, neg_15, ativ_15 = get_data()
```
with:
```python
    neg, ativ, ramp, inc, meses, fetched_at, hoje, fetched_deals, neg_15, ativ_15, ramp_15 = get_data()
```

- [ ] **Step 4: Update the selfcheck call in main() to the 7-arg signature**

Replace line 118:
```python
    checks = sc.run(neg, ativ, inc, meses, fetched_deals, hoje)
```
with:
```python
    checks = sc.run(neg, ativ, ramp, inc, meses, fetched_deals, hoje)
```

- [ ] **Step 5: Update the filtros base set + add ramp_sel/ramp_15_sel filtering + sort**

Replace line 129:
```python
    todos_deals = neg + ativ
```
with:
```python
    todos_deals = neg + ativ + ramp
```
Then, after `ativ_15_sel = _filtrar_paralelo(ativ_15, ativ_sel)` (line 184), add:
```python
    ramp_sel = aplica_filtros(ramp)
    ramp_15_sel = _filtrar_paralelo(ramp_15, ramp_sel)
```
And in the `_sort_padrao(...)` block (lines 187–190), add:
```python
    _sort_padrao(ramp_sel)
    _sort_padrao(ramp_15_sel)
```

- [ ] **Step 6: Extend `st.tabs` to 7 tabs and wire the 2 new render calls**

Replace the `st.tabs(...)` block (lines 193–206):
```python
    tab_neg, tab_neg15, tab_ativ, tab_ativ15, tab_cons = st.tabs(
        ["Negociação", "Negociação Potencial atualizado", "Ativação",
         "Ativação Potencial Atualizado", "Consolidado"])

    with tab_neg:
        _render_negociacao(neg_sel, inc, meses, fetched_at, dark, agrupar)
    with tab_neg15:
        _render_negociacao_15(neg_15_sel, inc, meses, fetched_at, dark, agrupar)
    with tab_ativ:
        _render_ativacao(ativ_sel, inc, meses, fetched_at, dark, agrupar)
    with tab_ativ15:
        _render_ativacao_15(ativ_15_sel, inc, meses, fetched_at, dark, agrupar)
    with tab_cons:
        _render_consolidado(neg_sel, ativ_sel, meses, dark)
```
with:
```python
    tab_neg, tab_neg15, tab_ativ, tab_ativ15, tab_ramp, tab_ramp15, tab_cons = st.tabs(
        ["Negociação", "Negociação Potencial atualizado", "Ativação",
         "Ativação Potencial Atualizado", "Rampagem",
         "Rampagem Potencial Atualizado", "Consolidado"])

    with tab_neg:
        _render_negociacao(neg_sel, inc, meses, fetched_at, dark, agrupar)
    with tab_neg15:
        _render_negociacao_15(neg_15_sel, inc, meses, fetched_at, dark, agrupar)
    with tab_ativ:
        _render_ativacao(ativ_sel, inc, meses, fetched_at, dark, agrupar)
    with tab_ativ15:
        _render_ativacao_15(ativ_15_sel, inc, meses, fetched_at, dark, agrupar)
    with tab_ramp:
        _render_rampagem(ramp_sel, inc, meses, fetched_at, dark, agrupar)
    with tab_ramp15:
        _render_rampagem_15(ramp_15_sel, inc, meses, fetched_at, dark, agrupar)
    with tab_cons:
        _render_consolidado(neg_sel, ativ_sel, ramp_sel, meses, dark)
```

- [ ] **Step 7: Add `_render_rampagem` and `_render_rampagem_15` (mirror Ativação twins)**

After `_render_ativacao_15` (line 357), add:

```python
# ---- renderização: Rampagem (stage RAMP UP do B2B Retention) --------------
def _render_rampagem(sel, incompletos, meses, fetched_at, dark, agrupar):
    """Espelha _render_ativacao, mas a data-base é a entrada no RAMP UP
    (data_ativacao) e o pipeline é o B2B Retention. Coluna "Data de ativação"
    no lugar de "Entrada na Ativação"."""
    inc_ramp = [d for d in incompletos if d.get("origem", "negociacao") == "rampagem"]
    total_6m = sum(d["total_linha"] for d in sel)
    pot_total = sum((d["potencial"] or 0) for d in sel)

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total corridas (6 meses)", fmt_int(total_6m))
    k2.metric("Deals em rampagem", len(sel))
    k3.metric("Potencial total", fmt_int(pot_total))
    k4.metric("Inconsistentes (>90d <100%)", 0)  # placeholder; sem regra D.3 p/ rampagem
    k5.metric("Incompletos", len(inc_ramp))

    st.markdown(f"_Mostrando **{len(sel)}** deals em rampagem (stage RAMP UP do "
                f"B2B Retention). Última atualização: "
                f"{fetched_at.strftime('%d/%m/%Y %H:%M')}._")

    df = _df_rampagem(sel, meses)
    _linha_total(df, meses, label="TOTAL")
    _tabela_principal(df, meses, dark, agrupar, aba="rampagem")
    _linha_total(df, meses, label="TOTAL")

    _incompletos_expander(inc_ramp, aba="rampagem", dark=dark)


# ---- renderização: Rampagem Potencial Atualizado (forecast sobre 15%) ------
def _render_rampagem_15(sel, incompletos, meses, fetched_at, dark, agrupar):
    """Espelha _render_ativacao_15, mas p/ Rampagem (data-base = entrada no
    RAMP UP). Coluna "15% potencial" à direita de "Potencial"; forecast
    (meses + TOTAL 6M) baseado em 15%. "Potencial" mostra o ORIGINAL.
    """
    inc_ramp = [d for d in incompletos if d.get("origem", "negociacao") == "rampagem"]
    total_6m = sum(d["total_linha"] for d in sel)
    pot_15_total = sum((d["potencial_15"] or 0) for d in sel)
    pot_total = sum((d["potencial"] or 0) for d in sel)

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total corridas (6 meses)", fmt_int(total_6m))
    k2.metric("Deals em rampagem", len(sel))
    k3.metric("Potencial total (15%)", fmt_int(pot_15_total))
    k4.metric("Inconsistentes (>90d <100%)", 0)
    k5.metric("Incompletos", len(inc_ramp))

    st.markdown(
        f"_Mostrando **{len(sel)}** deals em rampagem com forecast baseado em "
        f"**15% do potencial**. Potencial original: {fmt_int(pot_total)} → "
        f"15%: {fmt_int(pot_15_total)}. Última atualização: "
        f"{fetched_at.strftime('%d/%m/%Y %H:%M')}._")

    df = _df_rampagem_15(sel, meses)
    _linha_total(df, meses, label="TOTAL")
    _tabela_principal(df, meses, dark, agrupar, aba="rampagem_15")
    _linha_total(df, meses, label="TOTAL")

    _incompletos_expander(inc_ramp, aba="rampagem", dark=dark)
```

- [ ] **Step 8: Add `_df_rampagem` and `_df_rampagem_15` (mirror `_df_ativacao*`)**

After `_df_ativacao_15` (line 530), add:

```python
def _df_rampagem(sel, meses):
    """DataFrame da aba "Rampagem". Modelo mínimo + "Data de ativação"
    (entrada no RAMP UP). Mesmo schema de _df_ativacao, trocando
    "Entrada na Ativação" -> "Data de ativação" e "Dias em ativação" ->
    "Dias em rampagem"."""
    data = {
        "Nome do negócio": [], "Pipeline": [], "Proprietário": [],
        "Data de ativação": [], "Dias em rampagem": [],
        "Potencial": [], "TOTAL 6M": [],
    }
    for m in meses:
        data[mes_label(m)] = []
    for d in sel:
        data["Nome do negócio"].append(d["dealname"])
        data["Pipeline"].append(d["pipeline_label"])
        data["Proprietário"].append(d["owner_name"])
        data["Data de ativação"].append(d.get("entrada_rampagem"))
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
    df["Data de ativação"] = pd.to_datetime(df["Data de ativação"], errors="coerce").dt.date
    return df


def _df_rampagem_15(sel, meses):
    """DataFrame da aba "Rampagem Potencial Atualizado".
    Igual ao _df_rampagem, mas com a coluna "15% potencial" posicionada entre
    "Potencial" e "TOTAL 6M". "Potencial" mostra o ORIGINAL; meses e TOTAL 6M
    refletem o forecast sobre 15%."""
    data = {
        "Nome do negócio": [], "Pipeline": [], "Proprietário": [],
        "Data de ativação": [], "Dias em rampagem": [],
        "Potencial": [], "15% potencial": [], "TOTAL 6M": [],
    }
    for m in meses:
        data[mes_label(m)] = []
    for d in sel:
        data["Nome do negócio"].append(d["dealname"])
        data["Pipeline"].append(d["pipeline_label"])
        data["Proprietário"].append(d["owner_name"])
        data["Data de ativação"].append(d.get("entrada_rampagem"))
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
    df["Data de ativação"] = pd.to_datetime(df["Data de ativação"], errors="coerce").dt.date
    return df
```

- [ ] **Step 9: Extend `_tabela_principal` column_config with `rampagem` and `rampagem_15` branches**

In `_tabela_principal` (line 596), inside the `if/elif` chain on `aba`, after the `elif aba == "ativacao_15":` block (ends line 636) and before the `else:` (line 637), insert:

```python
    elif aba == "rampagem":
        cc["Data de ativação"] = st.column_config.DateColumn("Data de ativação", format="DD/MM/YYYY")
        cc["Dias em rampagem"] = st.column_config.NumberColumn("Dias em rampagem", format="%d")
        cc["Potencial"] = st.column_config.NumberColumn("Potencial", format="%d")
        cc["TOTAL 6M"] = st.column_config.NumberColumn("TOTAL 6M", format="%d")
    elif aba == "rampagem_15":
        cc["Data de ativação"] = st.column_config.DateColumn("Data de ativação", format="DD/MM/YYYY")
        cc["Dias em rampagem"] = st.column_config.NumberColumn("Dias em rampagem", format="%d")
        cc["Potencial"] = st.column_config.NumberColumn("Potencial", format="%d")
        cc["15% potencial"] = st.column_config.NumberColumn(
            "15% potencial", format="%d",
            help="15% do Potencial = round(potencial × 0,15). "
                 "O forecast desta aba (TOTAL 6M e meses) é baseado neste valor.")
        cc["TOTAL 6M"] = st.column_config.NumberColumn("TOTAL 6M", format="%d")
```

- [ ] **Step 10: Extend `_linha_total` cols_num with the rampagem numeric columns**

In `_linha_total` (line 551), find the `cols_num = [...]` list and add the rampagem column names. Replace:
```python
    cols_num = ["Potencial", "15% potencial", "Potencial mês (total)", "TOTAL 6M",
                "Corridas esperadas mês atual", "Dias em ativação", "% rampa mês atual"]
```
with:
```python
    cols_num = ["Potencial", "15% potencial", "Potencial mês (total)", "TOTAL 6M",
                "Corridas esperadas mês atual", "Dias em ativação", "% rampa mês atual",
                "Dias em rampagem"]
```

- [ ] **Step 11: Extend `_incompletos_expander` with a rampagem branch**

In `_incompletos_expander` (line 662), the row dict uses `aba == "negociacao"` to pick the etapa label and date. Replace the rows comprehension (lines 666–674):
```python
        rows = [{
            "Nome do negócio": d["dealname"], "Pipeline": d["pipeline_label"],
            "Etapa": _step_label(d) if aba == "negociacao" else "7. Ativação",
            "Proprietário": d["owner_name"],
            "Fechamento": fmt_data(d.get("previsao_fechamento") if aba == "negociacao"
                                   else d.get("closedate")),
            "Potencial": fmt_int(d["potencial"]),
            "Motivo": d.get("motivo_incompleto", "–"),
        } for d in incompletos]
```
with a 3-way branch on `aba`:
```python
        rows = []
        for d in incompletos:
            if aba == "negociacao":
                etapa = _step_label(d)
                data = fmt_data(d.get("previsao_fechamento"))
            elif aba == "rampagem":
                etapa = "RAMP UP"
                data = fmt_data(d.get("data_ativacao"))
            else:  # ativacao
                etapa = "7. Ativação"
                data = fmt_data(d.get("closedate"))
            rows.append({
                "Nome do negócio": d["dealname"], "Pipeline": d["pipeline_label"],
                "Etapa": etapa, "Proprietário": d["owner_name"],
                "Fechamento": data,
                "Potencial": fmt_int(d["potencial"]),
                "Motivo": d.get("motivo_incompleto", "–"),
            })
```
(Note: the column stays labeled "Fechamento" in the dataframe — consistent with the existing ativacao behavior, where closedate is shown under "Fechamento". If you want a clearer label for rampagem, that is a cosmetic follow-up, not required.)

- [ ] **Step 12: Extend `_render_consolidado` to sum 3 categories and take ramp_sel**

Replace `_render_consolidado` (lines 360–390) with:

```python
def _render_consolidado(neg_sel, ativ_sel, ramp_sel, meses, dark):
    total_6m = (sum(d["total_linha"] for d in neg_sel)
                + sum(d["total_linha"] for d in ativ_sel)
                + sum(d["total_linha"] for d in ramp_sel))
    n_neg = len(neg_sel); n_ativ = len(ativ_sel); n_ramp = len(ramp_sel)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total corridas (6 meses)", fmt_int(total_6m))
    k2.metric("Deals em negociação", n_neg)
    k3.metric("Deals em ativação", n_ativ)
    k4.metric("Deals em rampagem", n_ramp)

    st.markdown("#### Curva de forecast por mês (Negociação vs. Ativação vs. Rampagem)")
    st.plotly_chart(_stacked_bar_consolidado(neg_sel, ativ_sel, ramp_sel, meses),
                    use_container_width=True, config={"displayModeBar": False})

    st.markdown("#### Tabela consolidada por mês")
    rows = []
    for m in meses:
        vn = sum(d["volumes"].get(m, 0) for d in neg_sel)
        va = sum(d["volumes"].get(m, 0) for d in ativ_sel)
        vr = sum(d["volumes"].get(m, 0) for d in ramp_sel)
        rows.append({"Mês": mes_label(m), "Negociação": int(vn),
                     "Ativação": int(va), "Rampagem": int(vr),
                     "Total": int(vn + va + vr)})
    tot_vn = sum(r["Negociação"] for r in rows)
    tot_va = sum(r["Ativação"] for r in rows)
    tot_vr = sum(r["Rampagem"] for r in rows)
    rows.append({"Mês": "TOTAL 6 MESES", "Negociação": int(tot_vn),
                 "Ativação": int(tot_va), "Rampagem": int(tot_vr),
                 "Total": int(tot_vn + tot_va + tot_vr)})
    dfc = pd.DataFrame(rows)
    cc = {"Negociação": st.column_config.NumberColumn(format="%d"),
          "Ativação": st.column_config.NumberColumn(format="%d"),
          "Rampagem": st.column_config.NumberColumn(format="%d"),
          "Total": st.column_config.NumberColumn(format="%d")}
    st.dataframe(_zebra_styler(dfc, dark), column_config=cc,
                 use_container_width=True, hide_index=True)
```

- [ ] **Step 13: Update `_stacked_bar_consolidado` to take and plot 3 categories**

Replace `_stacked_bar_consolidado` (lines 680–699) with a version that takes `ramp_sel` and adds a 3rd `go.Bar` trace. The current impl uses `go.Bar` traces directly (not `px.bar`), with `theme.PIPELINE_COLORS_LIGHT` for colors:

```python
def _stacked_bar_consolidado(neg_sel, ativ_sel, ramp_sel, meses):
    labels = [mes_label(m) for m in meses]
    vn = [sum(d["volumes"].get(m, 0) for d in neg_sel) for m in meses]
    va = [sum(d["volumes"].get(m, 0) for d in ativ_sel) for m in meses]
    vr = [sum(d["volumes"].get(m, 0) for d in ramp_sel) for m in meses]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Negociação", x=labels, y=vn,
                         marker_color=theme.PIPELINE_COLORS_LIGHT["B2B Outbound"],
                         hovertemplate="%{x}<br>Negociação: %{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Bar(name="Ativação", x=labels, y=va,
                         marker_color=theme.PIPELINE_COLORS_LIGHT["B2B CSM Acquisition"],
                         hovertemplate="%{x}<br>Ativação: %{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Bar(name="Rampagem", x=labels, y=vr,
                         marker_color=theme.PIPELINE_COLORS_LIGHT["B2B Website Table"],
                         hovertemplate="%{x}<br>Rampagem: %{y:,.0f}<extra></extra>"))
    fig.update_layout(
        barmode="stack", height=300, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        font=dict(size=11), plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="rgba(0,0,0,0.08)", tickformat=",.0f"),
        xaxis=dict(showgrid=False),
    )
    return fig
```
(The Rampagem trace reuses the `B2B Website Table` color from `theme.PIPELINE_COLORS_LIGHT` — a 3rd distinct hue without needing a new theme entry. If `theme.PIPELINE_COLORS_LIGHT` does not have a "B2B Website Table" key, verify in `theme.py` and pick any available 3rd color; do not invent a new theme constant.)

- [ ] **Step 14: Update the footer caption to mention Rampagem**

Find the `st.caption(...)` at the end of `main()` (lines 208–216). Add a sentence about Rampagem. Replace:
```python
        f"Ativação: rampa desde o fechamento real (`closedate`). "
```
with:
```python
        f"Ativação: rampa desde o fechamento real (`closedate`). "
        f"Rampagem: rampa desde a entrada no stage RAMP UP (`hs_v2_date_entered_*`). "
```

- [ ] **Step 15: Run the full validation suite**

Run:
```bash
cd "G:/Drives compartilhados/B2B Planning (Sales Ops & Intelligence)/4. Planning/Marina/Rampagem/dash forecast acquisition" && PYTHONUTF8=1 python test_calc.py 2>&1 | tail -50
```
Expected: 0 exceptions, `Rampagem: 6`, all sanity `OK`, duplicidade 0, consolidated table has `ramp=` column, selfcheck 5.10 `ok`.

- [ ] **Step 16: Smoke-test the Streamlit app locally (headless import check)**

Run:
```bash
cd "G:/Drives compartilhados/B2B Planning (Sales Ops & Intelligence)/4. Planning/Marina/Rampagem/dash forecast acquisition" && PYTHONUTF8=1 python -c "
import app
print('app.py imports OK')
# verifica que as novas funções existem
for fn in ['_render_rampagem','_render_rampagem_15','_df_rampagem','_df_rampagem_15']:
    assert hasattr(app, fn), f'missing {fn}'
    print(f'  {fn}: OK')
"
```
Expected: `app.py imports OK` + 4 function checks `OK`. (If `import app` triggers Streamlit top-level code that requires a run context, wrap the check: the module must at least parse and define the functions.)

- [ ] **Step 17: Anti-leak scan + commit**

Run:
```bash
cd "G:/Drives compartilhados/B2B Planning (Sales Ops & Intelligence)/4. Planning/Marina/Rampagem/dash forecast acquisition" && git grep -n "pat-na1-<redacted>" -- . && echo "!!! LEAK" || echo "clean"
```
Expected: `clean`.

```bash
git add app.py
git commit -m "feat(rampagem): 2 abas novas + render/df/column_config + consolidado 3 categorias

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: README + final validation + push to fork

**Files:**
- Modify: `README.md` (document the Rampagem tab)

- [ ] **Step 1: Add a Rampagem section to the README**

In `README.md`, in the "Arquivos" table and "Decisões confirmadas" / "Regras de cálculo" sections, add rows/sections documenting: pipeline B2B Retention / stage RAMP UP; data-base = `hs_v2_date_entered_1412072536` (and the discovery that `hs_v2_*` IS returnable, unlike `hs_date_entered_*` v1); same curva; 2 tabs (total + 15%); Consolidado sums 3. Mirror the existing "Aba Ativação" documentation style.

- [ ] **Step 2: Final end-to-end validation**

Run:
```bash
cd "G:/Drives compartilhados/B2B Planning (Sales Ops & Intelligence)/4. Planning/Marina/Rampagem/dash forecast acquisition" && PYTHONUTF8=1 python test_calc.py 2>&1 | tail -40
```
Expected: 0 exceptions; 6 rampagem deals; sanity OK; duplicidade 0; selfcheck 5.10 ok; consolidated sums 3 categories.

- [ ] **Step 3: Anti-leak scan before push**

Run:
```bash
cd "G:/Drives compartilhados/B2B Planning (Sales Ops & Intelligence)/4. Planning/Marina/Rampagem/dash forecast acquisition" && (git grep -n "pat-na1-<redacted>" -- . && echo "!!! LEAK — NÃO PUSH" || echo "✓ clean")
```
Expected: `✓ clean`.

- [ ] **Step 4: Commit README and push everything to the fork**

```bash
cd "G:/Drives compartilhados/B2B Planning (Sales Ops & Intelligence)/4. Planning/Marina/Rampagem/dash forecast acquisition" && \
git add README.md && \
git commit -m "docs(rampagem): README — aba Rampagem + descoberta hs_v2_date_entered retornável

Co-Authored-By: Claude <noreply@anthropic.com>" && \
git pull --rebase origin main && \
git push origin main
```
Expected: push succeeds; Streamlit Cloud auto-redeploys in ~1 min.

- [ ] **Step 5: Confirm the live app shows the new tabs**

Open `https://forecast-acquisition-v9vr47dziyldkh8aqsgsht.streamlit.app/` (or the renamed URL). Verify: 7 tabs present; "Rampagem" tab shows 6 deals with "Data de ativação" column + 6-month volumes; "Rampagem Potencial Atualizado" shows the 15% column; Consolidado sums all 3.

---

## Self-Review Notes (for the implementer)

- **Type consistency:** `calcular_todos` returns a **5-tuple** `(neg, ativ, ramp, inc, meses)`. Every caller (`test_calc.py`, `selfcheck.py`'s own tests if any, `app.py` `main()`) must unpack 5 values. The signature change is the most common break point — verify all call sites.
- **`sc.run` is 7-arg** now: `run(neg, ativ, ramp, inc, meses, fetched_deals, hoje)`. Two callers: `test_calc.py` and `app.py` `main()`.
- **`_render_consolidado` is now 5-arg** (added `ramp_sel`): `_render_consolidado(neg_sel, ativ_sel, ramp_sel, meses, dark)`. Update the call in `main()`.
- **`_stacked_bar_consolidado`** signature changes too — read it before editing (Task 7 Step 10).
- **`deal["entrada_rampagem"]`** is the key for the data-base in rampagem deals (mirrors `entrada_ativacao`). `_df_rampagem` reads `d.get("entrada_rampagem")`.
- **`deal["dias_rampagem"]`** mirrors `dias_ativacao`. Both come from `calcular_todos`.
- **Don't redefine `_curva`** — rampagem reuses the existing one via `volume_por_mes_rampagem`.
