"""Stage U1 validation addition (REPLICATION_KICKOFF.md §10): **V44** on the
COFOG Level II rows a country builds from a secondary national table (D26).

V44 runs for every country whose `countries.yaml` names a `level2_source`
— the config key, never a country literal — and reports OK with an explicit
"no proxied Level II" message for the countries that do not, so the check is
exercised on every run instead of silently skipping three quarters of the
package.

Scope, precisely (the U1 remit is *checks and documentation*, not values):

* **Typing.** Every anchor-year row of a proxied country's COFOG Level II
  lines is `level2_proxy_actual`, grade B, and carries a concept note. Rows
  a later stage adds — forecasts (`is_forecast`) and backward stitches
  (`anchor_year != year`) — are out of V44's scope and are counted in the
  OK message so their arrival is visible; at U1 there are none. A line the
  country declares in `lines_absent` is published as `structural_zero`
  rows and is V41's business, not V44's.
* **Provenance.** Every row whose `source_id` is the register id behind the
  country's `level2_source` carries `concept_flag = level2_bea_function`
  (kickoff §5) and the `crosswalk_version` stamp of the §11.5 crosswalk that
  documents the mapping (D-S17-005). The interest line is deliberately not
  in this set: D10's fallback puts it on the anchor institution's own gross
  D.41 payable (`d41_gross_accrued`), which D-S16-005 measured equal to
  T11 `D4 x GF01` to USD 3 mn — so it is a Level II proxy row (typed and
  graded as one) sourced from the anchor, not from the national table.
* **Identity.** `remainder + Σ level2 = parent` is V19's arithmetic and is
  **delegated** to it: V44 runs `check_v19()` and fails on V19's ERRORs for
  the country rather than recomputing the same sums a second way.
* **Memo.** The IMF GFS Level II comparison D26 names as "the one external
  cross-check, reported not used" (`GF0170_T`, USA 1980-89) is reported at
  OK. Never WARN, never ERROR: it is a GFSM-basis series with a large,
  known wedge, and V1 already carries the per-year WARN rows.

V44 is ERROR-tier (kickoff §10) and registered at stage 1 in
`runner.V_SUITE_STAGE`.
"""

from __future__ import annotations

import pandas as pd

from ggfiscal import config
from ggfiscal.standardise import proxies
from ggfiscal.validate.runner import Finding

EXPECTED_TYPE = "level2_proxy_actual"
EXPECTED_GRADE = "B"


def _anchor_rows(g: pd.DataFrame) -> pd.DataFrame:
    """The rows V44 types: observed at their own anchor year, not forecast.
    A stitched row carries the boundary anchor (anchor_year != year) and a
    forecast row `is_forecast` — both are later stages' (U2/U3) rows with
    their own checks (V5, V13, V17)."""
    return g[(~g.is_forecast.astype(bool)) & (g.anchor_year == g.year)]


def check_v44() -> list[Finding]:
    """V44 (ERROR) — see the module docstring."""
    from ggfiscal.validate.stage1 import _tables, check_v19

    out: list[Finding] = []
    memo: list[Finding] = []
    tables = _tables()
    tree = config.tree_lines("COFOG")
    l2_codes = list(config.level2_lines("COFOG"))
    v19_errors = [f for f in check_v19() if f.severity == "ERROR"]

    proxied: list[str] = []
    unproxied: list[str] = []
    n_typed = n_sourced = n_later = 0
    for iso3 in config.COUNTRIES:
        routing = proxies.level2_routing(iso3)
        if routing is None:
            unproxied.append(iso3)
            continue
        proxied.append(iso3)
        stamp = proxies.level2_crosswalk_stamp(iso3)
        absent = config.absent_lines(iso3)
        for variant, df in tables.items():
            sub = df[(df.iso3 == iso3) & (df.series_variant == variant)
                     & (df.classification == "COFOG") & df.line_code.isin(l2_codes)]
            for code in l2_codes:
                if ("COFOG", code) in absent:
                    continue          # D20 structural zero — V41's business
                g = sub[sub.line_code == code]
                scope = f"{iso3}/{code}/{variant}"
                if g.empty:
                    out.append(Finding("V44", "ERROR", scope,
                                       "a country with a level2_source has no rows on this "
                                       "COFOG Level II line (D26 proxy did not build)"))
                    continue
                anchors = _anchor_rows(g)
                n_later += len(g) - len(anchors)
                n_typed += len(anchors)
                bad = anchors[anchors.observation_type != EXPECTED_TYPE]
                if not bad.empty:
                    out.append(Finding("V44", "ERROR", scope,
                                       f"{len(bad)} anchor-year row(s) typed "
                                       f"{sorted(set(bad.observation_type))} — D26 Level II rows "
                                       f"are {EXPECTED_TYPE}"))
                bad = anchors[anchors.quality_grade != EXPECTED_GRADE]
                if not bad.empty:
                    out.append(Finding("V44", "ERROR", scope,
                                       f"{len(bad)} anchor-year row(s) at grade "
                                       f"{sorted(set(bad.quality_grade))} — a D26 proxy is "
                                       f"grade {EXPECTED_GRADE} (§9: a measured proxy, not the anchor)"))
                blank = anchors[anchors.notes.isna() | (anchors.notes.astype(str).str.strip() == "")]
                if not blank.empty:
                    out.append(Finding("V44", "ERROR", scope,
                                       f"{len(blank)} Level II row(s) without a concept note "
                                       "(D26: every proxy carries its concept note)"))
                # provenance: the rows that actually came from the national table
                from_source = g[g.source_id == routing.source_id]
                n_sourced += len(from_source)
                bad = from_source[from_source.concept_flag != proxies.CONCEPT_FLAG]
                if not bad.empty:
                    out.append(Finding("V44", "ERROR", scope,
                                       f"{len(bad)} row(s) from {routing.source_id} without "
                                       f"concept_flag {proxies.CONCEPT_FLAG} (kickoff §5)"))
                bad = from_source[from_source.crosswalk_version != stamp]
                if not bad.empty:
                    out.append(Finding("V44", "ERROR", scope,
                                       f"{len(bad)} row(s) from {routing.source_id} not stamped "
                                       f"with the §11.5 crosswalk {stamp}"))
        # identity: delegated to V19, never recomputed here
        mine = [f for f in v19_errors if f.scope.split("/")[0] == iso3]
        for f in mine:
            out.append(Finding("V44", "ERROR", f.scope,
                               f"remainder + sum(level2) != parent — V19: {f.message}"))
        # memo: D26's one external cross-check, reported and never used
        strict = tables["strict"]
        for code in l2_codes:
            indicator = tree[code].get("gfs_indicator")
            g = strict[(strict.iso3 == iso3) & (strict.line_code == code)
                       & strict.imf_value.notna()]
            if not indicator or g.empty:
                continue
            memo.append(Finding("V44", "OK", f"{iso3}/{code}",
                                f"memo (D26: reported, never used): IMF GFS {indicator} covers "
                                f"{int(g.year.min())}-{int(g.year.max())} ({len(g)} year(s)); the "
                                f"GFSM series runs {g.imf_diff_pct.min():+.1f}% to "
                                f"{g.imf_diff_pct.max():+.1f}% against the built Level II value. "
                                "Cross-check only — no Level II value is taken from it"))

    if out:
        return out
    if not proxied:
        return [Finding("V44", "OK", "-",
                        f"no country names a level2_source: no proxied Level II anywhere "
                        f"({', '.join(unproxied)} take Level II from their own anchor table)")] + memo
    tail = (f"; no proxied Level II for {', '.join(unproxied)} (their anchor family "
            f"publishes Level II itself)" if unproxied else "")
    later = f"; {n_later} stitched/forecast Level II row(s) outside V44's scope" if n_later else ""
    return [Finding("V44", "OK", "-",
                    f"{', '.join(proxied)}: {n_typed} anchor-year Level II row(s) are "
                    f"{EXPECTED_TYPE} at grade {EXPECTED_GRADE} with a concept note, of which "
                    f"{n_sourced} carry the level2_source's concept flag and crosswalk stamp; "
                    f"remainder + sum(level2) = parent (delegated to V19){later}{tail}")] + memo


IMPLEMENTED = {"V44": check_v44}
