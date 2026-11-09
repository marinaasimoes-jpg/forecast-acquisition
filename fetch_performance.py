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
      linha1 (idx0): headers (Owner=col0, Company Name=col1, Activation
              Date=col2, Potential=col3, Forecast=col4..9, Actual <Mês>=col10,
              % Achievement=col11..)
      linha2 (idx1): sub-headers de mês (August/2026 etc.) nas col4..9
      linha3+ (idx2+): dados por empresa
    'Forecast' daquele mês (a meta planilha) está em col4..9 conforme o mês
    da aba; 'Actual' (realizado) está em col10.
    """
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    registros = []
    try:
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
    finally:
        wb.close()
    return registros


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
