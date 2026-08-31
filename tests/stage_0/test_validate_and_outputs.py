"""The validation runner and generated register/coverage outputs."""

import csv

from ggfiscal import config, coverage, register
from ggfiscal.validate import runner


def test_validate_no_errors_at_stage_0():
    findings = runner.run_all()
    errors = [f for f in findings if f.severity == "ERROR"]
    assert errors == [], [f"{f.check_id}: {f.message}" for f in errors]


def test_v_suite_all_28_accounted_for():
    assert len(runner.V_SUITE_STAGE) == 28
    findings = runner.run_all()
    reported = {f.check_id for f in findings}
    for vid in runner.V_SUITE_STAGE:
        assert vid in reported


def test_exceptions_csv_written(tmp_path):
    findings = runner.run_all()
    dest = runner.write_exceptions(findings, path=tmp_path / "exceptions.csv")
    rows = list(csv.DictReader(open(dest)))
    assert len(rows) == len(findings)


def test_coverage_v0_has_66_rows(tmp_path):
    dest = coverage.build_v0(path=tmp_path / "coverage_matrix_v0.csv")
    rows = list(csv.DictReader(open(dest)))
    assert len(rows) == 66
    # candidate sources known for every line even pre-harvest
    for row in rows:
        assert row["candidate_sources"], f"{row['iso3']}/{row['line_code']} has no candidate source"
    # D7 notes present where declared
    gf03 = [r for r in rows if r["line_code"] == "GF03"]
    assert all("D7" in r["notes"] for r in gf03)


def test_source_register_csv(tmp_path):
    dest = register.build(path=tmp_path / "source_register.csv")
    rows = list(csv.DictReader(open(dest)))
    assert {r["source_id"] for r in rows} >= {"IMF_WEO", "EC_AMECO", "ONS_ESA_T11",
                                              "EUROSTAT_GOV10A_EXP", "OECD_RS"}
    weo = next(r for r in rows if r["source_id"] == "IMF_WEO")
    assert weo["role"] == "reconciliation_only"
    assert weo["latest_vintage"] == "2026-04"
