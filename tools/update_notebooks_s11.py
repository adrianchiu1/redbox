"""One-off cell surgery for session 11 (D-S11-001..004): add the GF10_2 /
GF10_X pension split to the chartbook and the expenditure forecast books,
create the ESA_EXP companion books, and refresh the prose that cites series
counts. Idempotent: running it twice leaves the notebooks unchanged.
Execution (outputs) happens afterwards with nbconvert."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks"
COUNTRIES = ("GBR", "FRA", "DEU")
SECTION = {"GBR": 1, "FRA": 2, "DEU": 3}
CAT = pd.read_csv(ROOT / "deliverables" / "series_catalogue.csv")
FC = pd.read_csv(ROOT / "deliverables" / "statistical_forecasts.csv")
ESA_LINES = [f"E{n:02d}" for n in range(1, 10)]


def load(name):
    return json.loads((NB / name).read_text(encoding="utf-8"))


def save(name, nb):
    (NB / name).write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n",
                           encoding="utf-8")


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": text}


def src(cell):
    return "".join(cell["source"]).strip()


def index_of(cells, needle):
    for i, c in enumerate(cells):
        if src(c).startswith(needle):
            return i
    raise KeyError(needle)


# ------------------------------------------------------------- chartbook

def chartbook():
    nb = load("chartbook.ipynb")
    cells = nb["cells"]
    if not any(src(c) == 'chart("GBR", "GF10_2")' for c in cells):
        for iso3 in COUNTRIES:
            i = index_of(cells, f'chart("{iso3}", "GF10")')
            cells[i + 1:i + 1] = [code(f'chart("{iso3}", "GF10_2")'),
                                  code(f'chart("{iso3}", "GF10_X")')]
    # setup: read the economic tree too, so the seams table and the
    # no-projection table cover every published series
    setup = cells[index_of(cells, "import io")]
    s = "".join(setup["source"])
    if 'load("expenditure_esa")' not in s:
        s = s.replace('EXPENDITURE = load("expenditure_cofog")\nREVENUE = load("revenue_esa")\n'
                      'TREE = pd.concat([EXPENDITURE, REVENUE], ignore_index=True)',
                      'EXPENDITURE = load("expenditure_cofog")\n'
                      'ECONOMIC = load("expenditure_esa")   # the ESA_EXP tree, charted in chartbook_esa.ipynb\n'
                      'REVENUE = load("revenue_esa")\n'
                      'TREE = pd.concat([EXPENDITURE, ECONOMIC, REVENUE], ignore_index=True)')
        assert 'ECONOMIC = load' in s
        setup["source"] = s
    # prose
    how = cells[index_of(cells, "## How to read a chart")]
    h = "".join(how["source"])
    h = h.replace("Four series per country\n  carry long-term legs beyond it (`GF07`, `GF09`, `GF10` to 2070 and `GF01_7`\n  to 2036)",
                  "Five series per country\n  carry long-term legs beyond it (`GF07`, `GF09`, `GF10` and the old-age\n  pension line `GF10_2` to 2070, and `GF01_7` to 2036)")
    how["source"] = h
    fit = cells[index_of(cells, "## Series that do not fit this schema")]
    f = "".join(fit["source"])
    f = f.replace("Ten things sit awkwardly", "Twelve things sit awkwardly")
    f = f.replace("and all ten are visible", "and all twelve are visible")
    f = f.replace("2. **`GF01_X` is an identity, not a source.** It is `GF01 − GF01_7`, and by\n"
                  "   construction it is never forecast. Its chart always stops at the last\n"
                  "   outturn, and it is the only expenditure line that does.",
                  "2. **`GF01_X` and `GF10_X` are identities, not sources.** They are\n"
                  "   `GF01 − GF01_7` and `GF10 − GF10_2`, and by construction they are never\n"
                  "   forecast. Their charts always stop at the last outturn, and they are the\n"
                  "   only expenditure lines that do so by design.")
    f = f.replace("3. **`TE` and `TR` are totals, not members of the 66 line series.**",
                  "3. **`TE`, `TE_ESA` and `TR` are totals, not members of the 99 line series.**")
    if "11. **The economic tree" not in f:
        f = f.rstrip() + """
11. **The economic tree is a second cut of the same money.** `E01`–`E09`
    (compensation, intermediate consumption, social benefits in cash, social
    transfers in kind, interest, subsidies, other current, capital formation,
    capital transfers) sum to `TE_ESA`, which for France and Germany *is* the
    COFOG `TE` and for the UK is the ESA Table 2 total. Never add an `E` line
    to a `GF` line. Those charts live in
    [`chartbook_esa.ipynb`](chartbook_esa.ipynb), the companion to this book,
    so that this one stays small enough for GitHub to render.
12. **The pension line and the social-benefits line are different concepts
    of "pensions".** `GF10_2` is COFOG 10.2 Old age — everything the function
    spends, cash benefits plus administration and in-kind services — and it
    is what the Ageing Report projects to 2070 for France and Germany. `E03`
    is ESA D.62, every cash benefit across every function. Old age is about
    two thirds of `E03`; the rest is sickness, family, unemployment and other
    benefits.
"""
    fit["source"] = f
    return nb


def chartbook_esa(chartbook_nb):
    """The companion: same setup cell, the economic tree only."""
    base = copy.deepcopy(chartbook_nb)
    cells = base["cells"]
    setup = cells[index_of(cells, "import io")]
    intro = md("""# Chartbook — expenditure by ESA economic type

The companion to [`chartbook.ipynb`](chartbook.ipynb), which explains how to
read every chart here (levels, seams, projection shading, captions). This book
holds the third tree, **expenditure by ESA economic type** (`ESA_EXP`,
D-S11-003): nine lines per country that sum to `TE_ESA`, a second cut of the
same total expenditure as the COFOG functions — so an `E` line must never be
added to a `GF` line.

| line | ESA | what it is |
|---|---|---|
| `E01` | D.1 | compensation of employees |
| `E02` | P.2 | intermediate consumption |
| `E03` | D.62 | social benefits other than social transfers in kind — every cash benefit, all functions |
| `E04` | D.632 | social transfers in kind via market producers (purchased health care, etc.) |
| `E05` | D.41 | interest payable — the economic-type twin of COFOG `GF01_7` |
| `E06` | D.3 | subsidies |
| `E07` | D.29 + D.5 + (D.4 − D.41) + D.7 + D.8 | other current expenditure |
| `E08` | P.5 + NP | gross capital formation and net acquisitions of non-produced assets |
| `E09` | D.9 | capital transfers payable |
| `TE_ESA` | total | their sum: the ESA main-aggregates total expenditure |

Sources: Eurostat `gov_10a_main` payable items for France and Germany, ONS ESA
Table 2 payable rows for the UK — the same institution as each country's
anchor, so the identity `E01 + … + E09 = TE_ESA` is exact in every outturn
year (V2). Forecasts: AMECO carries every line on the same ESA concept, so
`E01`–`E07` project to 2027 at grade A for France and Germany; the UK's
compensation, intermediate consumption and other-current lines have no AMECO
history to measure coverage on and stop at the last outturn; `E08` and `E09`
have partial components only (§7.8 proxies, `maximum_extension`). Backward,
AMECO takes the French lines to 1978, the German ones to 1991, the UK ones to
1987 where the UK history exists.

Every caption states the recipe and how far each variant projects, exactly as
in the main book; "no projection published" and its five reasons mean the same
thing here.
""")
    out = [intro, setup]
    for iso3 in COUNTRIES:
        name = {"GBR": "United Kingdom", "FRA": "France", "DEU": "Germany"}[iso3]
        out.append(md(f"## {SECTION[iso3]}. {name} — expenditure by ESA economic type\n\n"
                      "Nine economic lines and their total. `E03` (cash social benefits) "
                      "and `E05` (interest) are the two that other publications forecast "
                      "directly; read `E05` against `GF01_7` in the main book."))
        for line in ESA_LINES + ["TE_ESA"]:
            out.append(code(f'chart("{iso3}", "{line}")'))
    out.append(md("---\n\n## Seams in the economic tree\n\nThe same triage table as the "
                  "main book's §6, restricted to the `E` lines: every year where the "
                  "source or method changes, with the year-on-year step across it."))
    out.append(code('''rows = []
for (iso3, line), g in ECONOMIC.query("variant == 'maximum_extension'").groupby(
        ["iso3", "line_code"]):
    for year in _seams(g):
        prev = g.query("year == @year - 1").iloc[0]
        curr = g.query("year == @year").iloc[0]
        rows.append({"iso3": iso3, "line": line, "seam_year": year,
                     "from": f"{prev.observation_type} ({prev.source_id})",
                     "to": f"{curr.observation_type} ({curr.source_id})",
                     "step_pct": round(100 * (curr.value_lcu_mn
                                              / prev.value_lcu_mn - 1), 2)})
seams = pd.DataFrame(rows).sort_values(["iso3", "line", "seam_year"])
print(f"{len(seams)} seams across {seams.groupby(['iso3', 'line']).ngroups} series")
seams.reindex(seams.step_pct.abs().sort_values(ascending=False).index).reset_index(drop=True)'''))
    base["cells"] = out
    return base


# ------------------------------------------------------- forecast books

def _series_cells(iso3, line, label):
    cells = [md(f"## {line} — {label}"),
             code(f'levels("{iso3}", "{line}")'),
             code(f'share("{iso3}", "{line}")')]
    has = not FC.query("iso3 == @iso3 and line_code == @line").empty
    if has:
        cells += [code(f'fan("{iso3}", "{line}", "{m}")')
                  for m in ("auto.arima", "ets", "prophet", "uc", "combination")]
    return cells


def forecast_expenditure(iso3):
    name = f"forecasts_{iso3}_expenditure.ipynb"
    nb = load(name)
    cells = nb["cells"]
    if any(src(c) == f'levels("{iso3}", "GF10_2")' for c in cells):
        return nb
    # insert after the GF10 block (before the next "## " heading or the end)
    i = index_of(cells, "## GF10 —")
    j = i + 1
    while j < len(cells) and not src(cells[j]).startswith("## "):
        j += 1
    labels = dict(zip(CAT.line_code, CAT.line_label))
    new = _series_cells(iso3, "GF10_2", labels["GF10_2"]) \
        + _series_cells(iso3, "GF10_X", labels["GF10_X"])
    cells[j:j] = new
    setup = cells[index_of(cells, "from pathlib import Path")]
    s = "".join(setup["source"])
    if 'load("expenditure_esa")' not in s:
        s = s.replace('TREE = pd.concat([load("expenditure_cofog"), load("revenue_esa")],\n'
                      '                 ignore_index=True)',
                      'TREE = pd.concat([load("expenditure_cofog"), load("expenditure_esa"),\n'
                      '                  load("revenue_esa")], ignore_index=True)')
        assert 'load("expenditure_esa")' in s
        setup["source"] = s
    return nb


def forecast_esa(iso3):
    """A new book per country for the economic tree, from the expenditure
    book's preamble and setup."""
    name = {"GBR": "United Kingdom", "FRA": "France", "DEU": "Germany"}[iso3]
    base = load(f"forecasts_{iso3}_expenditure.ipynb")
    cells = base["cells"]
    preamble = copy.deepcopy(cells[0])
    p = "".join(preamble["source"])
    p = p.replace(f"# {name} — COFOG expenditure: series and statistical forecasts",
                  f"# {name} — expenditure by ESA economic type: series and statistical forecasts")
    p = p.replace("A companion to [`chartbook.ipynb`](chartbook.ipynb). For each granular line it",
                  "A companion to [`chartbook_esa.ipynb`](chartbook_esa.ipynb), the book for the\n"
                  "`ESA_EXP` tree (expenditure by ESA economic type, a second cut of the same\n"
                  "total as the COFOG functions — never add an `E` line to a `GF` line). For\n"
                  "each granular line it")
    preamble["source"] = p
    setup = copy.deepcopy(cells[index_of(cells, "from pathlib import Path")])
    s = "".join(setup["source"])
    if 'load("expenditure_esa")' not in s:
        s = s.replace('TREE = pd.concat([load("expenditure_cofog"), load("revenue_esa")],\n'
                      '                 ignore_index=True)',
                      'TREE = pd.concat([load("expenditure_cofog"), load("expenditure_esa"),\n'
                      '                  load("revenue_esa")], ignore_index=True)')
    setup["source"] = s
    labels = dict(zip(CAT.line_code, CAT.line_label))
    out = [preamble, setup]
    for line in ESA_LINES:
        out += _series_cells(iso3, line, labels[line])
    nb = copy.deepcopy(base)
    nb["cells"] = out
    return nb


# ----------------------------------------------------------- derivation

def derivation():
    nb = load("derivation.ipynb")
    cells = nb["cells"]
    c = cells[2]
    s = "".join(c["source"])
    s = s.replace("* **12 COFOG expenditure lines** — `GF01`–`GF10` at COFOG Level I, plus the",
                  "* **14 COFOG expenditure lines** — `GF01`–`GF10` at COFOG Level I, plus the")
    if "* **9 ESA economic expenditure lines**" not in s:
        s = s.replace("* **10 ESA revenue lines** — `R01`–`R10`, from VAT through to other transfers",
                      "* **9 ESA economic expenditure lines** — `E01`–`E09`, the same total\n"
                      "  expenditure cut by ESA transaction (compensation, intermediate consumption,\n"
                      "  social benefits in cash, social transfers in kind, interest, subsidies, other\n"
                      "  current, capital formation, capital transfers), summing to `TE_ESA`\n"
                      "* **10 ESA revenue lines** — `R01`–`R10`, from VAT through to other transfers")
    s = s.replace("That is the 66 line series of the specification (3 countries × 22 lines), plus",
                  "That is the 99 line series (3 countries × 33 lines: the specification's 66 plus\n"
                  "the pension split `GF10_2`/`GF10_X` and the nine-line economic tree, D-S11-001), plus")
    c["source"] = s
    c = cells[15]
    s = "".join(c["source"])
    s = s.replace("The loop below prints the derivation of all published series — 12 COFOG lines",
                  "The loop below prints the derivation of all published series — 14 COFOG lines")
    s = s.replace("and total expenditure, 10 ESA revenue lines and total revenue, for each of the",
                  "and total expenditure, 9 ESA economic lines and their total, 10 ESA revenue\n"
                  "lines and total revenue, for each of the")
    c["source"] = s
    return nb


def main():
    cb = chartbook()
    save("chartbook.ipynb", cb)
    save("chartbook_esa.ipynb", chartbook_esa(cb))
    for iso3 in COUNTRIES:
        save(f"forecasts_{iso3}_expenditure.ipynb", forecast_expenditure(iso3))
        save(f"forecasts_{iso3}_esa.ipynb", forecast_esa(iso3))
    save("derivation.ipynb", derivation())
    print("notebooks updated")


if __name__ == "__main__":
    sys.exit(main())
