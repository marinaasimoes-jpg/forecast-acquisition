# Design — Fase 2: Acompanhamento meta vs. realizado (tab Rampagem)

**Data:** 2026-11-03 (brainstorm), spec escrita 2026-11-06
**Autor:** brainstorm Marina + Claude
**Fase:** 2 de 2. Fase 1 (divisão em 2 lentes) já em produção (commit `95d570f`).
**Spec anterior:** `2026-11-03-divisao-2-lentes-design.md`

## Contexto

O dashboard hoje mostra só o **forecast** (meta = potencial × curva). A Marina
quer mostrar também o **realizado** (corridas de fato feitas) e comparar os dois,
empresa a empresa, mês a mês — o "% achievement".

A performance que se compara é **vs. o forecast de rampagem** — as empresas já
em rampa (stage RAMP UP do B2B Retention), que são as mesmas 7 empresas da
planilha `Acompanhamento Linda`. Negociação e Ativação não têm realizado pra
comparar (ainda não operam). Por isso o acompanhamento vive **na tab Rampagem**.

## Decisões de design (validadas com a Marina)

1. **Fonte do realizado (fase atual): planilha Excel.** As corridas realizadas
   estão nas bases internas da 99 (via Supabase/Postgres), MAS o plugin Supabase
   MCP (v0.1.12) está com OAuth `client_id` rejeitado ("Unrecognized client_id")
   — não dá pra conectar agora. Solução: o dashboard lê a planilha
   `Acompanhamento_Rampagem.xlsx` (a mesma que a Marina já mantém). Migração
   pra Supabase fica pendente (ver memória `performance-fonte-supabase-pendente`).
2. **Planilha no repo (Opção 1).** O .xlsx é commitado em `data/` no repo (o
   Streamlit Cloud lê do filesystem do próprio repo). Script
   `atualizar_performance.py` faz `git add + commit + push` num comando quando a
   Marina cola o Actual. Defeito aceito: dado comercial de baixa sensibilidade
   (nomes de empresa + contagem de corridas, sem credencial) fica no repo
   público — mesmo patamar do que já está lá (`dealname` em docs/exemplos).
3. **Abordagem 1 (código junta as abas).** A Marina continua criando uma aba
   `Acompanhamento Linda MMaaaa` por mês (fluxo atual). O `fetch_performance`
   lê todas as abas `Acompanhamento Linda *`, extrai `(empresa, mês, meta,
   realizado)` e monta uma lista unificada. Histórico cresce organicamente.
4. **Acompanhamento na tab Rampagem, como colunas novas.** Não é página nova,
   não é seletor. A tab Rampagem (dentro das lentes Total e 15%) ganha colunas
   novas no fim da linha de cada empresa.
5. **Mês corrente = mês mais recente que existe na planilha** (não o mês
   calendário de hoje). Se a planilha tem até agosto, a coluna mostra agosto.
   Quando a Marina cola setembro, pula pra setembro. Tolerante a "ainda não
   colou".
6. **Histórico no expander por empresa.** A coluna mostra só o mês corrente;
   ao clicar na empresa, um expander abre o histórico mês a mês (meta |
   realizado | %) desde o primeiro mês com dado. Anti-poluimento visual.
7. **Ordem das colunas (decisão da Marina):** `% atingimento` primeiro,
   `Realizado` depois, ambas logo após a coluna Empresa (antes dos meses).
   `TOTAL 6M` continua no fim. Ordem completa:
   `Empresa | % atingimento | Realizado | ago | set | out | nov | dez | jan | TOTAL 6M`.
   (Incomum — % antes do realizado — mas é a ordem pedida; `st.dataframe`
   permite ordenação por clique em qualquer coluna.)
8. **Realizado é o mesmo nas duas lentes; o % muda.** Na lente Total, % =
   realizado ÷ meta_total. Na 15%, % = realizado ÷ meta_15. O número de
   corridas realizadas é um fato (não muda com a lente); o denominador (meta)
   muda. Mesmo princípio "duas lentes, mesmo dado" da Fase 1.

## Estrutura de arquivos (após)

| Arquivo | Responsabilidade | Estado |
|---|---|---|
| `fetch_performance.py` | NOVO. Lê `data/Acompanhamento_Rampagem.xlsx`, acha abas `Acompanhamento Linda *`, extrai `(empresa, mês, meta, realizado)` por empresa. Devolve lista de registros unificada. Isolado — fácil de migrar pra Supabase depois (troca só este módulo). | **NOVO** |
| `calc_forecast.py` | Adiciona helper `meta_de_mes_rampagem(deal, mes_alvo)` — calcula a meta de **qualquer mês** desde a entrada no RAMP UP (fora da janela de 6 meses), reusando `_curva` + `_fator_proporcional`. Sem alterar as funções existentes. | **MODIFICADO (aditivo)** |
| `config.py` | Adiciona `PATH_PLANILHA_PERFORMANCE = "data/Acompanhamento_Rampagem.xlsx"` e `EXCECOES_MATCH_NOME = {"Voetur": "Grupo Voetur", ...}` (tabela de exceções de match nome↔dealname). | **MODIFICADO (aditivo)** |
| `dashboard.py` | `_df_rampagem` / `_df_rampagem_15` ganham as colunas `% atingimento` + `Realizado` após Empresa. `_render_rampagem` / `_render_rampagem_15` ganham o expander de histórico por empresa + a seção "Deals sem acompanhamento na planilha". | **MODIFICADO** |
| `data/Acompanhamento_Rampagem.xlsx` | A planilha (copiada do Drive, commitada no repo). | **NOVO** |
| `atualizar_performance.py` | Script: depois de a Marina colar o Actual na planilha, roda este script → `git add data/Acompanhamento_Rampagem.xlsx` + `commit "performance: atualizar realizado MM/aaaa"` + `push`. | **NOVO** |
| `app.py`, `pages/*`, `fetch_hubspot.py`, `theme.py`, `selfcheck.py`, `test_calc.py` | Inalterados (estrutura multipage da Fase 1 intacta). | **INALTERADOS** |

## `fetch_performance.py` — leitura da planilha + match

### Leitura
- `ler_performance(path=PATH_PLANILHA_PERFORMANCE)`:
  - Abre o `.xlsx` com `openpyxl` (read_only, data_only).
  - Acha todas as abas cujo nome começa com `Acompanhamento Linda`.
  - De cada aba, extrai o mês do nome (`082026` → `2026-08`) e, por linha de
    empresa, `(Company Name, mês, Potential, Forecast[aquele mês], Actual)`.
  - Devolve lista de dicts: `{"empresa_planilha": str, "mes": date(first-of-month),
    "meta_planilha": float, "realizado": float|None}`.
- Cache: `@st.cache_data(ttl=900)` (igual ao `get_data`), chaveado por path +
  mtime do arquivo (pra invalidar quando a planilha for atualizada).

### Match empresa planilha ↔ HubSpot
- `normalizar_nome(s)`: lowercase, sem acento, sem "Food Service"/"LTDA"/"Ltda",
  trim. "Dellys Food Service" → "dellys".
- `casa_nome_para_dealname(empresa_planilha, deals_rampagem)`:
  1. Tenta `EXCECOES_MATCH_NOME[empresa_planilha]` → se mapeia pra um dealname,
     casa direto.
  2. Senão, normaliza `empresa_planilha` e cada `deal.dealname`, casa se
     normalizados forem iguais.
  3. Senão, retorna `None` → vira "Deals sem acompanhamento".
- **Sem fuzzy matching automático.** Caso não case, sinaliza (igual aos
  "incompletos") — a Marina adiciona na `EXCECOES_MATCH_NOME` e re-deploya.
  Preferível a casar errado silenciosamente.

### Mapeamento deal → performance
- `performance_por_deal(deals_rampagem, registros)`:
  - Pra cada deal em rampa, encontra (via match) seus registros de performance.
  - Devolve `{deal_id: {mes: {"meta_planilha": x, "realizado": y}}}`.
  - Determina `mes_corrente = max(mes) entre todos os registros` (mês mais
    recente que existe na planilha — decisão 5). **É o mesmo pra todas as
    empresas** (o mês mais recente da planilha inteira, não por empresa). Uma
    empresa que não tem registro naquele `mes_corrente` (só em meses
    anteriores) → a coluna "Realizado" mostra `–` e o "%" mostra `–` (mesmo
    padrão de dado ausente).

## `calc_forecast.py` — helper `meta_de_mes_rampagem`

```python
def meta_de_mes_rampagem(deal, mes_alvo, hoje):
    """Meta de forecast de rampagem para um mês qualquer (dentro ou fora da
    janela de 6 meses). Reusa _curva + _fator_proporcional.

    mes_alvo: date(first-of-month). Retorna float (meta sobre potencial do
    deal — potencial total OU potencial_15 conforme o deal passado).
    """
```

- Calcula o offset (mes_alvo − mes_da_entrada) em meses.
- Se offset < 0 (mês anterior à entrada): meta = 0.
- Se offset dentro da curva: `potencial * curva[offset]` (com proporcionalidade
  por dia se offset==0).
- Se offset após a curva: `potencial * 1.0` (100%, carry-forward).
- **Usa o `potencial` do deal passado.** Na lente Total, passa o deal com
  potencial original; na 15%, passa o deal 15% (já calculado em `neg_15` etc.).
  Mesmo helper, denominador diferente por lente.

## `dashboard.py` — colunas novas + expander

### `_df_rampagem` / `_df_rampagem_15`
- Após a coluna Empresa, inserir duas colunas:
  - `% atingimento`: `fmt` percentual (ex.: "81%") ou `–` se sem realizado.
  - `Realizado`: int (ex.: "60") ou `–`.
- Antes dos meses (ago/jan...). `TOTAL 6M` continua ao final.
- Valor: `realizado = performance_por_deal[deal_id][mes_corrente]["realizado"]`;
  `meta = meta_de_mes_rampagem(deal, mes_corrente)`; `% = realizado / meta`.

### `_render_rampagem` / `_render_rampagem_15`
- Após a tabela principal, um **expander por empresa clicada** mostra o
  histórico: `mes | meta | realizado | %`, mês a mês, desde o primeiro
  registro. (Reuso do padrão do `_incompletos_expander`.)
- Novo expander **"Deals sem acompanhamento na planilha"**: deals em rampa no
  HubSpot que não casaram com nenhuma empresa da planilha — lista o dealname +
  sugestão ("adicionar em EXCECOES_MATCH_NOME").

### Lentes (Total e 15%)
- A coluna e o expander aparecem em ambas. O realizado é o mesmo; a meta e o %
  diferem (a lente passa o deal com potencial correspondente pra
  `meta_de_mes_rampagem`).

## Cache e deploy
- `fetch_performance.ler_performance` cacheado (15 min, chave = path + mtime).
- A planilha é lida do filesystem do repo (`data/Acompanhamento_Rampagem.xlsx`)
  — funciona local e no Cloud.
- `atualizar_performance.py`: roda localmente depois de colar o Actual; faz
  `git add + commit + push` — o Cloud redeploya e o novo realizado aparece.

## Gotchas
- **Mês corrente = mês mais recente da planilha** (não mês calendário). Tolerante
  a "ainda não colou". Se a planilha não tem nenhuma aba `Acompanhamento Linda`,
  a coluna mostra `–` pra todos + expander "nenhum dado de performance ainda".
- **Match por nome é frágil.** A `EXCECOES_MATCH_NOME` vai crescer conforme
  aparecerem "não casados". Cada novo mapeamento = commit + redeploy.
- **Deploy após colar:** rodar `atualizar_performance.py` (ou `git add + commit
  + push` manual) depois de colar o Actual. Sem isso, o Cloud não vê o novo
  realizado. Igual ao workflow de push da Fase 1.
- **`meta_de_mes_rampagem` é novo, isolado.** Não altera `volume_por_mes_rampagem`
  (que continua calculando só a janela de 6 meses). O acompanhamento usa o
  helper novo pra meta de qualquer mês.

## Escopo desta fase
- ✅ `fetch_performance.py` (ler planilha + match por nome + exceções).
- ✅ `meta_de_mes_rampagem` helper em `calc_forecast.py`.
- ✅ Colunas `% atingimento` + `Realizado` na tab Rampagem (ambas as lentes).
- ✅ Expander de histórico por empresa.
- ✅ Expander "Deals sem acompanhamento".
- ✅ Planilha em `data/` + script `atualizar_performance.py`.

### Fora de escopo
- ❌ Migração pra Supabase/Postgres (pendente — plugin Supabase com OAuth
  rejeitado; ver memória `performance-fonte-supabase-pendente`).
- ❌ Filtros novos (faixa de %, mês específico) — a coluna+expander resolvem o
  anti-poluimento; filtros extra ficam pra fase futura se necessário.
- ❌ Acompanhamento em Negociação/Ativação (não há realizado pra essas).

## Teste/validação
- `test_calc.py`: adicionar teste do `meta_de_mes_rampagem` (mês dentro da
  janela, mês antes da entrada, mês após a curva, M1 proporcional).
- `test_calc.py` ou `selfcheck.py`: validar o `fetch_performance` lendo a
  planilha real (`data/Acompanhamento_Rampagem.xlsx`) — confirmar 7 empresas,
  mês de agosto, números coerentes com a aba `Acompanhamento Linda 082026`.
- Validação do match: rodar localmente, confirmar que as 7 empresas casam (ou
  sinalizar quais não casaram → adicionar em `EXCECOES_MATCH_NOME`).
- Smoke test: `streamlit run app.py`, ir na tab Rampagem (Total e 15%),
  confirmar colunas novas, % coerente, expander de histórico, e expander de
  "sem acompanhamento" (vazio se todas casaram).
