"""Family 'ecb_bbk' — euro reference rates (DEBT_KICKOFF.md §13).

Two registered sources feed this family, both confirmed live 2026-09-09
(reports/debt_sources/ecb_bbk.md has the full harvest record and the key
discovery notes below):

* ``ECB_EMMI_RATES`` — ECB Data Portal SDMX-CSV (``data-api.ecb.europa.eu``):
  the €STR (``EST``), the deposit facility rate, Euribor 3M/6M and EONIA
  (``FM``), and the euro-area HICP excluding tobacco (``ICP``, cross-check
  only — the same series already reaches `debt_reference_series` as
  ``EA_HICP_XT`` via `eurostat_insee_oecd`, so it is snapshotted here but not
  re-wired into `reference.build_reference_series`).
* ``BBK_KAPITALMARKT`` — Bundesbank SDW REST API
  (``api.statistiken.bundesbank.de``): the 10-year Bund yield from the
  Svensson term-structure estimate.

**Key corrections found live (2026-09-09):**

* EONIA is published in the ``FM`` dataflow at **monthly** frequency only
  (``M.U2.EUR.4F.MM.EONIA.HSTA``, 1994-01 to 2021-12, the last full month
  before EONIA's 2022-01 discontinuation) — the kickoff's daily
  ``D.U2.EUR.4F.MM.EONIA.HSTA`` guess 404s. The monthly key was recovered
  from `CL_PROVIDER_FM_ID`'s own code descriptions (several unrelated
  "deposit spread" codes cite it as `FM.M.U2.EUR.4F.MM.EONIA.HSTA` in their
  labels), then confirmed live.
* Euribor 3M/6M are likewise monthly-only in ``FM``
  (``M.U2.EUR.RT.MM.EURIBOR{3,6}MD_.HSTA``, 1994-01-); no daily Euribor key
  exists in this dataflow (the ``D.`` form 404s) — EMMI's own daily fixings
  are not republished by the ECB Data Portal under a discoverable key.
* The HICP-ex-tobacco item code is **``X02200``** ("HICP - All-items
  excluding tobacco"), not a ``TOB000``-shaped code — found via the
  ``CL_ICP_ITEM`` codelist (`grep`-ing for "tobacco") and confirmed live;
  its `DOM_SER_IDS` attribute (``...TOT_X_TBC.M``) matches Eurostat's own
  ``TOT_X_TBC`` coicop code one-for-one, i.e. it is the same series
  Eurostat republishes as `prc_hicp_minr`/`prc_hicp_midx`.
* The Bundesbank Svensson beta/tau curve parameters and the "Umlauf von
  Bundeswertpapieren" stock series were not found within the discovery
  budget (guessed keys 404; no public metadata-search endpoint was found
  under ``/rest/metadata/`` — only the SDW website's own JS search covers
  that, which is out of scope for a machine pull) — not pulled here. Only
  the 10y yield key (``R10XX`` for 10.0y residual maturity) was confirmed.
"""

from __future__ import annotations

from ggfiscal.ingest.endpoints import BROWSER_HEADERS, Pull

ECB_BASE = "https://data-api.ecb.europa.eu/service/data"
BBK_BASE = "https://api.statistiken.bundesbank.de/rest/data"

_ECB = "ECB_EMMI_RATES"
_BBK = "BBK_KAPITALMARKT"

# Bundesbank BBSIS key for the Svensson-method term structure of listed
# federal securities, 10.0y residual maturity, daily.
BBK_BUND_YIELD_10Y_KEY = "D.I.ZST.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A"


def ecb_url(flow: str, key: str) -> str:
    return f"{ECB_BASE}/{flow}/{key}?format=csvdata"


def bbk_url(flow: str, key: str) -> str:
    return f"{BBK_BASE}/{flow}/{key}?format=csv"


def pulls() -> list[Pull]:
    return [
        Pull(_ECB, "estr", ecb_url("EST", "B.EU000A2X2A25.WT"), headers=BROWSER_HEADERS),
        Pull(_ECB, "eonia", ecb_url("FM", "M.U2.EUR.4F.MM.EONIA.HSTA"), headers=BROWSER_HEADERS),
        Pull(_ECB, "euribor_3m", ecb_url("FM", "M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA"), headers=BROWSER_HEADERS),
        Pull(_ECB, "euribor_6m", ecb_url("FM", "M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA"), headers=BROWSER_HEADERS),
        Pull(_ECB, "dfr", ecb_url("FM", "D.U2.EUR.4F.KR.DFR.LEV"), headers=BROWSER_HEADERS),
        Pull(_ECB, "hicp_xt_ea", ecb_url("ICP", "M.U2.N.X02200.4.INX"), headers=BROWSER_HEADERS),
        Pull(_BBK, "bund_yield_10y", bbk_url("BBSIS", BBK_BUND_YIELD_10Y_KEY), headers=BROWSER_HEADERS),
    ]
