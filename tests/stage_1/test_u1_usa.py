"""Stage U1 (REPLICATION_KICKOFF.md §12 Stage U1, §10 V44, §11.4, §11.5;
D-S17-001..): the United States has a canonical history from its anchors —
V44 polices the D26 Level II proxy rows, the two U1 crosswalks document the
mappings, the small multiples carry a USA column and the §8.3 history
decomposition runs for the USA and passes V26. Nothing here touches
GBR/FRA/DEU (tools/byte_identity.py --countries is the gate for those)."""

import csv

import pandas as pd
import pytest

from ggfiscal import config
from ggfiscal.standardise import proxies
from ggfiscal.standardise import readers as R
from ggfiscal.validate import u1 as U1
from ggfiscal.validate.runner import V_SUITE_STAGE

needs_harvest = pytest.mark.skipif(
    ("OECD_T12_REV", "USA") not in R.latest_snapshots(),
    reason="USA snapshots not harvested in this environment (run ggfiscal fetch --all)")

CROSSWALK_COLUMNS = ["source_code", "source_label", "target_line", "allocation_pct",
                     "inclusion_note", "consolidation_treatment", "evidence", "reviewer",
                     "crosswalk_version"]
U1_CROSSWALKS = ("OECD_T11_to_COFOG", "BEA_NIPA_to_COFOG")


def _rows(stem: str) -> list[dict]:
    path = config.repo_root() / "crosswalks" / f"{stem}.csv"
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------- stage (§12)

def test_usa_stage_reached_is_one_and_changes_no_behaviour():
    assert config.stage_reached("USA") == 1
    # stage 1 is inside every stage-0/1 cohort and outside the leg cohorts:
    # the build runs backward legs from 2 and forecasts from 3 (D-S16-008)
    assert config.countries_at_stage(1) == config.COUNTRIES
    assert config.countries_at_stage(2) == ("GBR", "FRA", "DEU")
    assert config.countries_at_stage(3) == ("GBR", "FRA", "DEU")


# ------------------------------------------------------- V44 (§10, U1 step 3)

def test_v44_is_registered_at_stage_one_and_implemented():
    assert V_SUITE_STAGE["V44"] == 1
    from ggfiscal.validate import runner

    # the runner must reach the U1 implementation, not report "not implemented"
    findings = {f.check_id for f in runner.run_all()}
    assert "V44" in findings
    assert U1.IMPLEMENTED["V44"] is U1.check_v44


@needs_harvest
def test_v44_passes_on_the_usa_level2_rows_and_names_the_countries_without_a_proxy():
    findings = U1.check_v44()
    assert not [f for f in findings if f.severity != "OK"], [
        (f.scope, f.message) for f in findings if f.severity != "OK"]
    summary = next(f for f in findings if f.scope == "-")
    # 4 Level II lines x 55 anchor years x 2 variants; 3 of them from BEA
    assert "USA: 440 anchor-year Level II row(s)" in summary.message
    assert "330 carry the level2_source's concept flag and crosswalk stamp" in summary.message
    assert "delegated to V19" in summary.message
    assert "no proxied Level II for GBR, FRA, DEU" in summary.message
    # the D26 memo: reported, never used, never WARN or ERROR
    memo = next(f for f in findings if f.scope == "USA/GF01_7")
    assert memo.severity == "OK"
    assert "GF0170_T covers 1980-1989 (10 year(s))" in memo.message
    assert "reported, never used" in memo.message


@needs_harvest
@pytest.mark.parametrize("column,value,needle", [
    ("observation_type", "anchor_actual", "typed"),
    ("quality_grade", "A", "grade"),
    ("notes", "", "without a concept note"),
    ("concept_flag", "d41_gross_accrued", "concept_flag level2_bea_function"),
    ("crosswalk_version", None, "not stamped"),
])
def test_v44_errors_when_a_proxy_row_is_mistyped_ungraded_or_unstamped(
        monkeypatch, column, value, needle):
    """The check must fail on a broken layer, not merely pass on a good one:
    break one column of one USA Level II line and V44 must say so, scoped to
    that line, at ERROR."""
    from ggfiscal.validate import stage1

    tables = {v: df.copy() for v, df in stage1._tables().items()}
    strict = tables["strict"]
    broken = (strict.iso3 == "USA") & (strict.line_code == "GF10_2")
    assert broken.any()
    strict[column] = strict[column].mask(broken, value)
    monkeypatch.setattr(stage1, "_tables", lambda: tables)

    errors = [f for f in U1.check_v44() if f.severity == "ERROR"]
    assert errors, column
    assert any(needle in f.message for f in errors), [f.message for f in errors]
    assert all(f.scope.startswith("USA/GF10_2") for f in errors), [f.scope for f in errors]


def test_v44_reports_ok_for_a_country_without_a_level2_source(monkeypatch):
    """A monkeypatched world where no country names a level2_source: V44 is
    still run and still reports OK, with the explicit 'no proxied Level II'
    message — it never silently skips."""
    blocks = {iso3: dict(b) for iso3, b in config.countries().items()}
    for b in blocks.values():
        b.pop("level2_source", None)
    monkeypatch.setattr(config, "countries", lambda: blocks)
    assert all(proxies.level2_routing(i) is None for i in config.COUNTRIES)
    findings = U1.check_v44()
    assert [f.severity for f in findings] == ["OK"]
    assert "no country names a level2_source: no proxied Level II anywhere" in findings[0].message
    assert all(i in findings[0].message for i in config.COUNTRIES)


# ------------------------------------------- the two U1 crosswalks (§11.4/§11.5)

@pytest.mark.parametrize("stem", U1_CROSSWALKS)
def test_u1_crosswalk_is_present_and_complete(stem):
    path = config.repo_root() / "crosswalks" / f"{stem}.csv"
    assert path.exists(), stem
    rows = _rows(stem)
    assert rows
    for r in rows:
        assert list(r) == CROSSWALK_COLUMNS, stem          # §11.5 columns, in order
        for col in CROSSWALK_COLUMNS:
            assert (r[col] or "").strip(), (stem, r["source_code"], col)
        assert r["reviewer"] == "stage-u1-build"
        assert r["crosswalk_version"] == "1.0"
        assert float(r["allocation_pct"]) == 100.0
    assert config.crosswalk_version(stem) == "1.0"


def test_oecd_t11_crosswalk_maps_every_function_and_records_the_two_findings():
    rows = {r["source_code"]: r for r in _rows("OECD_T11_to_COFOG")}
    assert set(rows) == {f"GF{n:02d}" for n in range(1, 11)} | {"_T"}
    for n in range(1, 11):
        code = f"GF{n:02d}"
        assert rows[code]["target_line"] == code            # the identity mapping (D18)
    assert rows["_T"]["target_line"] == "TE"
    # the GF05 structural zero (D20) and the _T vs OTE wedge, with its range
    assert "STRUCTURAL ZERO (D20" in rows["GF05"]["inclusion_note"]
    assert "structural_zero" in rows["GF05"]["inclusion_note"]
    assert "-665.0" in rows["_T"]["inclusion_note"] and "1,334.8" in rows["_T"]["inclusion_note"]
    assert "never absorbed" in rows["_T"]["inclusion_note"]


def test_bea_nipa_crosswalk_carries_the_four_d26_cells_with_measured_shares():
    rows = {r["source_code"]: r for r in _rows("BEA_NIPA_to_COFOG")}
    cells = {code: meta["bea_nipa"] for code, meta in config.tree_lines("COFOG").items()
             if meta.get("bea_nipa")}
    assert len(cells) == 4
    for line, spec in cells.items():
        key = f"{spec['table']}:{spec['lines'][0]}"
        assert key in rows, line
        assert rows[key]["target_line"] == line
    # the measured 2024 shares of the parent (reports/source_verification_USA.md §5)
    for key, share in (("T31600:5", "0.6962"), ("T31600:38", "0.5815"),
                       ("T31600:40", "0.0161"), ("T31600:14", "0.2685")):
        assert share in rows[key]["evidence"], key
    # GF01_7 is registered but NOT applied: the build takes the D10 fallback
    assert rows["T31600:5"]["inclusion_note"].startswith("REGISTERED, NOT APPLIED")
    for key in ("T31600:38", "T31600:40", "T31600:14"):
        assert rows[key]["inclusion_note"].startswith("APPLIED")
    # OQ-15 on 04.5, resolved on its default (D-S17-002)
    note = rows["T31600:14"]["inclusion_note"]
    assert "OQ-15" in note and "D-S17-002" in note and "Table 3.17" in note


def test_both_u1_crosswalks_reach_the_crosswalks_deliverable():
    path = config.repo_root() / "data" / "canonical" / "crosswalks.csv"
    if not path.exists():
        pytest.skip("crosswalks.csv not built (run: ggfiscal build)")
    df = pd.read_csv(path, dtype=str)
    for stem in U1_CROSSWALKS:
        assert (df.crosswalk == stem).sum() == len(_rows(stem)), stem


# ------------------------------------- the proxy rows carry their crosswalk

@needs_harvest
def test_the_d26_proxy_rows_are_stamped_with_the_bea_crosswalk_and_nothing_else_is():
    from ggfiscal.build import load_canonical

    assert proxies.level2_crosswalk_stamp("USA") == "BEA_NIPA_to_COFOG:1.0"
    assert proxies.level2_crosswalk_stamp("GBR") is None
    df = load_canonical("COFOG", "strict")
    stamped = df[df.crosswalk_version == "BEA_NIPA_to_COFOG:1.0"]
    assert set(stamped.iso3) == {"USA"}
    assert set(stamped.line_code) == {"GF10_2", "GF10_5", "GF04_5"}
    assert len(stamped) == 3 * 55
    assert set(stamped.observation_type) == {"level2_proxy_actual"}
    assert set(stamped.quality_grade) == {"B"}
    assert set(stamped.concept_flag) == {"level2_bea_function"}
    # the interest line is the D10 fallback from the anchor, not a BEA row
    gf017 = df[(df.iso3 == "USA") & (df.line_code == "GF01_7")]
    assert set(gf017.observation_type) == {"level2_proxy_actual"}
    assert set(gf017.quality_grade) == {"B"}
    assert gf017.crosswalk_version.isna().all()
    assert set(gf017.concept_flag) == {"d41_gross_accrued"}
    # no other country's rows moved: anchors carry no crosswalk_version
    others = df[df.iso3 != "USA"]
    assert others.crosswalk_version.isna().all() or \
        not (others.crosswalk_version == "BEA_NIPA_to_COFOG:1.0").any()


# --------------------------- Gate U1: the layer, the charts, the decomposition

@needs_harvest
def test_gate_u1_usa_has_41_lines_and_the_ledger_from_anchors_1970_2024():
    from ggfiscal.build import load_ledger, load_trees

    df = load_trees("strict")
    usa = df[df.iso3 == "USA"]
    codes = {(r.classification, r.line_code) for r in usa.itertuples()
             if r.line_level != "total"}
    assert len(codes) == 41
    assert set(usa.year) == set(range(1970, 2025))
    assert set(usa.observation_type) <= {"anchor_actual", "derived_actual",
                                         "level2_proxy_actual", "structural_zero"}
    assert not usa.is_forecast.any()
    led = load_ledger()
    led = led[(led.iso3 == "USA") & (led.series_variant == "strict")]
    assert set(led.year) == set(range(1970, 2025))
    assert led.ni_lcu_mn.notna().all()


@needs_harvest
def test_gate_u1_small_multiples_render_a_usa_column_for_every_line(tmp_path):
    from ggfiscal.report import small_multiples as SM

    # render to tmp_path: a test never rewrites a committed deliverable
    dest = SM.write(tmp_path / "small_multiples_stage1.html")
    html = dest.read_text(encoding="utf-8")
    assert len(SM.LINE_ORDER) == 41
    for code in SM.LINE_ORDER:
        assert f'"USA {code}"' in html, code
    assert '"USA NLB"' in html
    # one column per configured country, the USA among them
    assert list(config.COUNTRIES) == ["GBR", "FRA", "DEU", "USA"]


@needs_harvest
def test_gate_u1_history_decomposition_runs_for_the_usa_and_passes_v26():
    from ggfiscal.reconcile.dynamics import v26_check

    path = config.repo_root() / "data" / "canonical" / "deficit_dynamics.csv"
    if not path.exists():
        pytest.skip("deficit_dynamics.csv not built (run: ggfiscal reconcile)")
    d = pd.read_csv(path)
    usa = d[(d.iso3 == "USA") & (d.series_variant == "strict")]
    assert set(range(2001, 2025)) <= set(usa.year.astype(int))     # §8.3, Gate U1
    for variant in ("strict", "maximum_extension"):
        assert not list(v26_check(variant)), variant
