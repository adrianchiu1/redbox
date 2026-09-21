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


def _with_usa(monkeypatch):
    base = config.countries()
    usa = {**base["DEU"], "name": "United States", "currency": "USD",
           "prose_name": "the United States", "aliases": ["United States", "US"],
           "anchor_family": "oecd_sna", "perimeter_break": None, "backward_legs": {}}
    monkeypatch.setattr(config, "countries", lambda: {**base, "USA": usa})


def _sources(nb):
    return ["".join(c["source"]) for c in nb["cells"]]


@pytest.mark.skipif(not (NB / "chartbook.ipynb").exists(), reason="notebooks absent")
def test_chart_site_reads_countries_from_config(monkeypatch):
    _with_usa(monkeypatch)
    site = _load_tool("build_chartsite", monkeypatch)
    assert site.COUNTRY == config.country_names()
    assert site.COUNTRY["USA"] == "United States"
    assert site.JOIN_NAMES["GBR"] == "the United Kingdom" and site.JOIN_NAMES["USA"] == "the United States"
    assert site.ISO_ALIASES["GBR"] == ("United Kingdom", "UK", "GB")
    assert site._join_names(["GBR", "USA"]) == "the United Kingdom and the United States"


@pytest.mark.skipif(not (NB / "chartbook.ipynb").exists(), reason="notebooks absent")
def test_notebook_tool_is_idempotent_on_the_committed_books(monkeypatch, tmp_path):
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
    _with_usa(monkeypatch)
    tool = _load_tool("update_notebooks_s11", monkeypatch)
    assert tool.COUNTRIES[-1] == "USA" and tool.SECTION["USA"] == 4
    for name in ("chartbook.ipynb", *(f"forecasts_{c}_{t}.ipynb" for c in config.COUNTRIES[:3]
                                       for t in ("expenditure", "revenue"))):
        shutil.copy(NB / name, tmp_path / name)
    monkeypatch.setattr(tool, "NB", tmp_path)

    cb = tool.chartbook()
    srcs = _sources(cb)
    stripped = [s.strip() for s in srcs]
    # the country section, copied from Germany's and retargeted
    assert "---\n\n# 4. United States (USA)" in stripped
    i_us = stripped.index("---\n\n# 4. United States (USA)")
    i_de = stripped.index("---\n\n# 3. Germany (DEU)")
    assert i_us > i_de
    for call in ('panel("USA", "expenditure")', 'panel("USA", "revenue")',
                 *(f'chart("USA", "{line}")' for line in config.granular_lines("COFOG")),
                 'chart("USA", "TE")', 'ledger_chart("USA", "PB")',
                 'weo_chart("USA", "revenue")', 'weo_chart("USA", "nlb")'):
        assert call in stripped, call
    assert stripped.index('chart("USA", "GF01")') > i_us
    assert any(s.startswith("## 4.2 Expenditure") for s in stripped)
    assert any(s.startswith("## 4.4 Balance ledger") for s in stripped)
    # the later sections are renumbered; the WEO sub-section follows Germany's
    assert "---\n\n# 5. Reconciliation to the IMF WEO" in " ".join(stripped)
    assert any(s.startswith("## 5.4 United States") for s in stripped)
    assert any(s.startswith("## 5.3 Germany") for s in stripped)
    assert stripped.index('weo_chart("USA", "nlb")') > stripped.index('weo_chart("DEU", "nlb")')
    # the existing countries' cells are untouched: drop the inserted block
    # and the inserted WEO sub-section, ignore section numbers, and the
    # remainder is the committed book cell for cell
    import re

    end_us = next(k for k in range(i_us + 1, len(stripped)) if stripped[k].startswith("---\n\n# "))
    i_weo = stripped.index('weo_chart("USA", "revenue")') - 1
    rest = stripped[:i_us] + stripped[end_us:i_weo] + stripped[i_weo + 4:]
    committed = [s.strip() for s in _sources(json.loads((NB / "chartbook.ipynb").read_text()))]
    unnumber = lambda s: re.sub(r"^(---\n\n# |## )\d+(\.\d+)?", r"\1N", s)
    assert [unnumber(s) for s in rest] == [unnumber(s) for s in committed]
    # no output survives the copy
    assert all(not c.get("outputs") for c in cb["cells"] if '"USA"' in "".join(c["source"]))

    # the forecast books: preamble and setup from Germany's, one section per line
    book = tool.forecast_book("USA", "expenditure")
    srcs = _sources(book)
    assert srcs[0].startswith("# United States — COFOG expenditure")
    assert "from pathlib import Path" in srcs[1]
    for line in config.granular_lines("COFOG"):
        assert f'levels("USA", "{line}")' in [s.strip() for s in srcs]
        assert f'share("USA", "{line}")' in [s.strip() for s in srcs]
    assert not any(s.strip().startswith("fan(") for s in srcs)   # no benchmark yet
    assert '"DEU"' not in "".join(srcs)
    tool.save("forecasts_USA_expenditure.ipynb", book)
    rev = tool.forecast_book("USA", "revenue")
    assert 'levels("USA", "R01")' in [s.strip() for s in _sources(rev)]
    esa = tool.forecast_esa("USA")
    assert _sources(esa)[0].startswith("# United States — expenditure by ESA economic type")
    assert 'levels("USA", "E01")' in [s.strip() for s in _sources(esa)]
    # the committed notebooks are untouched
    assert not (NB / "forecasts_USA_expenditure.ipynb").exists()
