"""Write notebooks/briefing_FRA_AFT.ipynb (unexecuted). Execute it with

    jupyter nbconvert --execute --inplace notebooks/briefing_FRA_AFT.ipynb

The notebook re-renders every chart of the AFT briefing from the bundle,
shows them quantised (the chartbook's size rule, D-S9-004), and prints the
tables the briefing quotes. It reads deliverables/ and nothing else.
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
nb = nbf.v4.new_notebook()
cells = []

cells.append(nbf.v4.new_markdown_cell("""# The AFT briefing — France's debt stock, its interest bill, and the 2027 map

Companion to [`../reports/briefing_FRA_AFT_2026-09/briefing.html`](../reports/briefing_FRA_AFT_2026-09/briefing.html)
(D-S12-001). The briefing was written for a meeting with the Agence France
Trésor's Chief Economist on 18 September 2026; this notebook regenerates every
chart and table in it from [`../deliverables/`](../deliverables) and nothing
else, so the numbers can be re-run when the register is refreshed.

Three modules do the work:

* `ggfiscal.report.briefing_fra` — the descriptive charts: the register against
  the AFT's totals, the maturity profile and redemption calendar, the maturity
  trend, the average coupon against the marginal yield, interest by security,
  the OAT–Bund spread, issuance by bucket; plus `key_figures.csv`.
* `ggfiscal.debt.simulate` — the yield-path simulation `DEBT_KICKOFF.md` §1 said
  the register was shaped for: the stock rolled forward year by year under a
  **declared** primary-balance path, spread path, bill stock and tenor mix, with
  interest feeding back into the deficit. Six scenarios: the current path, the
  four 2027 configurations (Le Pen / Philippe × majority / hung) and one rupture
  stress. Every parameter is a number in `BASELINE` or `SCENARIOS`.
* `ggfiscal.report.briefing_fra_scenarios` — the scenario charts, the spread-vs-
  volume decomposition of each scenario's interest gap, and the mark-to-market
  sensitivity (duration) of the stock.

Nothing here enters the canonical layer or the bundle: the outputs live under
`reports/briefing_FRA_AFT_2026-09/`.
"""))

cells.append(nbf.v4.new_code_cell("""import io
from pathlib import Path

import pandas as pd
from IPython.display import Image as Image_display, display
from PIL import Image

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents]
            if (p / "deliverables" / "debt_securities.csv").exists())
OUT = ROOT / "reports" / "briefing_FRA_AFT_2026-09" / "figures"

from ggfiscal.report import briefing_fra, briefing_fra_scenarios
from ggfiscal.debt import simulate as sim

FIGS = briefing_fra.render_all(OUT)
FIGS.update(briefing_fra_scenarios.render_all(OUT))
pd.set_option("display.width", 160)


def show(key, colours=48, width=880):
    \"\"\"Display a rendered PNG quantised to a small palette (D-S9-004: keep the
    notebook renderable on GitHub).\"\"\"
    im = Image.open(FIGS[key]).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    small = im.quantize(colours, dither=Image.Dither.NONE)
    buf = io.BytesIO(); small.save(buf, format="PNG", optimize=True)
    display(Image_display(data=buf.getvalue()))


print(f"{len(FIGS)} charts rendered into {OUT.relative_to(ROOT)}")"""))

cells.append(nbf.v4.new_markdown_cell("## 1. Where the stock stands\n\nThe register at the AFT's latest snapshot (10 September 2026) against the office's own totals, then the maturity profile, the redemption calendar, and what fell due each year since 2000 (`refinancing_by_year.csv`) to put the 2027–2029 redemptions in context."))
cells.append(nbf.v4.new_code_cell("pd.read_csv(OUT / 'key_figures.csv').set_index('metric').value.round(3).to_frame().T.T"))
for k in ("stock_by_class", "maturity_profile", "redemption_calendar", "refinancing_history"):
    cells.append(nbf.v4.new_code_cell(f"show('{k}')"))

cells.append(nbf.v4.new_markdown_cell("## 2. The interest bill\n\nGeneral-government interest (the strict `GF01_7`, with its EC AMECO / DSM leg), the ledger, the average coupon against the marginal yield, and interest by security against the official totals."))
for k in ("interest_gg", "ledger", "coupon_vs_yield", "interest_by_security"):
    cells.append(nbf.v4.new_code_cell(f"show('{k}')"))

cells.append(nbf.v4.new_markdown_cell("## 3. The shortening stock"))
for k in ("maturity_trend", "issuance_by_bucket"):
    cells.append(nbf.v4.new_code_cell(f"show('{k}')"))

cells.append(nbf.v4.new_markdown_cell("""## 4. The simulation

The engine's calibrations, computed from the bundle rather than declared: the
share of the general-government deficit the État's negotiable debt has
financed (Δ(F.31+F.32) over −NLB, 2015–2025) and the wedge between the
register's interest and `GF01_7` in 2025."""))
cells.append(nbf.v4.new_code_cell("sim.calibration()"))
cells.append(nbf.v4.new_markdown_cell("The declared scenarios, exactly as the engine reads them."))
cells.append(nbf.v4.new_code_cell("""pd.DataFrame([{"scenario": s.name, "label": s.label, "primary balance dev (pp GDP)": s.pb_deviation,
               "10y spread (bp)": s.spread_bp, "bill stock (EUR bn)": s.btf_stock, "tenor tilt": s.maturity_tilt}
              for s in sim.SCENARIOS]).set_index("scenario")"""))
cells.append(nbf.v4.new_code_cell("""RES = pd.read_csv(OUT / "scenarios_FRA.csv")
cols = ["label", "year", "spread_bp", "oat_10y_pct", "gg_interest_bn", "gg_interest_pct_gdp",
        "deficit_pct_gdp", "debt_pct_gdp", "mlt_gross_issuance_bn", "avg_coupon_fixed_pct"]
RES[RES.year.isin([2027, 2028, 2030, 2032, 2035])][cols].round(2).set_index(["label", "year"])"""))
for k in ("scen_interest", "scen_spread", "scen_deficit", "scen_debt", "scen_issuance", "scen_coupon"):
    cells.append(nbf.v4.new_code_cell(f"show('{k}')"))
cells.append(nbf.v4.new_markdown_cell("""### The wrong-way loop, decomposed

Each scenario's extra interest over the current path, split by re-running one
lever at a time: the spread alone (price), the primary balance and issuance
strategy alone (volume), and what is left (the interaction: extra issuance
that the extra interest itself requires, priced at the wider spread)."""))
cells.append(nbf.v4.new_code_cell("pd.read_csv(OUT / 'scenario_decomposition.csv').round(1).set_index(['label', 'year'])"))
cells.append(nbf.v4.new_code_cell("show('scen_decomposition')"))
cells.append(nbf.v4.new_markdown_cell("""## 5. Rate sensitivity of the stock

Every bond in the register priced at the Bund curve plus 90 bp (linkers on
real yields), with its modified duration; the sum is what a 100 bp move does
to the market value of the OAT stock, and where in the curve it sits."""))
cells.append(nbf.v4.new_code_cell("sim.duration_summary(90.0)"))
cells.append(nbf.v4.new_code_cell("show('duration')"))
cells.append(nbf.v4.new_code_cell("""d = sim.duration_table(90.0)
d.sort_values("value_per_bp_mn", ascending=False).head(12)[["name", "class", "nominal_bn", "years_to_maturity", "yield_pct", "price", "modified_duration", "value_per_bp_mn"]].round(2)"""))

nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                  "language_info": {"name": "python"}}
out = ROOT / "notebooks" / "briefing_FRA_AFT.ipynb"
nbf.write(nb, out)
print("wrote", out)
