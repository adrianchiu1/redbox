"""R0 step 7 (D-S15-007): the notebook tooling seeds a new country's books
by copy and inserts its chartbook blocks; the chart site reads countries
from config. Exercised on a temporary copy of the notebooks with a fourth
country added to a copy of the config — the committed notebooks are never
touched."""

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

from ggfiscal import config

ROOT = config.repo_root()
TOOLS = ROOT / "tools"
NB = ROOT / "notebooks"


def _load_tool(name: str, monkeypatch):
    """Import a tools/ script under a unique module name (they are scripts,
    not a package)."""
    spec = importlib.util.spec_from_file_location(f"_r0_{name}", TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, mod)
    spec.loader.exec_module(mod)
    return mod


def _with_books():
    """The countries whose notebooks exist (the three parent countries; the
    USA of Stage U0 has no books until U6 — kickoff §12)."""
    return {k: v for k, v in config.countries().items()
            if (NB / f"forecasts_{k}_expenditure.ipynb").exists()}


def _three(monkeypatch):
    base = _with_books()
    monkeypatch.setattr(config, "countries", lambda: base)


def _with_jpn(monkeypatch):
    """A fourth country on a copy of the three-country config (the R0 test
    premise: a country with no books and no catalogue rows yet). R0 used a
    synthetic USA; since U0 the real USA has catalogue rows, so the synthetic
    country is JPN — seeded from Germany's books, as R0 designed it."""
    base = _with_books()
    jpn = {**base["DEU"], "name": "Japan", "currency": "JPY",
           "prose_name": "Japan", "aliases": ["Japan", "JP"],
           "anchor_family": "oecd_sna", "perimeter_break": None, "backward_legs": {}}
    monkeypatch.setattr(config, "countries", lambda: {**base, "JPN": jpn})


def _sources(nb):
    return ["".join(c["source"]) for c in nb["cells"]]


@pytest.mark.skipif(not (NB / "chartbook.ipynb").exists(), reason="notebooks absent")
def test_chart_site_reads_countries_from_config(monkeypatch):
    site = _load_tool("build_chartsite", monkeypatch)
    assert site.COUNTRY == config.country_names()
    assert site.COUNTRY["USA"] == "United States"
    assert site.JOIN_NAMES["GBR"] == "the United Kingdom" and site.JOIN_NAMES["USA"] == "the United States"
    assert site.ISO_ALIASES["GBR"] == ("United Kingdom", "UK", "GB")
    assert site._join_names(["GBR", "USA"]) == "the United Kingdom and the United States"


@pytest.mark.skipif(not (NB / "chartbook.ipynb").exists(), reason="notebooks absent")
def test_notebook_tool_is_idempotent_on_the_committed_books(monkeypatch, tmp_path):
    _three(monkeypatch)
    tool = _load_tool("update_notebooks_s11", monkeypatch)
    assert tool.COUNTRIES == config.COUNTRIES and tool.NAME == config.country_names()
    for name in ("chartbook.ipynb", *(f"forecasts_{c}_{t}.ipynb" for c in config.COUNTRIES
                                       for t in ("expenditure", "revenue"))):
        shutil.copy(NB / name, tmp_path / name)
    monkeypatch.setattr(tool, "NB", tmp_path)
    cb = tool.chartbook()
    assert _sources(cb) == _sources(json.loads((NB / "chartbook.ipynb").read_text()))
    for iso3 in config.COUNTRIES:
        book = tool.forecast_book(iso3, "expenditure")
        assert _sources(book) == _sources(json.loads(
            (NB / f"forecasts_{iso3}_expenditure.ipynb").read_text()))


@pytest.mark.skipif(not (NB / "chartbook.ipynb").exists(), reason="notebooks absent")
def test_a_fourth_country_is_seeded_by_copy(monkeypatch, tmp_path):
    _with_jpn(monkeypatch)
    tool = _load_tool("update_notebooks_s11", monkeypatch)
    assert tool.COUNTRIES[-1] == "JPN" and tool.SECTION["JPN"] == 4
    for name in ("chartbook.ipynb", *(f"forecasts_{c}_{t}.ipynb" for c in config.COUNTRIES[:3]
                                       for t in ("expenditure", "revenue"))):
        shutil.copy(NB / name, tmp_path / name)
    monkeypatch.setattr(tool, "NB", tmp_path)

    cb = tool.chartbook()
    srcs = _sources(cb)
    stripped = [s.strip() for s in srcs]
    # the country section, copied from Germany's and retargeted
    assert "---\n\n# 4. Japan (JPN)" in stripped
    i_us = stripped.index("---\n\n# 4. Japan (JPN)")
    i_de = stripped.index("---\n\n# 3. Germany (DEU)")
    assert i_us > i_de
    for call in ('panel("JPN", "expenditure")', 'panel("JPN", "revenue")',
                 *(f'chart("JPN", "{line}")' for line in config.granular_lines("COFOG")),
                 'chart("JPN", "TE")', 'ledger_chart("JPN", "PB")',
                 'weo_chart("JPN", "revenue")', 'weo_chart("JPN", "nlb")'):
        assert call in stripped, call
    assert stripped.index('chart("JPN", "GF01")') > i_us
    assert any(s.startswith("## 4.2 Expenditure") for s in stripped)
    assert any(s.startswith("## 4.4 Balance ledger") for s in stripped)
    # the later sections are renumbered; the WEO sub-section follows Germany's
    assert "---\n\n# 5. Reconciliation to the IMF WEO" in " ".join(stripped)
    assert any(s.startswith("## 5.4 Japan") for s in stripped)
    assert any(s.startswith("## 5.3 Germany") for s in stripped)
    assert stripped.index('weo_chart("JPN", "nlb")') > stripped.index('weo_chart("DEU", "nlb")')
    # the existing countries' cells are untouched: drop the inserted block
    # and the inserted WEO sub-section, ignore section numbers, and the
    # remainder is the committed book cell for cell
    import re

    end_us = next(k for k in range(i_us + 1, len(stripped)) if stripped[k].startswith("---\n\n# "))
    i_weo = stripped.index('weo_chart("JPN", "revenue")') - 1
    rest = stripped[:i_us] + stripped[end_us:i_weo] + stripped[i_weo + 4:]
    committed = [s.strip() for s in _sources(json.loads((NB / "chartbook.ipynb").read_text()))]
    unnumber = lambda s: re.sub(r"^(---\n\n# |## )\d+(\.\d+)?", r"\1N", s)
    assert [unnumber(s) for s in rest] == [unnumber(s) for s in committed]
    # no output survives the copy
    assert all(not c.get("outputs") for c in cb["cells"] if '"JPN"' in "".join(c["source"]))

    # the forecast books: preamble and setup from Germany's, one section per line
    book = tool.forecast_book("JPN", "expenditure")
    srcs = _sources(book)
    assert srcs[0].startswith("# Japan — COFOG expenditure")
    assert "from pathlib import Path" in srcs[1]
    for line in config.granular_lines("COFOG"):
        assert f'levels("JPN", "{line}")' in [s.strip() for s in srcs]
        assert f'share("JPN", "{line}")' in [s.strip() for s in srcs]
    assert not any(s.strip().startswith("fan(") for s in srcs)   # no benchmark yet
    assert '"DEU"' not in "".join(srcs)
    tool.save("forecasts_JPN_expenditure.ipynb", book)
    rev = tool.forecast_book("JPN", "revenue")
    assert 'levels("JPN", "R01")' in [s.strip() for s in _sources(rev)]
    esa = tool.forecast_esa("JPN")
    assert _sources(esa)[0].startswith("# Japan — expenditure by ESA economic type")
    assert 'levels("JPN", "E01")' in [s.strip() for s in _sources(esa)]
    # the committed notebooks are untouched
    assert not (NB / "forecasts_JPN_expenditure.ipynb").exists()
