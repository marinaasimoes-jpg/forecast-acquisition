# Monthly Commercial Planning

Forecast de volume de corridas por mês (próximos 6 meses) dos clientes em
**Negociação** (etapas 4/5/6 — ainda não assinaram), em **Ativação**
(etapa 7) e em **Rampagem** (stage RAMP UP do pipeline B2B Retention —
clientes já em rampa, subindo a curva), dos pipelines B2B Outbound, B2B
Website Table, B2B CSM Acquisition e B2B Retention. Fonte: HubSpot.

## v2 (2026-10-15) — o que mudou

- **7 abas**: Negociação (4/5/6), Negociação Potencial atualizado (15%),
  Ativação (7), Ativação Potencial Atualizado (15%), Rampagem (RAMP UP),
  Rampagem Potencial Atualizado (15%) e Consolidado (soma das três
  categorias + gráfico de barras empilhadas + KPI 6 meses).
- **Filtros** na sidebar (Pipeline, Proprietário, Etapa) — operam sobre o
  cache, sem nova consulta ao HubSpot. Botão "Limpar filtros".
- **Ordenação por clique** nos cabeçalhos via `st.dataframe` nativo: valores
  numéricos e datas reais (não texto), então ordena numericamente, não
  alfabética. Linha TOTAL num bloco separado acima/abaixo (não ordenável).
- **Nova aba Ativação**: rampa desde a data de entrada na Ativação (ver
  abaixo), sem somar os 5 dias úteis (o deal já está em ativação).
- **Nova aba Rampagem** (2026-10-26): clientes já em rampa no pipeline
  **B2B Retention** (stage **RAMP UP**). Rampa desde a data de entrada
  no stage (`hs_v2_date_entered_*` — descoberta abaixo). Mesma curva da
  Negociação/Ativação. Cada categoria ganha também uma aba **"Potencial
  Atualizado"** com o forecast sobre 15% do potencial.
- Visual mais limpo: cor só em chips de pipeline e no gráfico. As tabelas
  têm **zebra striping** (linhas intercaladas) via `pandas.Styler` pintado
  no canvas do `st.dataframe` — mantém ordenação por clique e `column_config`.

## Rodar

```bash
export HUBSPOT_TOKEN="<seu Private App token>"   # env var, nunca no fonte
streamlit run app.py
```

Os dados ficam em cache 15 min; botões **🔄 Atualizar agora**
(incremental) e **♻️ Recarregar tudo** na sidebar.

## Arquivos

| Arquivo | Papel |
|---|---|
| `app.py` | App Streamlit: 7 abas, filtros, `st.dataframe` nativo + `column_config`, totais, gráfico. |
| `fetch_hubspot.py` | Search API dos stages 4/5/6 + 7 Ativação dos 3 pipelines (mesma consulta) + stage RAMP UP do B2B Retention + Owners API. |
| `calc_forecast.py` | Negociação: ativação +5dúteis, proporcionalidade M1, curva, janela. Ativação: rampa desde `closedate`. Rampagem: rampa desde `hs_v2_date_entered_*`. Variantes 15% (`_15`) p/ cada categoria. |
| `config.py` | IDs descobertos (4/5/6 + 7 Ativação + RAMP UP), propriedades, regras de cálculo. |
| `discover_schema.py` | Descoberta dinâmica de pipelines/stages/propriedades pelo label (inclui Ativação e RAMP UP). |
| `probe_ativacao.py` | Confirmou stage "7. Ativação" nos 3 pipelines + IDs 4/5/6. |
| `probe_date_entered.py` | Provou que `hs_date_entered_<id>` (v1) NÃO é retornável pela API → Ativação usa `closedate`. |
| `probe_potencial.py` | Probe que confirmou qual propriedade é o potencial absoluto de corridas. |
| `probe_previsao.py` | Confirmou `previsao_de_fechamento` como data de fechamento prevista. |
| `selfcheck.py` | Verificações automáticas (estrutura, contagem, valores, regras, consolidado 3 categorias, sanity, 15%). |
| `test_calc.py` | Validação do cálculo com deals reais (Negociação + Ativação + Rampagem). |

## Decisões confirmadas

### Propriedade de potencial: `share_vs_potencial_total`
Label **"Potencial Mês (Total)"**. Apesar do nome técnico ("share"), o
`probe_potencial.py` confirmou que é um **número absoluto de corridas**, não
razão: `>=` que `potencial_mes_99` em todos os deals, e é o mais populado.
Vem como string com separador de milhar BR (`"16.000"` = 16000) — tratado em
`_parse_potencial`.

### Data de fechamento: `previsao_de_fechamento` (NÃO `closedate`)
`previsao_de_fechamento` (label "Previsão de Fechamento", tipo date) é a
previsão real, com datas futuras coerentes. `closedate` é a data **real** de
fechamento (fica no passado/errada pra deals abertos em negociação) — usada
só na aba Ativação (abaixo).

### Aba Ativação: data de entrada = `closedate` (2026-10-15)
A spec original pedia `hs_date_entered_<stage_id>` (timestamp de quando o
deal entrou na etapa). **Essa propriedade NÃO é retornável pela CRM API v3**
do HubSpot — nem pela Search API, nem pela Read API com `properties=*`. É
timestamp interno do produto, visível só na UI. `probe_date_entered.py`
confirmou: 0/6 deals devolveram a prop, enquanto `closedate` voltou populada
em 8/8 (datas recentes, ago–out 2026). **Decisão do usuário: usar `closedate`
(data real de fechamento) como proxy da entrada na Ativação.**

- **Rampa** desde o mês do `closedate`, **sem** somar os 5 dias úteis (o deal
  já está em ativação). M1 = mês do `closedate`, proporcional por dia.
- Calcula-se a rampa DESDE a entrada, mas só se exibem os 6 meses da janela
  atual. Deal que entrou há 3 meses já aparece em 100% hoje.
- Mesma curva por potencial total: <20k → 25/50/100; ≥20k → 25/50/75/100.

### Aba Rampagem: data de entrada = `hs_v2_date_entered_1412072536` (2026-10-26)
Clientes **já em rampa** (ativaram, subindo a curva) vivem no pipeline
**B2B Retention** (`922791528`), stage **RAMP UP** (`1412072536`, step 8).
A fronteira: o deal migra do stage 7 "Ativação" (aquisição) para o RAMP UP
(Retention) ao iniciar a rampa. A data-base é a entrada nesse stage.

- **Descoberta chave — `hs_v2_date_entered_<stage_id>` É retornável pela
  CRM API v3** (diferente do `hs_date_entered_<id>` v1, que NÃO é — ver
  `probe_date_entered.py` e a aba Ativação acima). Populado em 6/6 deals
  em 2026-10-26. A propriedade `hs_v2_date_entered_1412072536` (label
  "Data de entrada no Ramp Up") veio populada pela Search API sem recurso
  à Read API — ao contrário da v1, que é timestamp interno só visível na UI.
- **Decisão do usuário: usar `hs_v2_date_entered_1412072536` como data-base
  da Rampagem** (entrada no RAMP UP). Diferente da Ativação, aqui NÃO é
  proxy — é o timestamp real de entrada no stage.
- **Rampa** desde o mês da entrada no RAMP UP, **sem** somar os 5 dias
  úteis (o deal já está em rampa). M1 = mês da entrada, proporcional por
  dia. Calcula-se a rampa DESDE a entrada, mas só se exibem os 6 meses da
  janela atual. Deal que entrou há 3 meses já aparece em 100% hoje.
- **Mesma curva** por potencial total: <20k → 25/50/100; ≥20k →
  25/50/75/100. Após 100%, permanece 100% nos meses seguintes da janela.
- **2 abas**: "Rampagem" (sobre o potencial total) e "Rampagem Potencial
  Atualizado" (forecast sobre 15% do potencial — espelha as abas
  "Negociação/Ativação Potencial Atualizado").
- **Consolidado soma 3 categorias**: Negociação + Ativação + Rampagem
  (mês a mês + total 6 meses + gráfico de barras empilhadas + KPI).

### Stage "7. Ativação" nos 3 pipelines (descoberto pelo label, não assumido)
- B2B Outbound (`890800903`): stage `1342981415`
- B2B Website Table (`917378965`): stage `1399082603`
- B2B CSM Acquisition (`927024659` — o HubSpot o chama de "B2B Inbound SQL";
  divergência só de nome amigável, IDs batem): stage `1420435115`

### Stage RAMP UP no B2B Retention (descoberto pelo label, não assumido)
- B2B Retention (`922791528`): stage `1412072536` (RAMP UP, step 8)

### Pipelines (4 ativos)
B2B Outbound (`890800903`), B2B Website Table (`917378965`), B2B CSM
Acquisition (`927024659`) e B2B Retention (`922791528` — só a aba
Rampagem consulta este pipeline).

### Regras de cálculo — Negociação
- **Ativação** = previsão de fechamento + 5 dias úteis (ignora sáb/dom e
  feriados nacionais BR, incluindo móveis). Deal atrasado (fechamento no
  passado) → base = fechamento + 1 mês (ou hoje + 1 mês), sinalizado.
- **Mês 1** = mês calendário da ativação, volume proporcional aos dias
  ativos: `potencial × 25% × (dias_ativos / dias_no_mês)`.
- **Curva**: <20k → 25/50/100 (teto mês 3); ≥20k → 25/50/75/100 (teto mês 4).
  Após 100%, permanece 100% nos meses seguintes da janela.
- **Janela**: 6 meses a partir do mês atual (inclusive).
- **Probabilidade**: 100% (não pondera etapa).

### Regras de cálculo — Rampagem
- **Data-base** = `hs_v2_date_entered_1412072536` (entrada no stage RAMP UP
  do pipeline B2B Retention). **Não** soma os 5 dias úteis (o deal já
  está em rampa).
- **Mês 1** = mês calendário da entrada no RAMP UP, volume proporcional
  aos dias ativos: `potencial × 25% × (dias_ativos / dias_no_mês)`.
- **Curva**: <20k → 25/50/100 (teto mês 3); ≥20k → 25/50/75/100 (teto mês 4).
  Após 100%, permanece 100% nos meses seguintes da janela. Mesma curva da
  Negociação/Ativação.
- **Janela**: 6 meses a partir do mês atual (inclusive). Calcula-se a
  rampa DESDE a entrada, mas só se exibem os 6 meses da janela atual.
- **Potencial Atualizado (15%)**: mesma lógica, mas o forecast é sobre
  `potencial_15 = round(potencial × 0.15)`. A curva é reavaliada pelo
  pot15 (um deal <20k no total pode cair na faixa high quando 15%).
- **Consolidado**: soma Negociação + Ativação + Rampagem, mês a mês.

### Exceções
- Deal sem a data base da sua aba (previsão p/ Negociação, `closedate` p/
  Ativação, `hs_v2_date_entered_*` p/ Rampagem) ou sem potencial → seção
  **"Deals com dados incompletos"**, fora dos totais, com motivo.
- Dado ausente → exibido como `–`.

### Heatmap
A spec v2 pedia heatmap nos meses, mas `BarColumn` **não existe no Streamlit
1.61.1** (só em versões posteriores); `ProgressColumn` mostra só a fração,
não o valor bruto. Prioridade foi manter os valores **numéricos** (requisito
hard para ordenação por clique) via `NumberColumn`. O heatmap cosmético pode
ser readicionado via CSS quando subir para uma versão com `BarColumn`.

## Segurança
O token do HubSpot está exposto nos `extract_*.py` do escopo Funnel Data
Pipeline (pasta pai do funnel automation) — ver `ONBOARDING.md` lá. Este
dashboard segue o padrão migrado em 2026-09-10: token via **env var
`HUBSPOT_TOKEN`** (ou secret do Streamlit Cloud), **nunca hardcoded**.
Qualquer pessoa com acesso à pasta compartilhada pode ver o token hardcoded
nos scripts antigos — trate como credencial comprometida se houver risco.
