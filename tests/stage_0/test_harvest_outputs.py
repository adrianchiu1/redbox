"""Measurements against the harvested snapshot store (skip when empty)."""

import pytest

from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(),
                                reason="no snapshots harvested in this environment")


def test_anchor_units_agree_with_imf_gfs():
    # Same national data redistributed: FRA GF02 should match to <0.5% —
    # this pins the unit scaling (GFS raw units -> millions) as much as the mapping.
    from ggfiscal.standardise import readers as R

    a = R.eurostat_cofog("FRA", "GF02")
    g = R.gfs_series("FRA", "cofog", "GF02_T")
    overlap = a.index.intersection(g.index)
    assert len(overlap) > 20
    for t in overlap:
        assert abs(g[t] - a[t]) / a[t] < 0.005, (t, a[t], g[t])


def test_ons_t2_headline_rows_resolve():
    from ggfiscal.standardise import readers as R

    tr = R.ons_t2_series("OTR", "")
    te = R.ons_t2_series("OTE", "")
    b9 = R.ons_t2_series("B9", "")
    assert tr.index.min() == 1990
    overlap = tr.index.intersection(te.index).intersection(b9.index)
    # accounting identity TR - TE = B9 in the anchor (V23 preview)
    for t in overlap:
        assert abs((tr[t] - te[t]) - b9[t]) <= 1.0, t  # £1m rounding


def test_weo_latest_vintage_has_base_year_attributes():
    from ggfiscal.standardise import readers as R

    for iso3 in ("GBR", "FRA", "DEU"):
        assert R.weo_latest_actual("2026-04", iso3, "GGXCNL") is not None, iso3


def test_bridge_computes_for_all_countries_on_latest_vintage():
    from ggfiscal.reconcile import bridge

    for iso3 in ("GBR", "FRA", "DEU"):
        anchor = bridge.anchor_aggregates(iso3)
        b = bridge.base_year("2026-04", iso3, anchor)
        assert b is not None and b >= 2023, (iso3, b)


def test_oecd_rs_reaches_1965():
    from ggfiscal.standardise import readers as R

    for iso3 in ("GBR", "FRA", "DEU"):
        s = R.oecd_rs_heading(iso3, "T_1100")
        assert s.index.min() == 1965, iso3  # D15: RS history from 1965
