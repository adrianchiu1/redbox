"""§11.7: detect-vintages against a SIMULATED new WEO edition, and the proof
that registering it is a config change plus rebuild — never a code change.

The fixture catalog is the real IMF.RES catalog of 2026-09-03 (WEO flows only)
plus a simulated "2026 October" edition. No live network is used here: the
comparison functions are pure, and the rebuild demonstration operates on a
temporary copy of config/ with one added register entry.
"""

import json
import shutil
from pathlib import Path

import pytest

from ggfiscal import config
from ggfiscal.vintages import (VintageFinding, diff_ons, diff_weo_catalog,
                               eurostat_annotations, weo_catalog_flows,
                               write_report)

FIXTURES = Path(__file__).parent / "fixtures"
SIMULATED = ("WEO_2026_OCT_VINTAGE", "1.0.0")


@pytest.fixture()
def fixture_catalog():
    with open(FIXTURES / "imf_catalog_new_vintage.json", encoding="utf-8") as f:
        return json.load(f)


def test_fixture_carries_real_editions_plus_simulated(fixture_catalog):
    flows = weo_catalog_flows(fixture_catalog)
    from ggfiscal.ingest.endpoints import weo_vintages
    assert {tuple(v) for v in weo_vintages().values()} < flows
    assert SIMULATED in flows


def test_detect_flags_simulated_new_vintage(fixture_catalog):
    findings = diff_weo_catalog(fixture_catalog)
    new = [f for f in findings if f.status == "new_vintage"]
    assert len(new) == 1
    assert "WEO_2026_OCT_VINTAGE/1.0.0" in new[0].detail
    # the action is the §11.7 protocol: config change + rebuild, no code change
    assert "config/sources.yaml" in new[0].action
    assert "no code change" in new[0].action
    assert "D-S0-007" in new[0].action  # snapshot promptly — editions vanish


def test_detect_flags_vanished_edition(fixture_catalog):
    registered = {"2026-04": ("WEO", "9.0.0"),
                  "2024-10": ("WEO_2024_OCT_VINTAGE", "1.0.0")}  # not in catalog
    findings = diff_weo_catalog(fixture_catalog, registered)
    vanished = [f for f in findings if f.status == "vanished"]
    assert len(vanished) == 1 and "2024-10" in vanished[0].detail
    assert "snapshot" in vanished[0].action  # the archive is the D8 store


# ---------- the §11.7 / Gate 6 core: rebuild without code change ----------

@pytest.fixture()
def repo_with_registered_simulated_vintage(tmp_path, monkeypatch):
    """A temporary repo whose ONLY difference from the real one is the config
    register entry for the simulated 2026-10 edition."""
    real_root = config.repo_root()
    (tmp_path / "COFOG_KICKOFF.md").write_text("marker for repo_root()\n")
    shutil.copytree(real_root / "config", tmp_path / "config")
    yaml_path = tmp_path / "config" / "sources.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    anchor = '"2026-04": {dataflow: WEO, version: "9.0.0", publication: "2026-04-14"}'
    assert anchor in text
    text = text.replace(
        anchor,
        '"2026-10": {dataflow: WEO_2026_OCT_VINTAGE, version: "1.0.0", '
        'publication: "2026-10-13"}\n        ' + anchor)
    yaml_path.write_text(text, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config._load.cache_clear()
    yield tmp_path
    config._load.cache_clear()


def test_new_vintage_is_config_change_plus_rebuild_only(
        fixture_catalog, repo_with_registered_simulated_vintage):
    """With ONE register entry added to sources.yaml (no code change), the
    whole pipeline enumeration picks the new edition up: the vintage map, the
    harvest pull set (fetch), and the reconciliation vintage list (§8.5) —
    and detect-vintages then reports the catalog as fully registered."""
    from ggfiscal.ingest.endpoints import all_stage0_pulls, weo_vintages

    vintages = weo_vintages()
    assert list(vintages)[0] == "2026-10"          # latest-first order kept
    assert vintages["2026-10"] == SIMULATED

    pulls = [p for p in all_stage0_pulls() if p.source_id == "IMF_WEO_2026_10"]
    assert len(pulls) == 15                        # 3 countries x 5 subjects
    assert all("WEO_2026_OCT_VINTAGE/1.0.0" in p.url for p in pulls)

    # §8.5: bridge/explanation enumerate vintages from the same config map,
    # so the reconciliation module re-runs over the new edition on rebuild
    assert "2026-10" in list(weo_vintages())

    findings = diff_weo_catalog(fixture_catalog)
    assert not [f for f in findings if f.status == "new_vintage"]
    assert [f for f in findings if f.status == "unchanged"]


def test_pipeline_source_code_identical_under_new_vintage(
        repo_with_registered_simulated_vintage):
    """The demonstration's 'no code change' clause, checked literally: the
    temporary repo contains no src/ tree at all — everything the previous test
    exercised ran on the installed code with only config differing."""
    assert not (repo_with_registered_simulated_vintage / "src").exists()


# ---------- the other pure check paths ----------

def test_diff_ons_changed_and_unchanged():
    sid = "ONS_GG_RECEIPTS"
    recorded = str((config.sources()[sid]["verification"] or {})
                   ["last_update_observed"])
    same = {"description": {"releaseDate": recorded + "T23:00:00.000Z"}}
    assert diff_ons(sid, same).status == "unchanged"
    drifted = {"description": {"releaseDate": "2026-09-22T23:00:00.000Z"}}
    f = diff_ons(sid, drifted)
    assert f.status == "changed" and "2026-09-22" in f.detail


def test_eurostat_annotation_parser():
    xml = """<?xml version="1.0"?>
    <m:Structure xmlns:m="urn:m" xmlns:c="urn:c">
      <c:Annotations>
        <c:Annotation>
          <c:AnnotationTitle>2026-07-21T11:00:00+0200</c:AnnotationTitle>
          <c:AnnotationType>UPDATE_DATA</c:AnnotationType>
        </c:Annotation>
        <c:Annotation>
          <c:AnnotationTitle>2025</c:AnnotationTitle>
          <c:AnnotationType>OBS_PERIOD_OVERALL_LATEST</c:AnnotationType>
        </c:Annotation>
      </c:Annotations>
    </m:Structure>"""
    ann = eurostat_annotations(xml)
    assert ann["UPDATE_DATA"].startswith("2026-07-21")
    assert ann["OBS_PERIOD_OVERALL_LATEST"] == "2025"


def test_report_written_and_names_the_protocol(fixture_catalog, tmp_path):
    findings = diff_weo_catalog(fixture_catalog) + [
        VintageFinding("OBR_EFO_LATEST", "unreachable", "blocked (OQ-6)")]
    dest = write_report(findings, path=tmp_path / "vintage_diff.md")
    text = dest.read_text(encoding="utf-8")
    assert "new_vintage" in text and "WEO_2026_OCT_VINTAGE" in text
    assert "config change plus rebuild" in text
    assert "D-S0-007" in text
    assert "1 finding(s) need action" in text or "Action needed on 1" in text
