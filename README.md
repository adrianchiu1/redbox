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

Stage 0 (verify + harvest) is in progress; the harvest is blocked on network
egress policy — see `HANDOFF.md` and OQ-1 in `OPEN_QUESTIONS.md`.
