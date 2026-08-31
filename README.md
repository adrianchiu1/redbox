# gg-fiscal

Reproducible pipeline for long-horizon general-government expenditure by
COFOG function, revenue by ESA type, and reconciliation to IMF WEO fiscal
aggregates, for the United Kingdom (GBR), France (FRA) and Germany (DEU).

**The specification is [`COFOG_KICKOFF.md`](COFOG_KICKOFF.md) (v2.2). It
governs.** Working state lives in [`HANDOFF.md`](HANDOFF.md); decisions in
[`DECISIONS.md`](DECISIONS.md); committee items in
[`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md).

This README will be generated from the build in Stage 6 (§11.6); until then
it is a hand-written stub.

## Layout (§11.2)

```
config/          countries.yaml, lines.yaml, sources.yaml, residual.yaml
crosswalks/      versioned source→target mappings (§11.5)
data/            raw → manual → standard → canonical → manifest (§11.1)
src/ggfiscal/    ingest | standardise | stitch | forecast | reconcile | validate | report
tests/           per-stage test suites (tests/stage_0, ...)
reports/         source_verification.md, validation/reconciliation reports
```

## Setup

```
pip install -e .[dev]
pytest
ggfiscal --help
```

## Stage status

Stages 0–5 complete (gates passed): harvest, canonical history (both trees),
backward extension, strict forecasts, maximum-extension forecasts with the
full coverage matrix, and the WEO reconciliation module (§8.2–8.5:
`weo_explanation.csv`, `net_interest_check.csv`, `weo_residual_history.csv`,
`reports/reconciliation_report.html`). Next: Stage 6 (packaging and vintage
re-run). See `HANDOFF.md` for the live state and `OPEN_QUESTIONS.md`
OQ-6/OQ-7 for the blocked forecast sources awaiting the committee.
