# vintage_diff.md — §11.7 vintage detection

Checked 2026-09-05 01:24 UTC (`ggfiscal detect-vintages`). Live source metadata vs the register (`config/sources.yaml`). A new vintage is a **config change plus rebuild, never a methodology change** (§11.7); WEO editions vanish from the IMF API, so new editions must be snapshotted promptly (D-S0-007).

**Action needed on 1 finding(s).**

| source | status | detail | action |
|---|---|---|---|
| EUROSTAT_NAMA10_GDP | changed | live UPDATE_DATA 2026-09-03 (latest observation 2025) vs register 2026-09-02 (2025) | update the register's verification fields in config/sources.yaml to the observed values, then re-run `ggfiscal fetch --all` and the build so the new release is snapshotted (D8) |
| DEU_BMAS_RVB | unreachable | publisher or egress policy blocks every available client (OQ-6); no vintage check possible until access exists | — |
| COR_2026 | no_check_path | PDF-only or unexercised source (§11.4 / OQ-5); vintage detection needs a machine-readable endpoint | — |
| DESTATIS_81000 | no_check_path | PDF-only or unexercised source (§11.4 / OQ-5); vintage detection needs a machine-readable endpoint | — |
| DEU_BMF_FINPLAN | no_check_path | PDF-only or unexercised source (§11.4 / OQ-5); vintage detection needs a machine-readable endpoint | — |
| DEU_STEUERSCHAETZUNG | no_check_path | no metadata endpoint; content-hash comparison available via `ggfiscal detect-vintages --hash` | — |
| EC_AGEING_2024 | no_check_path | no metadata endpoint; content-hash comparison available via `ggfiscal detect-vintages --hash` | — |
| EC_AMECO | no_check_path | no metadata endpoint; content-hash comparison available via `ggfiscal detect-vintages --hash` | — |
| EC_DSM | no_check_path | no metadata endpoint; content-hash comparison available via `ggfiscal detect-vintages --hash` | — |
| FRA_LFSS | no_check_path | PDF-only or unexercised source (§11.4 / OQ-5); vintage detection needs a machine-readable endpoint | — |
| FRA_LPFP_PSTAB | no_check_path | PDF-only or unexercised source (§11.4 / OQ-5); vintage detection needs a machine-readable endpoint | — |
| FRA_LPM_2030 | no_check_path | PDF-only or unexercised source (§11.4 / OQ-5); vintage detection needs a machine-readable endpoint | — |
| INSEE_APU | no_check_path | PDF-only or unexercised source (§11.4 / OQ-5); vintage detection needs a machine-readable endpoint | — |
| OECD_RS | no_check_path | no metadata endpoint; content-hash comparison available via `ggfiscal detect-vintages --hash` | — |
| OECD_T11 | no_check_path | no metadata endpoint; content-hash comparison available via `ggfiscal detect-vintages --hash` | — |
| ONS_GDP | no_check_path | no metadata endpoint; content-hash comparison available via `ggfiscal detect-vintages --hash` | — |
| EUROSTAT_GOV10A_EXP | unchanged | UPDATE_DATA 2026-07-21, latest observation 2025 | — |
| EUROSTAT_GOV10A_MAIN | unchanged | UPDATE_DATA 2026-07-21, latest observation 2025 | — |
| EUROSTAT_GOV10A_TAXAG | unchanged | UPDATE_DATA 2026-07-21, latest observation 2025 | — |
| IMF_GFS | unchanged | GFS_COFOG: pinned 11.0.0 is the latest exposed | — |
| IMF_GFS | unchanged | GFS_SOO: pinned 12.0.0 is the latest exposed | — |
| IMF_WEO | unchanged | live catalog exposes exactly the 3 registered editions: 2025-04, 2025-10, 2026-04 | — |
| ONS_ESA_T11 | unchanged | releaseDate 2026-04-22 | — |
| ONS_GG_RECEIPTS | unchanged | releaseDate 2026-06-18 | — |
| ONS_PSF_INTEREST | unchanged | releaseDate 2026-06-18 | — |
| ONS_TAX_DETAIL | unchanged | releaseDate 2026-06-18 | — |
| ONS_TAX_LIST | unchanged | releaseDate 2023-10-26 | — |

Statuses: `new_vintage` (unregistered edition live), `changed` (release/metadata drifted from the register), `vanished` (registered edition gone from the API — snapshots are the archive), `unreachable` (blocked host, OQ-6), `no_check_path` (no metadata endpoint or PDF-only, OQ-5), `unchanged`.

Re-run after registering a vintage: `ggfiscal fetch --all && ggfiscal build && ggfiscal reconcile && ggfiscal report` (reconciliation re-runs for every registered vintage, §8.5).
