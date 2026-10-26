# Task 5 Report — selfcheck.py: extend run() with rampagem + 5.10 checks

## What was implemented

Three edits to `selfcheck.py` per the task brief:

1. **Signature (line 28 → 7-arg):** `run(negociacao, ativacao, incompletos, meses, fetched_deals, hoje=None)` → `run(negociacao, ativacao, rampagem, incompletos, meses, fetched_deals, hoje=None)`. `rampagem` inserted as the 3rd positional arg (after `ativacao`, before `incompletos`), mirroring `calc_forecast.calcular_todos`'s 5-tuple order. Docstring + module docstring updated to note rampagem and the new 5.10 series.

2. **`todos` aggregate (line 34):** `negociacao + ativacao + incompletos` → `negociacao + ativacao + rampagem + incompletos`. This flows into 5.1 (`found_steps`), 5.2 (duplicate `ids` + `fora` checks), and 5.4 (`bad_owners`) — all now see rampagem deals, which is intended.

3. **5.10 Rampagem block (before `return checks`):** four sub-checks following the 5.6/5.7 structural template (`_ok`/`_warn` helpers, deal_id sets for the overlap):
   - (a) Pipeline B2B Retention configured (`config.PIPELINE_B2B_RETENTION`).
   - (b) Rampagem found — count of deals in RAMP UP stage (`config.STAGES_RAMPAGEM[...][0]`); warns if none.
   - (c) No Ativação↔Rampagem overlap — `ids_ramp & ids_ativ` intersection must be empty; warns with offending deals if non-empty.
   - (d) Consolidado = sum of 3 categories month-by-month (`vn + va + vr` per month in `meses`).

Exactly ONE `return checks` remains (line 329) — the new block's return replaced the old trailing one; no duplication.

## Step 3 verification output

Ran the brief's verification (real HubSpot fetch, `calcular_todos` 5-tuple, `sc.run` 7-arg):

```
⚠ 37 ok / 3 atenção
  WARN [5.2] Contagem NÃO bate: 82 buscados ≠ 65+9+2. (0 deals)
  WARN [5.2] 6 deal(s) fora dos pipelines/etapas alvo. (6 deals)
  WARN [5.10] Sanity da variante 15% FALHOU — revisar calcular_negociacao_15. (0 deals)
counts: neg=65 ativ=9 ramp=6 inc=2 fetched=82
5.10 series count: 12
```

Rampagem 5.10 series (all `ok`):
```
  [5.10] ok: Pipeline B2B Retention (id 922791528) configurado p/ Rampagem.
  [5.10] ok: Rampagem: 6 deal(s) no stage RAMP UP (1412072536).
  [5.10] ok: Nenhum deal aparece ao mesmo tempo em Ativação e Rampagem.
  [5.10] ok: Consolidado Oct/26: neg=0 + ativ=10308 + ramp=97129 = 107437.
  [5.10] ok: Consolidado Nov/26: neg=61285 + ativ=27000 + ramp=221800 = 310085.
  [5.10] ok: Consolidado Dec/26: neg=498986 + ativ=35950 + ramp=297800 = 832736.
  [5.10] ok: Consolidado Jan/27: neg=1116904 + ativ=42950 + ramp=372800 = 1532654.
  [5.10] ok: Consolidado Feb/27: neg=1689407 + ativ=42950 + ramp=372800 = 2105157.
  [5.10] ok: Consolidado Mar/27: neg=2283420 + ativ=42950 + ramp=372800 = 2699170.
```

- `sc.run` 7-arg works; returns checks.
- 5.10 Rampagem series present (9 Rampagem checks + 6 monthly consolidado = 9 lines; total `5.10` count = 12 because of the pre-existing 15%-variant `5.10` checks — see Concerns).
- 0 Ativação↔Rampagem overlap (5.10b = `ok`).
- `ramp=6` matches the plan's "Rampagem: 6" expectation.

## Files changed

- `selfcheck.py` (+43 / −4): signature, docstring, `todos`, 5.10 Rampagem block.

## Commits

- `144e17d` — feat(rampagem): selfcheck 5.10 — Rampagem found, no overlap, consolidado 3 abas

## Self-review findings

- **Signature position:** `rampagem` is the 3rd positional arg, after `ativacao` and before `incompletos` — matches `calcular_todos`'s `(neg, ativ, ramp, inc, meses)` order. ✓
- **Single `return checks`:** exactly one, at line 329. ✓
- **5.10 mirrors 5.6/5.7 style:** uses `_ok`/`_warn` helpers, `("5.10",) +` tuple prefix, deal_id sets for the overlap intersection. ✓
- **Overlap uses deal_id sets:** `ids_ramp = {d["deal_id"] for d in rampagem}`; `ids_ativ = {d["deal_id"] for d in ativacao}`; `dup_ra = ids_ramp & ids_ativ`. ✓
- **Anti-leak:** `git grep -n "pat-na1-abfbac1b" -- '*.py'` returns no matches (exit 1). ✓
- **Callers broken by design:** `app.py` `main()` (line ~118) and `test_calc.py` (line ~147) still call `sc.run` with the old 6-arg signature — will break until Tasks 6-7 update them. Not touched in this task per the brief. ✓

## Concerns

1. **5.10 ID collision (cosmetic, pre-existing).** The plan/spec reserved `5.10` for the Rampagem series, but the file already used `5.10` (15% Negociação variant, commit `bb70637`) and `5.11` (15% Ativação variant, commit `a73756d`) — those commits post-dated the plan's authoring and pre-dated Task 1. The brief gives exact code with `("5.10",)` literals and says to apply it as-is, so I followed it literally. Result: the summary output now contains 12 checks tagged `5.10` (3 from the 15% Negociação sanity/potencial/over + 9 from the Rampagem series). This is confusing in the WARN listing but functionally harmless — `summary()` only counts ok/warn, it doesn't key off IDs, and no external code references the numeric IDs (verified via `git grep`). The 5.10 Rampagem checks are all `ok` so they don't appear in the WARN list anyway. **Recommendation for a follow-up:** renumber the 15%-variant checks to `5.12`/`5.13` (or the Rampagem series to `5.12`+) to disambiguate. Flagging here so the next task owner can decide; did not renumber unilaterally because the brief was explicit.

2. **5.2 count reconciliation now warns (expected, pending T7).** Adding `rampagem` to `todos` without updating 5.2's count formula produces a false WARN: `82 buscados ≠ 65+9+2` (the 6 ramp deals are in `fetched_deals` but not summed: 82 − 76 = 6). The same ripple causes `6 deal(s) fora dos pipelines/etapas alvo` — ramp deals are in pipeline "B2B Retention" (not in `config.PIPELINES`) and step 8 (not in 4/5/6/7). The brief explicitly says "Existing 5.6/5.7/5.8 Ativação checks may now warn about consolidation expecting 2 — that's fine, Task 7 fixes the consolidated check fully" and restricts this task to 3 edits ("Do not restructure other checks"), so I left 5.2 untouched. Task 7 should update 5.2's formula to `n_neg + n_ativ + n_ramp + n_incompl` and extend the `fora`/`found_steps` checks to accept pipeline "B2B Retention" and step 8.

3. **Pre-existing 5.10 15% sanity WARN (unrelated to this task).** `WARN [5.10] Sanity da variante 15% FALHOU — revisar calcular_negociacao_15` is the pre-existing 15% Negociação sanity check (commit `bb70637`), not the Rampagem series. It was already warning before my change. Not in scope.

## Fix for review findings

Both Important findings from the Task 5 review adjudication were real plan-vs-reality conflicts and have been resolved in `selfcheck.py`:

**Finding 1 — 5.10 ID collision (renumber Rampagem → 5.12).** Renumbered ONLY the Rampagem series (the block starting at the `# ---- 5.12 Rampagem ----` comment, formerly `5.10 Rampagem`) from `("5.10",)` → `("5.12",)`. The pre-existing 15% Negociação `5.10` block (commit `bb70637`) and 5.11 Ativação block (commit `a73756d`) were left untouched. Section comment, `# 5.12b` / `# 5.12c` inline comments, and module docstring updated. Result: `5.10` count dropped from 12 → 3 (15% Neg only); `5.12` count = 9 (Rampagem series).

**Finding 2 — 5.2 count reconciliation broken (make 5.2 count rampagem).** Updated 5.2:
1. Count formula: `n_fetched == n_neg + n_ativ + n_ramp + n_incompl` where `n_ramp = len(rampagem)`. Both `ok` and `warn` message strings now include ramp in the sum.
2. `fora` allowlist: a deal is "in target" if (in `config.PIPELINES` with step in 4/5/6/7) OR (in `config.PIPELINE_B2B_RETENTION` with step 8). Ramp deals no longer flagged "fora". `pipeline_id` comparison used (not label) since `PIPELINE_B2B_RETENTION` is an id constant.

### Step 3 verification output (post-fix, real fetch + `calcular_todos` 5-tuple + `sc.run` 7-arg)

```
⚠ 39 ok / 1 atenção
  WARN [5.10] Sanity da variante 15% FALHOU — revisar calcular_negociacao_15. (0 deals)
5.12 count: 9
5.10 count: 3
counts: neg=65 ativ=9 ramp=6 inc=2 fetched=82
```

- `5.12 count: 9` (Rampagem series present); `5.10 count: 3` (15% Neg only — collision resolved).
- `5.2 Contagem NÃO bate` WARN GONE (now `82 = 65+9+6+2`).
- `5.2 6 deal(s) fora dos pipelines/etapas` WARN GONE (ramp deals now allowed).
- Summary improved from "37 ok / 3 warn" to "39 ok / 1 warn" — the only remaining warn is the pre-existing 15% Negociação sanity FALHOU (commit `bb70637`, unrelated to this task).
- Note: the brief estimated "37 ok / 1 warn"; the actual improvement is 39 ok / 1 warn because the two formerly-warned 5.2 checks (count + fora) are now `ok`, not merely neutralized.
- Anti-leak: `git grep -n "pat-na1-abfbac1b" -- '*.py'` returns no matches (exit 1).
