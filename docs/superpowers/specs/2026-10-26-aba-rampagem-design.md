# Aba Rampagem — Design Spec

**Data:** 2026-10-26
**Status:** Aprovada para implementação (após revisão)
**Dashboard:** Monthly Commercial Planning (`marinaasimoes-jpg/forecast-acquisition`)

## 1. Objetivo

Adicionar ao dashboard a **3ª categoria de forecast**: Rampagem — projeção de
volume de corridas dos clientes **já em rampa** (ativados, subindo a curva até o
potencial). Hoje o dashboard tem Negociação (4/5/6) e Ativação (7). Rampagem
completa o trio: cliente já entrou em operação e está rampando.

Estrutura final: **7 abas** (Negociação, Negociação 15%, Ativação, Ativação 15%,
Rampagem, Rampagem 15%, Consolidado). Consolidado passa a somar as 3 categorias.

## 2. Contexto validado contra a realidade (HubSpot + Excel)

Tudo abaixo foi confirmado por chamadas reais à API do HubSpot (token no env)
e leitura do `Acompanhamento_Rampagem - FINAL.xlsx`:

### 2.1 Pipeline e stage
- **Pipeline:** `B2B Retention` (id `922791528`), objectType `deals`.
- **Stage:** `RAMP UP` (id `1412072536`, displayOrder 0, archived=false).
  - Demais stages do Retention (`RETENTION` `1412072538`, `RECOVERY`
    `1412072260`) **fora do escopo** — cliente estabilizado/em recuperação é
    outro ciclo de vida.
- **6 deals** no stage RAMP UP hoje: Sintetel- Voucher, Grupo Voetur, Milky
  Moo, BTM (Voll), Dellys Food Service, MKT Digital e Social - Promocode.
  Todos com `share_vs_potencial_total` e `closedate` populados.

### 2.2 Data-base da rampa (descoberta-chave)
A spec original considerava "data de ativação (prop própria)". Investigação
mostrou que:
- **Não existe** prop simples "Data de ativação" populada. As candidatas
  `data_de_expectativa_de_go_live` e `estimativa_cft` estão **vazias em
  todos os 6** deals (0 populadas / 6).
- **"Data da 1ª corrida"** (ideal) **não é acessível** — o token de Private App
  não tem scope p/ objetos custom/schemas (`/schemas` retorna 0; corridas são
  transacionais, vivem fora do CRM).
- **`hs_v2_date_entered_1412072536`** (timestamp de entrada no stage RAMP UP)
  **É retornável** pela CRM Search API v3 e está **populada em 6/6** deals.
  - Quebra a limitação documentada no README ("`hs_date_entered_<id>` não é
    retornável") — a variante **`hs_v2_`** sim é.

**Decisão:** data-base da rampa = `hs_v2_date_entered_1412072536` (entrada no
stage RAMP UP). É a melhor proxy de "início da rampagem" disponível sem
necessitar novo scope/admin. Conceitualmente superior ao `closedate`: um deal
pode ficar semanas no stage "7. Ativação" antes de migrar pra RAMP UP, e
`closedate` faria a rampa começar no fechamento (impreciso).

### 2.3 Curva
Idêntica às outras abas (validado contra a aba "Racional" do Excel):
`_curva(potencial)`: potencial < 20.000 → `[0.25, 0.5, 1.0]`; ≥ 20.000 →
`[0.25, 0.5, 0.75, 1.0]`. Corte `LIMITE_POTENCIAL_ALTO = 20000`.
Carry-forward 100% após o teto.

### 2.4 Sem performance observada
Conforme decisão do usuário, **ignorar** as colunas "Atual" e "%Achieved" do
Excel. A aba Rampagem é **projeção pura** com base no potencial, igual a
Negociação e Ativação. Sem fonte externa, sem upload, 100% live do HubSpot.

## 3. Arquitetura (reaproveita o padrão existente)

A rampagem segue a **mesma 3-camada** das outras abas. Mudanças por arquivo:

### 3.1 `config.py` — novas constantes
```python
PIPELINE_B2B_RETENTION = "922791528"
STAGE_RAMP_UP = "1412072536"
PROP_DATA_ATIVACAO_RAMPAGEM = "hs_v2_date_entered_1412072536"
```
(Convenção fixa: IDs descobertos pelo label, não assumidos. Já validados.)

### 3.2 `fetch_hubspot.py` — nova busca
+1 query de deals: `dealstage == STAGE_RAMP_UP` (pipeline Retention). Mesma
estrutura da busca de Ativação (stage 7), pedindo as props:
`dealname`, `share_vs_potencial_total`, `closedate`, `previsao_de_fechamento`,
`hubspot_owner_id`, `pipeline`, `dealstage`, e **`hs_v2_date_entered_1412072536`**.
Retorna deals marcados com `step = 8` (convenção: 7=Ativação, 8=Rampagem),
mesmo esquema de `step` que `calcular_todos` já usa pra distinguir Ativação.
A partição em `calcular_todos` checa `step == 8` (ver §3.4).

### 3.3 `calc_forecast.py` — nova função de cálculo
+`volume_por_mes_rampagem(deal, meses, hoje)` — espelha
`volume_por_mes_ativacao`, com a única diferença: a data-base é
`deal["data_ativacao"]` (preenchido com `hs_v2_date_entered_1412072536` pelo
fetch), **não** `deal["closedate"]`.

Lógica (idêntica à Ativação, só troca a data-base):
- M1 = mês calendário da data de ativação, volume = `potencial × 25% ×
  (dias_ativos / dias_no_mês)` (proporcional por dia, via `_fator_proporcional`).
- Se M1 está **antes** da janela: a rampa já começou no passado — descobrir o
  offset da curva que cai no primeiro mês da janela (carry-forward). Deal que
  entrou há 3 meses já aparece em 100% hoje. (Mesma lógica de
  `volume_por_mes_ativacao` linhas 231-243.)
- Se M1 está **depois** da janela (data de ativação futura): zerado, registra
  a data p/ exibir.
- Após atingir 100% (offset ≥ len(curva)): permanece 100% nos meses restantes.

+`calcular_rampagem_15(rampagem, meses, hoje)` — wrapper fino espelhando
`calcular_ativacao_15`: `pot15 = round(potencial × 0.15)`, re-chama
`volume_por_mes_rampagem` com `{**d, "potencial": pot15}` (curva reavaliada
pelo pot15). Preserva `d["potencial"]` original, guarda `d["potencial_15"]`.

+`_calc_rampagem_15_safe(...)` — wrapper de diagnóstico espelhando
`_calc_ativacao_15_safe` (catch + iterar deal-a-deal + RuntimeError com
dealname/campos/tipo-erro). Razão: Streamlit Cloud redacta exceções no
traceback público.

### 3.4 `calcular_todos(deals, hoje)` — nova partição
Hoje particiona em `(negociacao, ativacao, incompletos)`. Passa a
`(negociacao, ativacao, rampagem, incompletos)`:
- `step == 8` (ou origem rampagem) → rampagem. Data-base exigida:
  `data_ativacao` (não `closedate`). Sem potencial OU sem `data_ativacao` →
  incompletos com `motivo_incompleto` citando "data de ativação (entrada no
  Ramp Up)".
- `_motivo_incompleto` ganha ramo rampagem.

### 3.5 `app.py` — 2 abas novas + Consolidado
- `st.tabs([...])` passa de 5 pra 7 elementos: `Negociação, Negociação
  Potencial Atualizado, Ativação, Ativação Potencial Atualizado, Rampagem,
  Rampagem Potencial Atualizado, Consolidado`.
- +`_render_rampagem(sel, meses, ...)` e +`_render_rampagem_15(sel, meses, ...)`
  espelhando `_render_ativacao`/`_render_ativacao_15`.
- +`_df_rampagem(rampagem, meses)` e +`_df_rampagem_15(...)`: colunas = KAM,
  Cliente, Pipeline, **Data de ativação**, Potencial, (15% potencial na aba
  15%), TOTAL 6M, + 6 meses. `_tabela_principal(..., aba="rampagem")` e
  `aba="rampagem_15"` ganham ramos em `_column_config`.
- Consolidado: tabela mês × (Negociação, Ativação, **Rampagem**, Total) e
  KPI 6 meses somando as 3.

### 3.6 `test_calc.py` + `selfcheck.py`
+`sanity_test_rampagem()` (deal fictício: 10k entrando hoje → M1 proporcional;
10k entrou há 3 meses → 100% hoje; 30k → curva 4 meses) espelhando
`sanity_test_ativacao`. +verificações no `selfcheck.py` (estrutura, contagem,
consolidado com rampagem).

## 4. Renderização — colunas da aba Rampagem

Modelo 1 (mínimo, espelha Negociação) + coluna "Data de ativação":

| Coluna | Conteúdo | Tipo |
|---|---|---|
| KAM | `hubspot_owner_id` → nome via Owners API | texto |
| Cliente | `dealname` | texto |
| Pipeline | label do pipeline ("B2B Retention") | texto/chip |
| Data de ativação | `hs_v2_date_entered_1412072536` → `dt.date` | data |
| Potencial | `share_vs_potencial_total` (original) | número |
| 15% potencial | `round(potencial × 0.15)` (**só na aba 15%**) | número |
| TOTAL 6M | soma dos 6 meses | número |
| Mês 1..6 | volume por mês da janela | número (ordenável) |

Incompletos: expander "Deals com dados incompletos" (igual às outras abas),
motivo "Faltando: data de ativação (entrada no Ramp Up) e/ou potencial mês".

## 5. Fronteira de escopo (sem sobreposição)

- **Negociação** (4/5/6): ainda vai fechar.
- **Ativação** (7): fechou, CSM ainda não ativou.
- **Rampagem** (RAMP UP do Retention): já ativou, em rampa.
Um deal migra: aquisição (4→5→6→7) → Retention (RAMP UP). Quando sai do
stage 7 e entra no RAMP UP, muda de aba. **Nenhuma duplicação** entre abas
— cada deal está em exatamente um stage de cada vez.

## 6. Decisões explícitas e porquês

1. **Data-base = `hs_v2_date_entered_1412072536`** (não `closedate`, não
   go_live): única prop retornável + populada + conceitualmente correta.
2. **Sem "Atual"/"%Achieved"**: projeção pura, consistente com as irmãs;
   performance observada seria escopo separado (fonte externa).
3. **2 abas (total + 15%)**: espelha o padrão "Atualizado" existente;
   `calcular_rampagem_15` reusa a mesma função de cálculo.
4. **Consolidado soma as 3**: visão unificada do forecast comercial.
5. **Probabilidade 100%** (não usa `probability=0.9` do stage): convenção
   fixa do `/forecast` — não pondera por etapa.
6. **Stage 8 / origem rampagem**: novo marcador interno pra distinguir de
   Ativação (7) na partição.

## 7. Fora de escopo (YAGNI)

- Performance observada ("Atual"/"%Achieved") — v2 futura, exige fonte externa.
- Stages RETENTION e RECOVERY do pipeline Retention — outro ciclo de vida.
- Heatmap cosmético nos meses (mesma limitação do restante do dashboard —
  `BarColumn` indisponível na versão do Streamlit em uso).
- Reagrupar abas por categoria — muda navegação existente, sem ganho real.
- Refinar a data-base da aba Ativação existente p/ `hs_v2_date_entered_*`
  (embora agora saibamos que é possível) — escopo separado, não mexer no
  que funciona.

## 8. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Deal em RAMP UP sem `hs_v2_date_entered_1412072536` | Vai pra incompletos com motivo claro (validado: 0/6 faltando hoje). |
| `hs_v2_date_entered_*` deixar de ser retornável (mudança HubSpot) | `_calc_rampagem_15_safe` + fallback documentado p/ `closedate`. |
| Stage RAMP UP renomeado/recriado no HubSpot | Rodar `discover_schema.py` e atualizar `config.py` (convenção fixa). |
| Cloud redacta erro em produção | Wrapper `_safe` com diagnóstico descritivo (padrão existente). |

## 9. Plano de validação (rotina `/forecast`)

1. `PYTHONUTF8=1 python test_calc.py` — 0 exceções, janela 6 meses, totais
   coerentes, 6 deals de rampagem + incompletos separados, consolidado soma 3.
2. `git grep -n "pat-na1"` — anti-vazamento antes de commit.
3. `streamlit run app.py` local — 7 abas carregam, aba Rampagem mostra os 6
   deals com data de ativação + volumes.
4. Commit + push pro fork → Cloud redeploya → confirmar na URL pública.
