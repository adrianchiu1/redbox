# DECISIONS.md — append-only decision log

Per §16: never edit an earlier decision; supersede it with a new entry.
Spec references are to `COFOG_KICKOFF.md` v2.2.

---

## D-S0-001 — Python 3.11 runtime accepted for now (serves §11.3)
2026-08-31. The build environment provides Python 3.11.15; §11.3 specifies 3.12.
`pyproject.toml` sets `requires-python >= 3.11` and the code avoids 3.12-only
syntax, so it runs identically on 3.12. No behavioural dependence on the minor
version. Revisit only if a dependency forces 3.12.

## D-S0-002 — Stage 0 harvest blocked by network egress policy; fetch layer built to run when unblocked (serves §12 Stage 0, D8)
2026-08-31. This execution environment routes all outbound HTTPS through an
organisation egress proxy that returns 403 (policy denial) for every
statistical host needed by Stage 0: `ec.europa.eu`, `sdmx.oecd.org`,
`api.imf.org`, `data.imf.org`, `www.imf.org`, `www.ons.gov.uk`,
`economy-finance.ec.europa.eu`. Server-side page fetching is blocked by the
same policy; only web *search* is available. Per D13 (no fabrication, no
silent filling) no data was invented and no secondary mirror was used as a
substitute anchor. What was done instead:
  - endpoint verification via web search, recorded with per-entry confidence
    in `reports/source_verification.md`;
  - the full ingestion layer (`ggfiscal fetch`) written against the verified
    endpoints, storing every pull as an immutable content-hashed snapshot per
    D8, ready to run unchanged in a network-enabled environment.
Gate 0 is therefore **open/blocked**, not failed: see `HANDOFF.md` for the
exact unblock request and next command.

## D-S0-003 — Endpoint selections for the register (serves §13, §12 Stage 0)
2026-08-31. Chosen access paths (verification status in
`reports/source_verification.md`):
  - **Eurostat**: dissemination API, SDMX-CSV via
    `https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0/data/dataflow/ESTAT/{ds}/1.0/?format=csvdata`
    (SDMX 2.1 XML kept as fallback). Datasets `gov_10a_exp`, `gov_10a_main`,
    `gov_10a_taxag`, plus `nama_10_gdp` for the FRA/DEU GDP denominator.
  - **IMF**: the 2025-migrated portal API, base
    `https://api.imf.org/external/sdmx/3.0` (legacy
    `dataservices.imf.org` paths deliberately NOT used, per §12 Stage 0
    warning). WEO: agency `IMF.RES`, dataflow `WEO`, editions exposed as
    dataflow versions — enumerate versions live, take latest + preceding 4–9
    per §15 Q11. GFS COFOG: `data.imf.org` dataset `GFS_COFOG` (agency
    `IMF.STA`); exact dataflow id to confirm live.
  - **OECD**: `https://sdmx.oecd.org/public/rest/data/{flow}` SDMX-CSV.
    Revenue Statistics: `OECD.CTP.TPS,DSD_REV_COMP_GLOBAL@DF_RSGLOBAL`.
    COFOG Table 11 and National Accounts flow ids to confirm live.
  - **AMECO**: bulk zip-per-chapter download from
    `economy-finance.ec.europa.eu` (Spring 2026 vintage, published
    2026-06-03); no stable REST API identified, bulk file is the snapshot.
  - **ONS**: dataset landing pages under
    `www.ons.gov.uk/economy/governmentpublicsectorandtaxes/publicspending/datasets/`
    serving versioned xlsx; the xlsx file is the snapshot. Archived vintages
    for pre-1995 via the same pages' "previous versions".

## D-S0-004 — Raw snapshots content-addressed but not committed to git (serves D8, §11.1, §16)
2026-08-31. `data/raw/` follows `{source_id}/{retrieved_at}_{sha256[:12]}.{ext}`
and snapshots are never mutated, but the raw files themselves are gitignored:
the repository records provenance through `data/manifest/` (full sha256 per
pull) while the bytes live in the working store. Rationale: WEO/AMECO/Eurostat
bulk pulls are tens of MB per vintage and git is a poor archive for them;
reproducibility is preserved because any snapshot can be re-verified against
its recorded hash. `data/manual/` (hand-keyed CSVs, §11.4) IS committed.
Supersede this if the committee wants raw bytes in-repo or in LFS/object
storage.

## D-S0-005 — Source register is YAML seed + generated CSV (serves §13, §11.6 deliverable 8)
2026-08-31. `config/sources.yaml` is the editable register seeded from §13,
extended with the verification fields §6.4 requires (release date, vintage,
retrieval date, URL, snapshot hash, supersedes, scenario_label, concept_note,
plus `verification` status). `source_register.csv` is generated from it at
build time, never hand-edited.
