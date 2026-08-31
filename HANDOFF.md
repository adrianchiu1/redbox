# HANDOFF.md

Rewritten 2026-08-31, end of session 1.

## Current stage

**Stage 0 (verify and harvest) — in progress, harvest blocked.**

## Gate 0 status: OPEN (blocked, not failed)

| Gate 0 requirement | Status |
|---|---|
| Endpoints confirmed (incl. IMF 2025 portal migration) | Partially: migration confirmed, new base `api.imf.org/external/sdmx/3.0` adopted, WEO-editions-as-dataflow-versions understood; 4 dataflow ids still need one live catalog query each (see `reports/source_verification.md`). |
| All anchors + WEO + GFS + OECD RS + AMECO pulled as D8 snapshots | **Blocked — OQ-1**: org egress policy denies every statistical host (confirmed live via `ggfiscal fetch --all`). |
| 66 lines with programmatic coverage → `coverage_matrix_v0.csv` | Frame emitted (66 rows, candidate sources per line, D7 notes); year columns empty pending harvest — deliberately not hand-filled (D13). |
| §8.2 base-year bridge, 3 countries, latest WEO vintage (2026-04) | Blocked on the same harvest. |
| `reports/source_verification.md` | Written; complete to the limit of search-only verification; flagged entries listed. |

## Blocked on whom

**The committee (AC)** — OQ-1 in `OPEN_QUESTIONS.md`: either allowlist the
listed hosts for this repo's remote sessions, or run the harvest from a
network-enabled machine (`pip install -e . && ggfiscal fetch --all`) and sync
`data/manifest/` + `data/raw/` back. Nothing else blocks.

## What exists and is verified working

- Repo skeleton per §11.2; configs (`countries/lines/sources/residual.yaml`)
  encoding D1–D17 and the Q1–Q13 defaults; §13 register with verification fields.
- `ggfiscal` package: immutable content-hashed snapshot store (D8) with
  append-only manifest and hash re-verification; endpoint builders (no legacy
  IMF paths, enforced by test); fetch orchestration distinguishing egress
  denial from source failure; validation runner (V1–V28 registered with
  stage-gated SKIP semantics + Stage 0 structural checks) writing
  `exceptions.csv`; coverage-matrix and source-register generators; typer CLI.
- `pytest`: 20/20 green. `ggfiscal validate`: OK=2 SKIP=28 WARN=1, **no ERROR**
  (the WARN is the absent harvest, which is correct).

## Exact next command

In a network-enabled environment (or after allowlisting):

```
pip install -e .[dev] && ggfiscal fetch --all && ggfiscal validate
```

Then, same session: enumerate WEO dataflow versions from the fetched catalog
(pin Q11 vintage count), confirm the 4 open dataflow ids, write the
standardise step for the fetched snapshots, measure first/last usable years
into `coverage_matrix_v0.csv`, and compute the §8.2 base-year bridge on WEO
2026-04. That completes Gate 0.

## §15 dependencies currently riding on defaults

Q1 (nominal LCU primitive), Q3 (`grow_with_proxy`), Q4 (tolerances as
tabled — in `countries.yaml`), Q7 (defence plans strict-B if ≥90% GG),
Q8 (keep uplift), Q11 (5–10 WEO vintages — final count pinned at harvest),
Q12 (OBR primary for GBR §8.3), Q13 (R06 single line). No default has been
overridden; none has yet forced a committee call.
