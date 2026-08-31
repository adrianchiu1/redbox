"""Gate 2: every backward stitch has a boundary record, crosswalk version and
grade; V5/V6/V13 run; C-grade rows never leak into strict; stitch arithmetic
follows §7.3 exactly."""

import pandas as pd
import pytest

from ggfiscal import config
from ggfiscal.build import load_canonical
from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(),
                                reason="no snapshots harvested in this environment")


@pytest.fixture(scope="module")
def boundaries():
    path = config.repo_root() / "data" / "canonical" / "stitch_boundaries.csv"
    if not path.exists():
        from ggfiscal.build import build
        build()
    return pd.read_csv(path)


def _stitched(variant):
    """Backward stitches only (year < anchor_year): Stage 3+ also writes
    forward newer-actual stitches, which tests/stage_3+ cover."""
    df = pd.concat([load_canonical("COFOG", variant),
                    load_canonical("ESA_REV", variant)], ignore_index=True)
    return df[(df.observation_type == "stitched_actual")
              & (df.year < df.anchor_year)]


def test_every_stitch_has_boundary_record_grade_and_crosswalk(boundaries):
    st = _stitched("maximum_extension")
    stitched_lines = set(zip(st.iso3, st.line_code, st.growth_source_id))
    applied = boundaries[boundaries.variants != "not_applied_grade_D"]
    recorded = set(zip(applied.iso3, applied.line_code, applied.incoming_source))
    assert stitched_lines == recorded
    assert applied.crosswalk_version.notna().all()
    assert set(applied.grade) <= {"B", "C"}
    assert applied.coverage_share.notna().all()
    assert applied.coverage_share_year.notna().all()


def test_no_c_grade_in_strict_and_c_only_in_maximum():
    strict, maximum = _stitched("strict"), _stitched("maximum_extension")
    assert set(strict.quality_grade) <= {"B"}
    assert (maximum.quality_grade == "C").any()
    # strict stitched rows are a subset of maximum's
    key = ["iso3", "line_code", "year"]
    s = set(map(tuple, strict[key].values))
    m = set(map(tuple, maximum[key].values))
    assert s <= m


def test_stitch_arithmetic_is_growth_never_level():
    # §7.3: Y_t = Y_{t+1} x X_t/X_{t+1}, chained from the anchor's first year
    st = _stitched("maximum_extension")
    for (iso3, line), g in st.groupby(["iso3", "line_code"]):
        g = g.sort_values("year", ascending=False)
        prev = None
        for _, r in g.iterrows():
            if prev is not None and prev.year == r.year + 1:
                assert abs(r.value_lcu_mn - prev.value_lcu_mn * r.growth_rate) \
                    < 1e-6 * max(1.0, abs(prev.value_lcu_mn)), (iso3, line, r.year)
            prev = r


def test_deu_never_extends_below_1991(boundaries):
    st = _stitched("maximum_extension")
    assert st[st.iso3 == "DEU"].year.min() >= 1991


def test_grade_d_sources_recorded_but_not_applied(boundaries):
    d = boundaries[boundaries.variants == "not_applied_grade_D"]
    assert len(d) >= 1
    st = _stitched("maximum_extension")
    for _, r in d.iterrows():
        # no stitched rows from a D-graded (iso3, line, source)
        leak = st[(st.iso3 == r.iso3) & (st.line_code == r.line_code)
                  & (st.growth_source_id == r.incoming_source)]
        assert leak.empty, (r.iso3, r.line_code)


def test_v5_v6_v13_v25_run_and_v6_v13_green():
    from ggfiscal.validate.runner import current_stage, run_all
    assert current_stage() >= 2
    findings = run_all()
    by_id = {}
    for f in findings:
        by_id.setdefault(f.check_id, []).append(f)
    for vid in ("V5", "V6", "V13", "V25"):
        assert vid in by_id and by_id[vid][0].severity != "SKIP", vid
    assert all(f.severity != "ERROR" for f in by_id["V6"])
    assert all(f.severity != "ERROR" for f in by_id["V13"])
    assert not [f for f in findings if f.severity == "ERROR"]


def test_gbr_interest_chain_reaches_1987_via_two_stitches(boundaries):
    b = boundaries[(boundaries.iso3 == "GBR") & (boundaries.line_code == "GF01_7")
                   & (boundaries.variants != "not_applied_grade_D")]
    assert len(b) == 2  # anchor->ONS_PSF_INTEREST at 1995, ->EC_AMECO at 1990
    st = _stitched("strict")
    g = st[(st.iso3 == "GBR") & (st.line_code == "GF01_7")]
    assert g.year.min() == 1987
