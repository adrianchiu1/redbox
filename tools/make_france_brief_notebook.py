"""Write and execute notebooks/France_fiscal_brief_20261013.ipynb (D-S18-003).

The notebook reproduces the AFT briefing note from the flat files: it renders
every chart, shows each section of the note with its text, tables and charts
in the note's order (the questions for the AFT left out), and finishes by
writing reports/briefing_FRA_AFT_2026-09/briefing.html and
briefing_inline.html.

    python3 tools/make_france_brief_notebook.py
"""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbconvert.preprocessors import ExecutePreprocessor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "France_fiscal_brief_20261013.ipynb"

SECTIONS = [("s0", "Bottom line and key figures"), ("s1", None), ("s2", None), ("s3", None),
            ("s4", None), ("s5", None), ("s6", None), ("s9", None), ("s8", None)]

cells = [nbf.v4.new_markdown_cell("""# France fiscal brief, 13 October 2026

French sovereign debt: the interest bill, the shortening stock, who bears the
rate risk, and what five 2027 political configurations do to it, set against
Redbox's own statistical benchmark.

This notebook is the executable form of the briefing note
`reports/briefing_FRA_AFT_2026-09/briefing_inline.html`. Run top to bottom, it

1. renders every chart from the flat files in `deliverables/` (plus the
   Eurostat debt history and balance sheet in `data/manual/`) with
   `ggfiscal.report.briefing_fra` (the descriptive charts and
   `key_figures.csv`), `ggfiscal.report.briefing_fra_scenarios` (the
   register rolled forward under each scenario by `ggfiscal.debt.simulate`)
   and `ggfiscal.report.briefing_fra_balance` (the asset side, net debt and
   the sell-down runs of `ggfiscal.debt.balance_sheet`);
2. fills the note's template with the values `tools/build_briefing_fra.py`
   computes and shows each section in the note's order;
3. writes `briefing.html` and `briefing_inline.html`, so the published page is
   reproduced by this notebook.

The questions for the AFT (section 8 of the note and the "To ask the AFT"
boxes) are left out here; the HTML keeps them. Facts marked **[ext]** come
from outside Redbox and are listed in section 9. Scenario assumptions are in
the tables of section 5; decisions D-S18-001 to D-S18-006 and D-S19-001 (the
balance-sheet section, 7) in `DECISIONS.md`.""")]

cells.append(nbf.v4.new_code_cell("""import io

import pandas as pd
from IPython.display import HTML, SVG, Image as Image_display, display
from PIL import Image

from ggfiscal.debt import simulate as sim
from ggfiscal.report import briefing_fra, briefing_fra_balance, briefing_fra_scenarios, france_brief

FIG = france_brief.BRIEF_DIR / "figures"
FIGS = briefing_fra_scenarios.render_all(FIG)     # scenarios_FRA.csv, decomposition, duration
FIGS.update(briefing_fra.render_all(FIG))         # descriptive charts, key_figures.csv
FIGS.update(briefing_fra_balance.render_all(FIG)) # balance_sheet_FRA.csv, ladder, selldown (D-S19-001)
france_brief.clear_cache()


def show(key, colours=96, width=1200):
    \"\"\"Display a rendered PNG quantised to a small palette (D-S9-004: keep the
    notebook renderable on GitHub).\"\"\"
    im = Image.open(FIGS[key]).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    small = im.quantize(colours, dither=Image.Dither.NONE)
    buf = io.BytesIO(); small.save(buf, format="PNG", optimize=True)
    display(Image_display(data=buf.getvalue()))


def section(sid):
    \"\"\"One section of the note: text and tables as HTML, charts as images.\"\"\"
    for kind, value in france_brief.chunks(sid):
        if kind == "fig":
            show(value)
        elif kind == "svg":
            display(SVG(value))
        else:
            display(HTML(value))


missing = set(france_brief.figures()) - set(FIGS)
assert not missing, missing
print(f"{len(FIGS)} charts rendered into {FIG.relative_to(sim.ROOT)}; "
      f"{len(france_brief.figures())} appear in the brief")"""))

for sid, name in SECTIONS:
    if name is None:
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        from ggfiscal.report import france_brief  # noqa: E402
        name = france_brief.title(sid)
    cells.append(nbf.v4.new_markdown_cell(f"## {name}"))
    cells.append(nbf.v4.new_code_cell(f'section("{sid}")'))

cells.append(nbf.v4.new_markdown_cell("""## The scenario results as data

Every scenario-year the engine produced, at the years the note quotes."""))
cells.append(nbf.v4.new_code_cell("""res = pd.read_csv(FIG / "scenarios_FRA.csv")
cols = ["label", "year", "spread_bp", "oat_10y_pct", "primary_balance_pct", "gg_interest_bn",
        "gg_interest_pct_gdp", "deficit_pct_gdp", "debt_pct_gdp", "mlt_gross_issuance_bn"]
res[res.year.isin([2027, 2028, 2030, 2032, 2035])][cols].round(1).set_index(["label", "year"])"""))

cells.append(nbf.v4.new_markdown_cell("""## The balance-sheet runs as data

The sell-down ladder (what is there at end-2025 and how much each run sells),
then every run-year of section 7: gross and net debt, the interest bill, the
asset income and the net interest, on the status-quo scenario."""))
cells.append(nbf.v4.new_code_cell("""lad = pd.read_csv(FIG / "ladder_FRA.csv")
lad[["label", "where", "liquidity", "stock_bn", "sold_liquidity_bn", "sold_realistic_bn", "sold_maximal_bn", "sold_extreme_bn"]].round(0).set_index("label")"""))
cells.append(nbf.v4.new_markdown_cell("""The ladder line by line (D-S19-002): valuation on the CGE, the APE and Eurostat, who holds
it, whether the État can sell it, what it pays the État, and the amount proposed for each run.
A review table: the runs below still use the first-pass rung totals."""))
cells.append(nbf.v4.new_code_cell("""det = pd.read_csv(FIG / "ladder_detail_FRA.csv", keep_default_na=False)
pd.set_option("display.max_rows", 100); pd.set_option("display.max_colwidth", 70)
det[~det.reference_only][["group", "line", "holder", "stock_bn", "can_sell", "liquidity", "income_bn", "yield_pct",
                          "sold_liquidity_bn", "sold_realistic_bn", "sold_everything_bn"]].round(2).set_index(["group", "line"])"""))
cells.append(nbf.v4.new_code_cell("""sd = pd.read_csv(FIG / "selldown_FRA.csv")
cols = ["run_label", "year", "sfa_bn", "debt_pct_gdp", "net_debt_pct_gdp", "net_fin_debt_pct_gdp", "gg_interest_bn",
        "asset_income_bn", "net_interest_bn", "deficit_pct_gdp", "primary_balance_pct"]
sd[sd.year.isin([2027, 2030, 2035])][cols].round(1).set_index(["run_label", "year"])"""))

cells.append(nbf.v4.new_markdown_cell("""## Reproducing the HTML note

Writes `briefing.html` (figures by relative path) and `briefing_inline.html`
(figures embedded, the page that is published) from the template, the values
and the charts rendered above, and checks that every chart is embedded."""))
cells.append(nbf.v4.new_code_cell("""inline = france_brief.builder().main()
page = inline.read_text()
n_img = page.count('<img src="data:image/png;base64,')
assert "{{" not in page and n_img == len(france_brief.figures()), n_img
print(f"{inline.relative_to(sim.ROOT)}: {inline.stat().st_size / 1e6:.2f} MB, {n_img} charts embedded")"""))

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                  "language_info": {"name": "python"}}

if __name__ == "__main__":
    ExecutePreprocessor(timeout=900, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(ROOT / "notebooks")}})
    nbf.write(nb, OUT)
    print("wrote", OUT)
