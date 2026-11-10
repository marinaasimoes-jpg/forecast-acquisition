# -*- coding: utf-8 -*-
"""Script de atualização mensal do acompanhamento.

Depois de colar o 'Actual' na planilha data/Acompanhamento_Rampagem.xlsx
(criando/atuando a aba 'Acompanhamento Linda MMaaaa'), rode:

    python atualizar_performance.py

Faz git add + commit + push da planilha, disparando o redeploy do
Streamlit Cloud. Não mexe em código, só no dado da planilha.

Pré-validação: antes de pushar, confirma que a planilha continua legível
(ver validar_antes_de_pushar) — evita pushar um arquivo quebrado e
derrubar o dashboard no Cloud.
"""
import subprocess
import sys

import fetch_performance as fp

PATH = "data/Acompanhamento_Rampagem.xlsx"


def validar_antes_de_pushar():
    """Roda antes do git add+commit+push. Retorna (ok: bool, msg: str).

    Deve pegar problemas que, se pushados, quebrariam o dashboard no Cloud
    (onde não dá pra debugar fácil). Falhar aqui é barato; falhar no Cloud
    é caro.

    Nível: confirma que a planilha abre + que há registros + que pelo menos
    1 tem realizado numérico. Pega as duas falhas silenciosas totais (aba
    errada → []; Actual colado como texto → tudo None). Deixa passar o
    parcial (5 de 7 com realizado) — mês em andamento é normal.
    """
    try:
        regs = fp.ler_performance(PATH)
    except Exception as e:
        return False, f"planilha não abre ({type(e).__name__}: {e})"
    if not regs:
        return False, "nenhuma aba 'Acompanhamento Linda *' válida (nome da aba está errado?)"
    com_real = [r for r in regs if r["realizado"] is not None]
    if not com_real:
        return False, "0 realizados numéricos (colou texto no Actual?)"
    return True, f"{len(regs)} regs, {len(com_real)} com realizado"


def _run(cmd):
    """Roda um comando, ecoa, e aborta a cadeia se falhar."""
    print(f"$ {' '.join(cmd)}")
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print(f"comando falhou (código {r.returncode}). Pare e verifique.")
        sys.exit(r.returncode)


def main():
    ok, msg = validar_antes_de_pushar()
    if not ok:
        print(f"✗ Validação falhou: {msg}")
        print("  Planilha NÃO foi pushada. Corrija e rode de novo.")
        sys.exit(1)
    print(f"✓ Validação ok: {msg}")

    msg = input("Mensagem do commit (Enter p/ padrão 'performance: atualizar realizado'): ").strip()
    if not msg:
        msg = "performance: atualizar realizado"
    msg += "\n\nCo-Authored-By: Claude <noreply@anthropic.com>"

    _run(["git", "add", PATH])
    _run(["git", "commit", "-m", msg])
    _run(["git", "push"])
    print("✓ Planilha atualizada e pushada. O Cloud vai redeployar.")


if __name__ == "__main__":
    main()
