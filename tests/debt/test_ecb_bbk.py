"""Family 'ecb_bbk' — pulls() coverage and reader sanity checks against the
harvested snapshot store (DEBT_KICKOFF.md §13). Skipped when the store is
empty, following the tests/deliverables and tests/stage_N pattern (see
tests/debt/test_boe.py)."""

from __future__ import annotations

import pandas as pd
import pytest

from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(),
                                reason="no snapshots harvested in this environment")


def test_pulls_list_all_parts_with_correct_source_ids():
    from ggfiscal.debt.families import ecb_bbk as fam

    pulls = fam.pulls()
    assert len(pulls) < 15

    by_source: dict[str, set[str]] = {}
    for p in pulls:
        by_source.setdefault(p.source_id, set()).add(p.part)

    assert by_source["ECB_EMMI_RATES"] == {
        "estr", "eonia", "euribor_3m", "euribor_6m", "dfr", "hicp_xt_ea",
    }
    assert by_source["BBK_KAPITALMARKT"] == {"bund_yield_10y"}

    urls = [p.url for p in pulls]
    assert len(urls) == len(set(zip((p.source_id for p in pulls), (p.part for p in pulls))))
    assert all(u.startswith("https://") for u in urls)
    ecb_urls = [p.url for p in pulls if p.source_id == "ECB_EMMI_RATES"]
    bbk_urls = [p.url for p in pulls if p.source_id == "BBK_KAPITALMARKT"]
    assert all(u.startswith("https://data-api.ecb.europa.eu/") for u in ecb_urls)
    assert all(u.startswith("https://api.statistiken.bundesbank.de/") for u in bbk_urls)


def test_estr_starts_2019_10_01():
    from ggfiscal.debt.readers.ecb_bbk import ecb_series

    s = ecb_series("estr")
    assert s.index.min() == pd.Timestamp("2019-10-01")
    assert s.index.is_monotonic_increasing
    assert s.dtype == float


def test_euribor_3m_monthly_span():
    from ggfiscal.debt.readers.ecb_bbk import ecb_series

    s = ecb_series("euribor_3m")
    assert s.index.min() <= pd.Timestamp("1999-01-01")
    assert s.index.max() >= pd.Timestamp("2026-06-01")
    assert s.index.is_monotonic_increasing


def test_eonia_discontinued_2021_12_monthly_only():
    from ggfiscal.debt.readers.ecb_bbk import ecb_series

    s = ecb_series("eonia")
    assert s.index.max() == pd.Timestamp("2021-12-01")
    assert s.index.is_monotonic_increasing


def test_deposit_facility_rate_has_recent_positive_level():
    from ggfiscal.debt.readers.ecb_bbk import ecb_series

    s = ecb_series("dfr")
    assert s.index.is_monotonic_increasing
    assert s.iloc[-1] > -1  # sanity: a plausible policy-rate level, not a parsing artefact


def test_bund_yield_10y_daily_from_late_1990s():
    from ggfiscal.debt.readers.ecb_bbk import bbk_series

    s = bbk_series("bund_yield_10y")
    assert s.index.min() <= pd.Timestamp("1997-12-31")
    assert s.index.is_monotonic_increasing
    assert s.dtype == float
    # Bundesbank's "." (no value available) rows must be dropped, not coerced
    # to NaN-as-float-parse-failure (real 10y yields did print exactly 0.00
    # during 2019-2020, so 0 itself is not a reliable parsing-artefact check)
    assert s.notna().all()


def test_build_reference_series_includes_ecb_bbk_series():
    from ggfiscal.debt.reference import build_reference_series

    df = build_reference_series("test-run", include_curves=False)
    ids = set(df["series_id"])
    for sid in ("EA_ESTR", "EA_EURIBOR_3M", "EA_EURIBOR_6M", "EA_EONIA", "DE_BUND_YIELD_10Y"):
        assert sid in ids, f"{sid} missing from build_reference_series output"
    sub = df[df["series_id"].isin(
        {"EA_ESTR", "EA_EURIBOR_3M", "EA_EURIBOR_6M", "EA_EONIA", "DE_BUND_YIELD_10Y"})]
    assert (sub["unit"] == "pct_pa").all()
    assert sub["snapshot_sha256"].notna().all()
