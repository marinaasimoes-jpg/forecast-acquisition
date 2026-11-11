# -*- coding: utf-8 -*-
"""Camada de coleta do REALIZADO (corridas feitas) — Fase 3.

Substitui o fetch_performance (planilha manual da Fase 2) pela consulta direta
ao BigQuery da 99/Didi: tabela final_report (corrida-a-corrida, 2024-01..hoje).
O dashboard.py não muda — este módulo devolve o MESMO formato que
fetch_performance.performance_por_deal, só trocando a fonte (planilha → BQ) e
a chave de match (nome → company_id curado em config.DEAL_PARA_COMPANY_IDS_99).

Caminho: Deal em rampa (HubSpot) → dealname → config.DEAL_PARA_COMPANY_IDS_99
→ [company_id na 99] → SELECT no final_report GROUP BY year, month →
{deal_id: {mes: {"realizado": n}}}.

Decisões de design (validadas com a Marina, 2026-11-11):
  - 0 corridas = realizado 0 (NÃO vai pro "sem acompanhamento"; 0 é um dado).
    Só vai pro sem-acompanhamento o deal sem company_id mapeado.
  - Histórico completo: todos os meses disponíveis no BQ (2024-01..hoje).
  - Conta TODAS as corridas do company_id (callplatform app/api/web/webapp),
    não só 'api' — volume total da empresa na 99.

Credencial: service account JSON em config.BQ_CRED_PATH (fora do repo, nunca
commitada). No Streamlit Cloud, precisa do arquivo lá + a var de ambiente
GOOGLE_APPLICATION_CREDENTIALS apontando pra ele (ver notas de deploy).
"""
import datetime as dt
import json

from google.cloud import bigquery
from google.oauth2 import service_account

import config


def _client():
    """Constrói o cliente BigQuery a partir da service account.

    Dois modos (a presença do secret decide — sem if de ambiente explícito):
      1. Streamlit Cloud: lê o JSON da service account de st.secrets
         ["bq_service_account"] (string JSON definida nos secrets do app).
         NUNCA commitada — ver memória forecast-acquisition-token-security.
      2. Local: lê o arquivo em config.BQ_CRED_PATH (no Drive, fora do repo).

    Mantido em função (não no escopo do módulo) pra não conectar no import —
    só no uso real, evitando custo/latência em testes/smoke que só importam.
    """
    # Tenta o secret do Streamlit (Cloud). st.secrets só existe com runtime.
    try:
        import streamlit as st
        sa_json = st.secrets.get("bq_service_account")
    except Exception:
        sa_json = None
    if sa_json:
        info = _parse_sa_json(sa_json)
        creds = service_account.Credentials.from_service_account_info(info)
    else:
        creds = service_account.Credentials.from_service_account_file(
            config.BQ_CRED_PATH)
    return bigquery.Client(credentials=creds, project=config.BQ_PROJECT)


def _parse_sa_json(sa_json):
    """Parseia o JSON da service account vindo do st.secrets, tolerante ao
    gotcha das aspas triplas duplas.

    Se o secret foi colado com aspas triplas DUPLAS (\"\"\"), o TOML converte
    os '\\n' da private_key em quebras de linha reais -> JSON inválido
    (JSONDecodeError: Invalid control character). Com aspas triplas SIMPLES
    (''') funciona direto. Aqui cobrimos os dois: se o json.loads direto
    falhar, normalizamos as quebras reais dentro do campo private_key de
    volta pra '\\n' (dois chars) e re-tentamos. Assim o secret funciona com
    qualquer um dos dois formatos — não depende da Marina acertar o tipo de
    aspas. Ver memória fase3-corridas-99-api.
    """
    if isinstance(sa_json, dict):
        return sa_json  # já é um dict (st.secrets pode ter parseado)
    try:
        return json.loads(sa_json)
    except json.JSONDecodeError:
        # gotcha do \"\"\": private_key veio com quebras reais. Recoloca \\n.
        import re
        # pega o conteúdo entre "private_key": " ... " (inclusive o header/footer)
        fixed = re.sub(
            r'("private_key"\s*:\s*")(.*?)(")',
            lambda m: m.group(1) + m.group(2).replace("\n", "\\n") + m.group(3),
            sa_json, flags=re.DOTALL)
        return json.loads(fixed)


def _query_corridas_por_empresa(company_ids):
    """Conta corridas por (company_id, ano, mês) no final_report.

    Retorna lista de dicts: {company_id, mes: date(1º), realizado: int}.
    Só inclui (company_id, mês) com >=1 corrida — meses sem corrida não vêm
    (quem precisa de 0 explícito trata fora, ver performance_por_deal_bq).
    """
    if not company_ids:
        return []
    sql = f"""
    SELECT
      company_id,
      year,
      month,
      COUNT(*) AS corridas
    FROM `{config.BQ_PROJECT}.{config.BQ_DATASET}.{config.BQ_TABLE}`
    WHERE company_id IN UNNEST(@ids)
    GROUP BY company_id, year, month
    """
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ArrayQueryParameter("ids", "INT64", list(company_ids)),
    ])
    client = _client()
    rows = client.query(sql, job_config=cfg, location="US").result()
    return [{
        "company_id": int(r.company_id),
        "mes": dt.date(int(r.year), int(r.month), 1),
        "realizado": int(r.corridas),
    } for r in rows]


def _deal_para_company_ids(deal):
    """Resolve um deal → [company_id] na 99 via config.DEAL_PARA_COMPANY_IDS_99.
    Casamento por dealname EXATO (chave do dict). Retorna [] se não mapeado."""
    ids = config.DEAL_PARA_COMPANY_IDS_99.get(deal["dealname"])
    return list(ids) if ids else []


def performance_por_deal_bq(deals_rampagem):
    """Análogo a fetch_performance.performance_por_deal, mas fonte = BigQuery.

    Retorna (por_deal, mes_corrente, sem_acompanhamento):
      por_deal: {deal_id: {mes(date): {"meta_planilha": None,
                                       "realizado": int}}}
        — meta_planilha=None (a meta oficial vem do calc_forecast; aqui só
        o realizado, que é o que o BQ sabe). realizado somado sobre todos os
        company_ids mapeados daquele deal (um grupo pode ter N empresas na 99).
      mes_corrente: date (1º do mês) = mês mais recente entre todos os
                    registros, ou None se nenhum.
      sem_acompanhamento: deals em rampa SEM company_id mapeado no config
                          (não tem como puxar corrida — falta a tradução).
                          Deals mapeados com 0 corridas NÃO entram aqui (0 é
                          um dado, não falta).
    """
    # 1. resolve company_ids de todos os deals mapeados
    deal_to_ids = {}
    todos_ids = []
    for d in deals_rampagem:
        ids = _deal_para_company_ids(d)
        if ids:
            deal_to_ids[d["deal_id"]] = ids
            todos_ids.extend(ids)

    # 2. puxa corridas do BQ (1 query, todos os ids)
    registros = _query_corridas_por_empresa(todos_ids) if todos_ids else []

    # 3. indexa corridas por company_id → {mes: realizado}
    por_cid = {}
    for r in registros:
        por_cid.setdefault(r["company_id"], {})[r["mes"]] = r["realizado"]

    # 4. monta por_deal: soma os meses de todos os company_ids do deal
    por_deal = {}
    for d in deals_rampagem:
        ids = deal_to_ids.get(d["deal_id"])
        if not ids:
            continue
        meses = {}
        for cid in ids:
            for mes, real in por_cid.get(cid, {}).items():
                meses[mes] = meses.get(mes, 0) + real
        # mesmo se meses vazio (0 corridas em todo o histórico), registra o
        # deal com dict vazio → aparece no dashboard com realizado "–"/0,
        # mas NÃO no sem_acompanhamento (deal mapeado, só não correu).
        if meses:
            por_deal[d["deal_id"]] = {
                mes: {"meta_planilha": None, "realizado": real}
                for mes, real in meses.items()
            }
        else:
            por_deal[d["deal_id"]] = {}

    # 5. mês corrente = mês mais recente entre todos os registros do BQ
    meses_com_dado = [r["mes"] for r in registros if r["mes"] is not None]
    mes_corrente = max(meses_com_dado) if meses_com_dado else None

    # 6. sem_acompanhamento = deals SEM company_id mapeado
    sem_acompanhamento = [d for d in deals_rampagem
                          if d["deal_id"] not in deal_to_ids]
    return por_deal, mes_corrente, sem_acompanhamento
