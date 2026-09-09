"""ggfiscal.debt — the central-government debt securities register, the
interest and financing reconciliation chains, and the maturity profile
(DEBT_KICKOFF.md v1.0, DD12).

Layering mirrors the parent package: register entries in config
(`config/debt_sources.yaml`, merged into `config.sources()`), D8 snapshots
via `debt.fetch`, per-family readers in `debt.readers`, canonical tables in
`data/canonical/debt_*.csv`, validation V29-V40, flat files in
`deliverables/debt_*.csv`.

Source families (`debt.families.*`) each expose `pulls() -> list[Pull]` and
may expose `get(pull) -> bytes` when the publisher needs a non-standard
client (the BMF bot manager, the BoE IADB HTML table).
"""
