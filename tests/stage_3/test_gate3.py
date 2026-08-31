"""Gate 3: every strict forecast row A or B with measured coverage; every D7
line has its note; V-tests green. Plus the §7 machinery Stage 3 introduces:
forward chaining (§7.2), D12 ordering, §7.5 %-GDP handling, §7.10 conversion,
D11 interpolation, and the not-applied C/D records."""

import pandas as pd
import pytest

from ggfiscal import config
from ggfiscal.build import load_canonical
from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(),
                                reason="no snapshots harvested in this environment")


@pytest.fixture(scope="module")
def boundaries():
    path = config.repo_root() / "data" / "canonical" / "forecast_boundaries.csv"
    if not path.exists():
        from ggfiscal.build import build
        build()
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def declarations():
    path = config.repo_root() / "data" / "canonical" / "forecast_declarations.csv"
    return pd.read_csv(path)


def _rows(variant):
    df = pd.concat([load_canonical("COFOG", variant),
                    load_canonical("ESA_REV", variant)], ignore_index=True)
    return df


def _forecast(variant):
    df = _rows(variant)
    return df[df.is_forecast]


def test_gate3_every_strict_forecast_row_a_or_b_with_measured_coverage():
    fc = _forecast("strict")
    assert len(fc) > 0
    assert set(fc.quality_grade) <= {"A", "B"}
    assert fc.coverage_share.notna().all()
    assert fc.coverage_share_year.notna().all()
    assert fc.source_id.notna().all()
    assert fc.crosswalk_version.notna().all()


def test_every_forward_stitch_has_boundary_record(boundaries):
    fc = _forecast("maximum_extension")
    stitched = set(zip(fc.iso3, fc.line_code, fc.growth_source_id))
    applied = boundaries[boundaries.variants.isin(["strict+maximum", "maximum_only"])]
    recorded = set(zip(applied.iso3, applied.line_code, applied.incoming_source))
    assert stitched <= recorded
    assert applied.crosswalk_version.notna().all()
    # strict-tier boundaries are A/B; the maximum-only tier adds C and the
    # §7.9-mandated D (Stage 4)
    strict_tier = applied[applied.variants == "strict+maximum"]
    assert set(strict_tier.grade) <= {"A", "B"}
    assert set(applied.grade) <= {"A", "B", "C", "D"}
    assert applied.coverage_share.notna().all()
    # concept note per stitch (V13 tier)
    assert (applied.scope.astype(str).str.len() >= 20).all()


def test_c_and_d_measurements_recorded_but_not_applied(boundaries):
    skips = boundaries[boundaries.variants.str.startswith("not_applied")]
    assert len(skips) >= 4  # GF10 x2 (C), R05 x3 (C/D), R09 GBR (D), DSM x2 (V16)
    grade_skips = skips[skips.variants.str.startswith("not_applied_grade")]
    assert set(grade_skips.grade) <= {"C", "D"}
    for variant in ("strict", "maximum_extension"):
        fc = _forecast(variant)
        for _, r in skips.iterrows():
            leak = fc[(fc.iso3 == r.iso3) & (fc.line_code == r.line_code)
                      & (fc.growth_source_id == r.incoming_source)]
            assert leak.empty, (r.iso3, r.line_code, r.incoming_source)


def test_forward_arithmetic_is_growth_never_level():
    # §7.2: Y_t = Y_{t-1} x X_t/X_{t-1}, chained from the anchor's last year
    df = _rows("strict")
    fwd = df[df.growth_source_id.notna() & (df.year > df.anchor_year)]
    for (iso3, line), g in fwd.groupby(["iso3", "line_code"]):
        g = g.sort_values("year")
        prev = None
        for _, r in g.iterrows():
            if prev is None:
                anchor = df[(df.iso3 == iso3) & (df.line_code == line)
                            & (df.year == int(r.anchor_year))]
                assert len(anchor) == 1
                base = float(anchor.value_lcu_mn.iloc[0])
                assert r.year == int(r.anchor_year) + 1
                assert abs(r.value_lcu_mn - base * r.growth_rate) \
                    < 1e-6 * max(1.0, base), (iso3, line, r.year)
            elif prev.year == r.year - 1:
                assert abs(r.value_lcu_mn - prev.value_lcu_mn * r.growth_rate) \
                    < 1e-6 * max(1.0, abs(prev.value_lcu_mn)), (iso3, line, r.year)
            prev = r


def test_d12_v16_long_term_leg_withheld_above_threshold(boundaries):
    # FRA/DEU GF01_7: AMECO applies through its 2027 horizon; the DSM leg
    # diverges beyond the V16 threshold in the overlap, so per D12 it is NOT
    # auto-joined — recorded as not_applied_v16_divergence for the committee
    df = _rows("strict")
    for iso3 in ("FRA", "DEU"):
        g = df[(df.iso3 == iso3) & (df.line_code == "GF01_7")
               & df.growth_source_id.notna() & (df.year > df.anchor_year)]
        ameco_years = set(g[g.growth_source_id == "EC_AMECO"].year)
        assert ameco_years and max(ameco_years) == 2027
        assert g[g.growth_source_id == "EC_DSM"].empty
        rec = boundaries[(boundaries.iso3 == iso3)
                         & (boundaries.line_code == "GF01_7")
                         & (boundaries.incoming_source == "EC_DSM")]
        assert len(rec) == 1
        assert rec.variants.iloc[0] == "not_applied_v16_divergence"
        assert "OQ-7" in rec.scope.iloc[0]


def test_newer_actuals_are_not_forecast_rows():
    # §7.2: AMECO 2025 values are actuals on the Spring 2026 vintage
    df = _rows("strict")
    st = df[(df.year == 2025) & (df.growth_source_id == "EC_AMECO")
            & (df.line_code == "GF01_7")]
    assert len(st) == 3  # all three countries stitch 2025
    assert not st.is_forecast.any()
    assert set(st.observation_type) == {"stitched_actual"}


def test_declarations_cover_every_line_without_a_forecast(declarations):
    fc = _forecast("strict")
    have_fc = set(zip(fc.iso3, fc.line_code))
    declared = set(zip(declarations.iso3, declarations.line_code))
    all_lines = set()
    for iso3 in config.COUNTRIES:
        for code in [f"GF{n:02d}" for n in range(1, 11)] + ["GF01_7", "GF01_X", "TE"]:
            all_lines.add((iso3, code))
        for code in [f"R{n:02d}" for n in range(1, 11)] + ["TR"]:
            all_lines.add((iso3, code))
    missing = all_lines - have_fc - declared
    assert not missing, missing
    # every declaration carries a real note
    assert (declarations.note.astype(str).str.len() >= 30).all()


def test_d7_lines_declared_with_notes(declarations):
    d7 = declarations[declarations.status == "no_official_forecast"]
    for iso3 in config.COUNTRIES:
        lines = set(d7[d7.iso3 == iso3].line_code)
        # sources.yaml no_forecast_lines plus GF01 (§7.9) and GF01_X (D10)
        assert {"GF03", "GF04", "GF05", "GF06", "GF08",
                "GF01", "GF01_X", "R08", "R10"} <= lines


def test_gf01x_never_forecast():
    for variant in ("strict", "maximum_extension"):
        fc = _forecast(variant)
        assert fc[fc.line_code == "GF01_X"].empty


def test_strict_forecast_rows_subset_of_maximum():
    key = ["iso3", "line_code", "year"]
    s = set(map(tuple, _forecast("strict")[key].values))
    m = set(map(tuple, _forecast("maximum_extension")[key].values))
    assert s <= m


def test_pct_gdp_sources_record_constructed_gdp():
    # §7.5: AR rows carry the constructed same-source GDP path
    df = _rows("strict")
    ar = df[df.growth_source_id == "EC_AGEING_2024"]
    assert len(ar) > 0
    assert (ar.gdp_source_id == "EC_AGEING_2024_constructed").all()
    assert ar.gdp_lcu_mn.notna().all()


def test_fy_to_cy_conversion_710():
    from ggfiscal.forecast.forward import fy_to_cy

    fy = pd.Series({2025: 100.0, 2026: 200.0, 2027: 300.0})
    cy = fy_to_cy(fy)
    # CY_t = 0.25 x FY_{t-1/t} + 0.75 x FY_{t/t+1}; one horizon year consumed
    assert list(cy.index) == [2026, 2027]
    assert cy[2026] == 0.25 * 100 + 0.75 * 200
    assert cy[2027] == 0.25 * 200 + 0.75 * 300


def test_d11_benchmark_interpolation():
    from ggfiscal.forecast.forward import interpolate_benchmarks

    bench = pd.Series({2030: 10.0, 2035: 20.0})
    lin = interpolate_benchmarks(bench, "ratio_linear")
    assert list(lin.index) == [2030, 2031, 2032, 2033, 2034, 2035]
    assert lin[2032] == pytest.approx(14.0)
    assert lin[2035] == 20.0
    comp = interpolate_benchmarks(bench, "level_compound")
    assert comp[2031] / comp[2030] == pytest.approx((2.0) ** (1 / 5))
    assert comp[2035] == 20.0
    with pytest.raises(ValueError):
        interpolate_benchmarks(bench, "nope")


def test_v_suite_green_and_stage3_checks_run():
    from ggfiscal.validate.runner import current_stage, run_all

    assert current_stage() >= 3
    findings = run_all()
    by_id = {}
    for f in findings:
        by_id.setdefault(f.check_id, []).append(f)
    for vid in ("V6", "V10", "V11", "V13", "V15", "V16", "V18"):
        assert vid in by_id and by_id[vid][0].severity != "SKIP", vid
    assert not [f for f in findings if f.severity == "ERROR"]
    # V16 must surface the AMECO-vs-DSM interest divergence as a committee flag
    assert any(f.severity == "WARN" for f in by_id["V16"])
