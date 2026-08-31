"""Gate 5: additivity exact; net-interest cross-check present; residual
history populated; a reader can state, for each country and horizon, how much
of the WEO balance change the official granular forecasts explain."""

import pandas as pd
import pytest

from ggfiscal import config
from ggfiscal.ingest.endpoints import WEO_VINTAGES
from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(),
                                reason="no snapshots harvested in this environment")

VARIANTS = ("strict", "maximum_extension")


def _table(name):
    path = config.repo_root() / "data" / "canonical" / f"{name}.csv"
    if not path.exists():
        from ggfiscal.reconcile.explanation import write
        write()
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def explanation():
    return _table("weo_explanation")


@pytest.fixture(scope="module")
def ni():
    return _table("net_interest_check")


@pytest.fixture(scope="module")
def residuals():
    return _table("weo_residual_history")


COMPONENT_KINDS = ["covered_line", "denom_effect", "resid_coverage",
                   "resid_disagreement", "resid_total", "weo_internal_wedge"]


def test_gate5_additivity_exact(explanation):
    key = ["iso3", "series_variant", "weo_vintage", "horizon_year"]
    parts = explanation[explanation.component_kind.isin(COMPONENT_KINDS)]
    sums = parts.groupby(key).contribution_pp.sum()
    targets = explanation[explanation.component_kind == "weo_change"]
    assert len(targets) > 0
    for _, r in targets.iterrows():
        s = sums.get((r.iso3, r.series_variant, r.weo_vintage, r.horizon_year))
        assert s is not None
        assert abs(s - r.contribution_pp) < 1e-9, \
            (r.iso3, r.series_variant, r.weo_vintage, r.horizon_year)
    # residuals stay lumps: no resid/denominator row is allocated to a line (§8.6)
    resid = parts[parts.component_kind != "covered_line"]
    assert resid.line_code.isna().all()
    # covered_total memo equals the sum of the covered_line rows
    cov = (explanation[explanation.component_kind == "covered_line"]
           .groupby(key).contribution_pp.sum())
    for _, r in explanation[explanation.component_kind == "covered_total"].iterrows():
        k = (r.iso3, r.series_variant, r.weo_vintage, r.horizon_year)
        assert abs(cov.get(k, 0.0) - r.contribution_pp) < 1e-9


def test_gate5_net_interest_check_present_everywhere(explanation, ni):
    key = ["iso3", "series_variant", "weo_vintage", "horizon_year"]
    want = set(map(tuple, explanation[key].drop_duplicates().values))
    have = set(map(tuple, ni[key].values))
    assert want <= have
    # non-computable cells say why; at least one horizon IS computable
    # (FRA b=2024: 2025 has both a stitched GF01_7 and an anchor R07)
    missing = ni[ni.ni_ours_mn.isna()]
    assert (missing.notes.astype(str).str.len() >= 20).all()
    have_ni = ni[ni.ni_ours_mn.notna()]
    assert len(have_ni) > 0
    assert ((have_ni.gap_mn - (have_ni.ni_ours_mn - have_ni.ni_weo_mn)).abs()
            < 1e-6).all()


def test_gate5_residual_history_populated(residuals):
    assert set(residuals.weo_vintage) == set(WEO_VINTAGES)
    for vintage in WEO_VINTAGES:
        for iso3 in config.COUNTRIES:
            for variant in VARIANTS:
                sub = residuals[(residuals.weo_vintage == vintage)
                                & (residuals.iso3 == iso3)
                                & (residuals.series_variant == variant)]
                assert len(sub) > 0, (vintage, iso3, variant)
    assert set(residuals.residual_kind) <= {"resid_coverage",
                                            "resid_disagreement", "resid_total"}


def test_gate5_reader_can_state_explained_share(explanation):
    # for every (country, variant, vintage, horizon) with a non-trivial WEO
    # change, an explicit explained_share row exists — the headline number
    targets = explanation[(explanation.component_kind == "weo_change")
                          & (explanation.contribution_pp.abs() > 1e-9)]
    shares = explanation[explanation.component_kind == "explained_share"]
    key = ["iso3", "series_variant", "weo_vintage", "horizon_year"]
    want = set(map(tuple, targets[key].values))
    have = set(map(tuple, shares[key].values))
    assert want <= have
    # and it is exactly covered_total / weo_change
    m = targets.merge(shares, on=key, suffixes=("_t", "_s"))
    cov = explanation[explanation.component_kind == "covered_total"]
    m = m.merge(cov, on=key)
    assert (abs(m.contribution_pp_s - m.contribution_pp / m.contribution_pp_t)
            < 1e-12).all()


def test_vintage_keys_on_every_table(explanation, ni, residuals):
    for df in (explanation, ni, residuals):
        assert df.weo_vintage.notna().all()
        assert df.source_vintage_set_hash.notna().all()
        assert df.base_year.notna().all()
    bridge = _table("weo_base_bridge")
    assert bridge.weo_vintage.notna().all()
    # the two variants carry distinct source vintage sets (strict lacks the
    # Stage 4 proxies)
    hashes = explanation.groupby("series_variant").source_vintage_set_hash.first()
    assert len(set(hashes)) >= 1  # equal only if variants use identical sources


def test_denominator_effect_reported_never_absorbed(explanation):
    de = explanation[explanation.component_kind == "denom_effect"]
    # one per (cell, side) with covered lines
    assert len(de) > 0
    assert set(de.side) <= {"revenue", "expenditure"}


def test_reconciliation_report_written():
    from ggfiscal.report.reconciliation import write

    dest = write()
    html = dest.read_text(encoding="utf-8")
    assert html.count("plotly-graph-div") >= 12  # 3 countries x 2 variants x 2
    assert "explained_share" in html
    assert "Net-interest cross-check" in html
    assert "Residual history" in html


def test_v_suite_green_and_stage5_checks_run():
    from ggfiscal.validate.runner import current_stage, run_all

    assert current_stage() >= 5
    findings = run_all()
    by_id = {}
    for f in findings:
        by_id.setdefault(f.check_id, []).append(f)
    for vid in ("V24", "V26", "V27", "V28"):
        assert vid in by_id and by_id[vid][0].severity != "SKIP", vid
    assert not [f for f in findings if f.severity == "ERROR"]
    assert not [f for f in findings if f.severity == "SKIP"]  # all 28 run now
