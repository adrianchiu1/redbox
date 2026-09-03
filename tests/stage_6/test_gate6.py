"""Gate 6: any stitched value reproducible from anchor and recorded growth
using ONLY deliverables; all §1 objectives met; the §11.6 packaging complete
(generated README, validation report, crosswalks.csv, run-manifest
completeness).

The reproducibility proof deliberately reads nothing but the published CSVs:
each stitched or forecast row records its per-year growth factor and its
anchor, so the value must equal the neighbouring year's value times the
recorded growth — chained, this reconstructs every stitched observation from
the anchor without touching the pipeline's source code or raw data.
"""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from ggfiscal import config
from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(),
                                reason="no snapshots harvested in this environment")

CANONICAL = config.repo_root() / "data" / "canonical"
VARIANTS = ("strict", "maximum_extension")
ANCHOR_TYPES = {"anchor_actual", "derived_actual", "level2_proxy_actual",
                "imf_actual", "official_benchmark_interpolation"}
RTOL = 1e-9


def _tree(stem: str, variant: str) -> pd.DataFrame:
    return pd.read_csv(CANONICAL / f"{stem}_{variant}.csv")


@pytest.fixture(scope="module")
def trees():
    return {(stem, variant): _tree(stem, variant)
            for stem in ("expenditure_long", "revenue_long")
            for variant in VARIANTS}


# ---------- Gate 6 core: reproducibility from deliverables alone ----------

def test_gate6_stitched_values_reproduce_from_anchor_and_recorded_growth(trees):
    checked = 0
    for (stem, variant), df in trees.items():
        for (iso3, line), g in df.groupby(["iso3", "line_code"]):
            values = dict(zip(g.year, g.value_lcu_mn))
            derived = g[g.growth_rate.notna()]
            for _, r in derived.iterrows():
                neighbour = r.year + 1 if r.year < r.anchor_year else r.year - 1
                assert neighbour in values, \
                    (stem, variant, iso3, line, r.year, "chain gap")
                expected = values[neighbour] * r.growth_rate
                assert expected == pytest.approx(r.value_lcu_mn, rel=RTOL), \
                    (stem, variant, iso3, line, r.year)
                # the recorded anchor is itself in the deliverable, unchanged
                assert r.anchor_year in values
                assert values[r.anchor_year] == pytest.approx(
                    r.anchor_value, rel=RTOL), (stem, variant, iso3, line)
                checked += 1
    assert checked > 900  # backward + forward stitches across all four tables


def test_gate6_anchor_rows_carry_their_own_values(trees):
    for (stem, variant), df in trees.items():
        anchors = df[df.observation_type.isin(ANCHOR_TYPES)
                     & df.anchor_value.notna()]
        assert len(anchors) > 0
        pd.testing.assert_series_equal(
            anchors.value_lcu_mn, anchors.anchor_value,
            check_names=False, rtol=RTOL)


def test_gate6_every_derived_row_names_source_and_growth(trees):
    """No stitched/forecast row without full stitch provenance (§5)."""
    for (stem, variant), df in trees.items():
        derived = df[~df.observation_type.isin(ANCHOR_TYPES)]
        assert derived.growth_source_id.notna().all()
        assert derived.growth_rate.notna().all()
        assert derived.anchor_year.notna().all()
        assert derived.anchor_value.notna().all()


# ---------- §1 objectives ----------

def test_gate6_all_66_series_built_both_variants(trees):
    for variant in VARIANTS:
        built = set()
        for stem in ("expenditure_long", "revenue_long"):
            df = trees[(stem, variant)]
            built |= set(map(tuple, df[["iso3", "classification", "line_code"]]
                             .drop_duplicates().values))
        want = set(config.line_universe())
        assert want <= built, want - built


def test_gate6_balance_ledger_and_reconciliation_objectives():
    ledger = pd.read_csv(CANONICAL / "balance_ledger.csv")
    assert ledger.nlb_lcu_mn.to_numpy() == pytest.approx(
        (ledger.tr_lcu_mn - ledger.te_lcu_mn).to_numpy(), abs=1e-6)
    complete = ledger[ledger.complete_both_sides]
    assert len(complete) > 0
    assert complete.pb_lcu_mn.to_numpy() == pytest.approx(
        (complete.nlb_lcu_mn + complete.ni_lcu_mn).to_numpy(), abs=1e-6)
    # the reconciliation objective (§1.3): decomposition tables exist for
    # every registered vintage and both variants
    exp = pd.read_csv(CANONICAL / "weo_explanation.csv")
    from ggfiscal.ingest.endpoints import weo_vintages
    assert set(exp.weo_vintage) == set(weo_vintages())
    assert set(exp.series_variant) == set(VARIANTS)


# ---------- §11.6 packaging ----------

def test_gate6_crosswalks_csv_is_the_concatenation():
    cw = pd.read_csv(CANONICAL / "crosswalks.csv", dtype=str)
    files = sorted((config.repo_root() / "crosswalks").glob("*.csv"))
    assert set(cw.crosswalk) == {p.stem for p in files}
    total = sum(len(pd.read_csv(p, dtype=str)) for p in files)
    assert len(cw) == total
    # §11.5 columns survive intact
    for col in ("source_code", "target_line", "allocation_pct",
                "crosswalk_version", "evidence"):
        assert col in cw.columns


def test_gate6_readme_generated_from_build():
    text = (config.repo_root() / "README.md").read_text(encoding="utf-8")
    assert "GENERATED FILE" in text and "ggfiscal report" in text
    # measured content, not boilerplate: coverage rows and the §11.6 inventory
    for needle in ("coverage_matrix.csv", "| GF01_7 |", "explained_share",
                   "config change plus rebuild", "D-S0-007"):
        assert needle in text, needle


def test_gate6_validation_report_written_and_green():
    html = (config.repo_root() / "reports" / "validation_report.html"
            ).read_text(encoding="utf-8")
    assert "No ERROR findings: the gate holds" in html
    for vid in ("V26", "V27", "V28"):
        assert vid in html
    assert "OQ-7" in html  # the WARN tiers are explained, not hidden


def test_gate6_vintage_diff_written():
    text = (config.repo_root() / "reports" / "vintage_diff.md"
            ).read_text(encoding="utf-8")
    assert "§11.7" in text and "config change plus rebuild" in text


def test_gate6_run_manifest_completeness():
    from ggfiscal import manifest as M

    path = M.latest_run_path()
    assert path is not None
    doc = json.loads(path.read_text(encoding="utf-8"))
    for key in ("run_id", "config_files", "crosswalk_files", "snapshots",
                "deliverables", "environment"):
        assert key in doc, key
    assert len(doc["snapshots"]) >= 70          # the full harvest set
    root = config.repo_root()
    # every config and crosswalk hash matches the file on disk
    for name, sha in doc["config_files"].items():
        assert hashlib.sha256((root / "config" / name).read_bytes()
                              ).hexdigest() == sha, name
    for name, sha in doc["crosswalk_files"].items():
        assert hashlib.sha256((root / "crosswalks" / name).read_bytes()
                              ).hexdigest() == sha, name
    # every §11.6 deliverable is present, and the recorded hash matches disk
    # for the data files (the HTML reports are regenerated with fresh plotly
    # ids by the stage_5 tests themselves, so presence suffices there)
    assert set(doc["deliverables"]) == set(M.DELIVERABLES)
    for rel, entry in doc["deliverables"].items():
        assert entry.get("present"), rel
        if Path(rel).suffix in (".csv", ".parquet"):
            assert hashlib.sha256((root / rel).read_bytes()
                                  ).hexdigest() == entry["sha256"], rel


def test_gate6_v_suite_green_all_checks_run():
    from ggfiscal.validate.runner import run_all

    findings = run_all()
    assert not [f for f in findings if f.severity == "ERROR"]
    assert not [f for f in findings if f.severity == "SKIP"]
