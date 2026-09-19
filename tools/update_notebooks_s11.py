"""Notebook cell surgery for the Level II splits and the economic tree
(sessions 11: D-S13-001..005). Idempotent — running it twice leaves the
notebooks unchanged; execution (outputs) happens afterwards with nbconvert.

What it does, from `deliverables/series_catalogue.csv` and
`statistical_forecasts.csv`:
  * chartbook.ipynb: one `chart(iso3, code)` cell for every COFOG / ESA_REV
    series, inserted right after its parent's cell (Level II lines and
    remainders follow the line they split), plus the prose counts;
  * chartbook_esa.ipynb and chartbook_revenue.ipynb: the companion books
    for the ESA_EXP and ESA_REV trees (created from the chartbook's setup
    cell; the main book keeps the COFOG tree, ledger, WEO and seams);
  * forecasts_{iso3}_{expenditure,revenue}.ipynb: a section per missing
    series (levels, share, five fans where a benchmark exists), inserted
    after the parent's section; forecasts_{iso3}_esa.ipynb created for the
    economic tree;
  * derivation.ipynb: the prose that cites series counts.
"""

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
NAME = {"GBR": "United Kingdom", "FRA": "France", "DEU": "Germany"}
CAT = pd.read_csv(ROOT / "deliverables" / "series_catalogue.csv")
FC = pd.read_csv(ROOT / "deliverables" / "statistical_forecasts.csv")
LABEL = dict(zip(CAT.line_code, CAT.line_label))
ESA_LINES = [f"E{n:02d}" for n in range(1, 10)]

sys.path.insert(0, str(ROOT / "src"))
from ggfiscal import config  # noqa: E402

PARENT = {}
for sp in config.level2_splits():
    for c in sp["level2s"]:
        PARENT[c] = sp["parent"]
    PARENT[sp["remainder"]] = sp["parent"]


def ordered(classification: str) -> list[str]:
    """Granular lines of a tree in publication order: each parent followed
    by its Level II lines and remainder (the lines.yaml order)."""
    return config.granular_lines(classification)


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


def _after_block(cells, start):
    """Index just past the run of code cells that begins at `start` and
    belongs to the same series (the next heading or chart call of another
    series ends it)."""
    j = start + 1
    while j < len(cells) and cells[j]["cell_type"] == "code" \
            and not src(cells[j]).startswith(("chart(", "levels(", "ledger_chart(", "weo_")):
        j += 1
    return j


# ------------------------------------------------------------- chartbook

def chartbook():
    nb = load("chartbook.ipynb")
    cells = nb["cells"]
    # the revenue tree moves to chartbook_revenue.ipynb (D-S13-006): drop its
    # chart cells and section headings here so the main book stays under the
    # size GitHub renders
    rev_calls = {f'chart("{iso3}", "{line}")' for iso3 in COUNTRIES
                 for line in ordered("ESA_REV") + ["TR"]}
    nb["cells"] = cells = [c for c in cells
                           if src(c) not in rev_calls
                           and not (c["cell_type"] == "markdown"
                                    and src(c).startswith(("## 1.2 Revenue", "## 2.2 Revenue",
                                                           "## 3.2 Revenue")))]
    for iso3 in COUNTRIES:
        for cls in ("COFOG",):
            for line in ordered(cls):
                call = f'chart("{iso3}", "{line}")'
                if any(src(c) == call for c in cells):
                    continue
                # insert after the previous line in publication order that
                # is already charted (its parent, or the preceding sibling)
                lines = ordered(cls)
                prev = [l for l in lines[:lines.index(line)]
                        if any(src(c) == f'chart("{iso3}", "{l}")' for c in cells)][-1]
                i = index_of(cells, f'chart("{iso3}", "{prev}")')
                cells.insert(i + 1, code(call))
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
    _chartbook_prose(cells)
    for c in cells:
        if c["cell_type"] == "markdown":
            s = "".join(c["source"])
            s2 = s.replace("and its\nfive companions.", "and its\neight companions.")
            s2 = s2.replace(
                "* **Expenditure is `GF01_7 + GF01_X + GF02…GF10`, never `GF01…GF10`.** The two\n"
                "  are the same identity in history. In forecast they are not: the Level I set\n"
                "  hides the interest line inside `GF01`, whose own univariate fit knows nothing\n"
                "  about the official interest projection. For France that choice is worth over\n"
                "  two points of GDP by 2031, and it is the single largest judgement in this\n"
                "  section.",
                "* **Expenditure is `GF01_7 + GF01_X + GF02…GF09 + GF10_2 + GF10_5 + GF10_X`,\n"
                "  never `GF01…GF10`.** The two are the same identity in history. In forecast\n"
                "  they are not: the Level I set hides the interest line inside `GF01`, whose\n"
                "  own univariate fit knows nothing about the official interest projection. For\n"
                "  France that choice is worth over two points of GDP by 2031, and it is the\n"
                "  single largest judgement in this section. The same rule splits `GF10`\n"
                "  (D-S13-007): for France and Germany the old-age pension line `GF10_2` is on\n"
                "  the Ageing Report's official path, which `GF10` itself carries only in\n"
                "  `maximum_extension`. A parent is split here exactly when one of its Level II\n"
                "  lines has an official strict path to 2031 and the parent has not; `GF04` and\n"
                "  the revenue splits stay as their parents.")
            if s2 != s:
                c["source"] = s2
    return nb


def _chartbook_prose(cells):
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
                  "2. **The `_X` remainders are identities, not sources.** `GF01_X`, `GF04_X`,\n"
                  "   `GF10_X`, `R02_X` and `R06_X` are each a parent minus its Level II lines\n"
                  "   (`GF10 − GF10_2 − GF10_5`, `R06 − R06_E − R06_H`, and so on), and by\n"
                  "   construction they are never forecast. Their charts always stop at the\n"
                  "   last outturn by design.")
    f = f.replace("2. **`GF01_X` and `GF10_X` are identities, not sources.** They are\n"
                  "   `GF01 − GF01_7` and `GF10 − GF10_2`, and by construction they are never\n"
                  "   forecast. Their charts always stop at the last outturn, and they are the\n"
                  "   only expenditure lines that do so by design.",
                  "2. **The `_X` remainders are identities, not sources.** `GF01_X`, `GF04_X`,\n"
                  "   `GF10_X`, `R02_X` and `R06_X` are each a parent minus its Level II lines\n"
                  "   (`GF10 − GF10_2 − GF10_5`, `R06 − R06_E − R06_H`, and so on), and by\n"
                  "   construction they are never forecast. Their charts always stop at the\n"
                  "   last outturn by design.")
    f = f.replace("3. **`TE` and `TR` are totals, not members of the 66 line series.**",
                  "3. **`TE`, `TE_ESA` and `TR` are totals, not members of the 123 line series.**")
    f = f.replace("3. **`TE`, `TE_ESA` and `TR` are totals, not members of the 99 line series.**",
                  "3. **`TE`, `TE_ESA` and `TR` are totals, not members of the 123 line series.**")
    if "13. **Three books, one schema.**" not in f:
        f = f.rstrip() + """
13. **Three books, one schema.** This book holds the COFOG expenditure tree,
    the ledger, the WEO comparison and the seams table;
    [`chartbook_revenue.ipynb`](chartbook_revenue.ipynb) holds the revenue
    tree and [`chartbook_esa.ipynb`](chartbook_esa.ipynb) the economic tree.
    All three share the setup cell and the caption discipline; the split is
    only so that each stays small enough for GitHub to render.
"""
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
    # the two prose cells that cite projection counts
    none = int((CAT.final_maximum_year <= CAT.final_actual_year).sum())
    max_only = int(((CAT.final_maximum_year > CAT.final_actual_year)
                    & (CAT.final_strict_year <= CAT.final_actual_year)).sum())
    import re
    for c in cells:
        if c["cell_type"] != "markdown":
            continue
        t = "".join(c["source"])
        t2 = re.sub(r"\*\*\d+ of the \d+ series carry no projection at all\*\*, and another \d+ project only",
                    f"**{none} of the {len(CAT)} series carry no projection at all**, and another {max_only} project only", t)
        t2 = re.sub(r"of \d+ series, §\"Before the charts\"", f"of {len(CAT)} series, §\"Before the charts\"", t2)
        t2 = t2.replace("| `TE` and `TR` are envelopes", "| `TE`, `TE_ESA` and `TR` are envelopes")
        if t2 != t:
            c["source"] = t2


def _panel_cell_for(cells, tree_of, totals):
    """A copy of the main book's panel cell (D-S11-001) pointed at another
    tree. The cell's closing census runs over TREE_OF, so it reports the
    companion's own lines."""
    cell = copy.deepcopy(cells[index_of(cells, "# --------------------------------------------------------------- the panels")])
    s = "".join(cell["source"])
    start = s.index("TOTALS = (")
    end = s.index("\n", s.index("TREE_OF = {")) + 1
    end = s.index("\n\n", start) + 1
    head = s[:start]
    assert 'TREE_OF = {"expenditure"' in s[start:end], s[start:end]
    s = head + totals + "    # envelopes, not categories, and never forecast\n" + tree_of + "\n" + s[end:]
    cell["source"] = s
    cell["outputs"] = []
    cell["execution_count"] = None
    return cell


def chartbook_esa(chartbook_nb):
    """The companion: same setup cell, the economic tree only."""
    base = copy.deepcopy(chartbook_nb)
    cells = base["cells"]
    setup = cells[index_of(cells, "import io")]
    panel_cell = _panel_cell_for(cells, 'TREE_OF = {"economic": (ECONOMIC, "ESA economic type")}',
                                 'TOTALS = ("TE", "TR", "TE_ESA")')
    intro = md("""# Chartbook — expenditure by ESA economic type

The companion to [`chartbook.ipynb`](chartbook.ipynb), which explains how to
read every chart here (levels, seams, projection shading, captions). This book
holds the third tree, **expenditure by ESA economic type** (`ESA_EXP`,
D-S13-003): nine lines per country that sum to `TE_ESA`, a second cut of the
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
`E01`–`E07` project to 2027 at grade A for France and Germany, and `E05`
chains into the Debt Sustainability Monitor's interest path to 2036 under
the same committee approval as `GF01_7`; the UK's compensation, intermediate
consumption and other-current lines have no AMECO history to measure
coverage on and stop at the last outturn; `E08` and `E09` have partial
components only (§7.8 proxies, `maximum_extension`). Backward, AMECO takes
the French lines to 1978, the German ones to 1991, the UK ones to 1987 where
the UK history exists.

Every caption states the recipe and how far each variant projects, exactly as
in the main book; "no projection published" and its five reasons mean the same
thing here. Each country opens with the same **forecast panel** as the main
book (D-S11-001, extended to this tree by D-S13-007): every `E` line as a share
of GDP with the one forecast this project would quote for it — the official
projection where one is published, the statistical combination with its 80%
interval where none is — and the levels charts carry the statistical benchmark
in currency (D-S11-003) wherever the strict series has no official path. The
ranked `changes()` picture and the benchmark balance stay in the main book:
the balance is built from the COFOG and revenue trees, and this tree is the
same money cut a second way.
""")
    out = [intro, setup, panel_cell]
    for iso3 in COUNTRIES:
        out.append(md(f"## {SECTION[iso3]}. {NAME[iso3]} — expenditure by ESA economic type\n\n"
                      "The forecast panel first, then nine economic lines and their total. "
                      "`E03` (cash social benefits) and `E05` (interest) are the two that "
                      "other publications forecast directly; read `E05` against `GF01_7` "
                      "in the main book."))
        out.append(code(f'panel("{iso3}", "economic")'))
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


def chartbook_revenue(chartbook_nb):
    """The revenue companion: same setup cell, the ESA_REV tree only."""
    base = copy.deepcopy(chartbook_nb)
    cells = base["cells"]
    setup = cells[index_of(cells, "import io")]
    intro = md("""# Chartbook — revenue by ESA type

The companion to [`chartbook.ipynb`](chartbook.ipynb), which explains how to
read every chart here (levels, seams, projection shading, captions). This book
holds the **revenue tree** (`ESA_REV`): the ten ESA revenue types `R01`–`R10`
that sum to `TR`, plus the Level II splits of D-S13-005 — `R02_A` excise
duties (remainder `R02_X`) and `R06_E` employers' / `R06_H` households'
actual social contributions (remainder `R06_X`, the imputed and
supplementary part). A remainder plus its Level II lines equals the parent
exactly in every year; remainders are never forecast.

| line | ESA | what it is |
|---|---|---|
| `R01` | D.211 | value added tax |
| `R02` | D.2 − D.211 | other taxes on production and imports — `R02_A` excise duties (D.214A + D.2122C) and `R02_X` the rest |
| `R03` | D.51 households | taxes on household income incl. holding gains |
| `R04` | D.51 corporations | taxes on corporate income |
| `R05` | D.51 other + D.59 + D.91 | other current taxes and capital taxes |
| `R06` | D.61 | net social contributions — `R06_E` employers' actual (D.611), `R06_H` households' actual (D.613), `R06_X` imputed and supplementary |
| `R07` | D.41 resources | interest receivable |
| `R08` | D.4 − D.41 | other property income |
| `R09` | P.11 + P.12 + P.131 | sales of goods and services |
| `R10` | D.39 + D.7 + D.92 + D.99 | other current and capital transfers receivable |
| `TR` | total | total revenue |

The revenue tree was moved out of the main book only for size: the two
books share the setup cell and the caption discipline, and "no projection
published" and its five reasons mean the same thing here.
""")
    out = [intro, setup]
    for iso3 in COUNTRIES:
        out.append(md(f"## {SECTION[iso3]}. {NAME[iso3]} — revenue by ESA type\n\n"
                      "Ten revenue types and their total, with the excise-duty and "
                      "contributions splits beside their parents."))
        for line in ordered("ESA_REV") + ["TR"]:
            out.append(code(f'chart("{iso3}", "{line}")'))
    out.append(md("---\n\n## Seams in the revenue tree\n\nThe same triage table as the "
                  "main book's §6, restricted to the revenue lines."))
    out.append(code('''rows = []
for (iso3, line), g in REVENUE.query("variant == 'maximum_extension'").groupby(
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

def _series_cells(iso3, line):
    cells = [md(f"## {line} — {LABEL[line]}"),
             code(f'levels("{iso3}", "{line}")'),
             code(f'share("{iso3}", "{line}")')]
    has = not FC.query("iso3 == @iso3 and line_code == @line").empty
    if has:
        cells += [code(f'fan("{iso3}", "{line}", "{m}")')
                  for m in ("auto.arima", "ets", "prophet", "uc", "combination")]
    return cells


def _fix_setup(cells):
    setup = cells[index_of(cells, "from pathlib import Path")]
    s = "".join(setup["source"])
    if 'load("expenditure_esa")' not in s:
        s = s.replace('TREE = pd.concat([load("expenditure_cofog"), load("revenue_esa")],\n'
                      '                 ignore_index=True)',
                      'TREE = pd.concat([load("expenditure_cofog"), load("expenditure_esa"),\n'
                      '                  load("revenue_esa")], ignore_index=True)')
        assert 'load("expenditure_esa")' in s
        setup["source"] = s


def forecast_book(iso3, tree):
    cls = {"expenditure": "COFOG", "revenue": "ESA_REV"}[tree]
    name = f"forecasts_{iso3}_{tree}.ipynb"
    nb = load(name)
    cells = nb["cells"]
    _fix_setup(cells)
    lines = ordered(cls)
    for line in lines:
        if any(src(c) == f'levels("{iso3}", "{line}")' for c in cells):
            continue
        prev = [l for l in lines[:lines.index(line)]
                if any(src(c) == f'levels("{iso3}", "{l}")' for c in cells)][-1]
        i = index_of(cells, f'levels("{iso3}", "{prev}")')
        j = _after_block(cells, i)
        # also step over the fan cells of `prev` (they start with fan(, not chart)
        while j < len(cells) and src(cells[j]).startswith(f'fan("{iso3}", "{prev}"'):
            j += 1
        cells[j:j] = _series_cells(iso3, line)
    return nb


def forecast_esa(iso3):
    """A new book per country for the economic tree, from the expenditure
    book's preamble and setup."""
    name = NAME[iso3]
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
    out = [preamble, setup]
    _fix_setup(out)
    for line in ESA_LINES:
        out += _series_cells(iso3, line)
    nb = copy.deepcopy(base)
    nb["cells"] = out
    return nb


# ----------------------------------------------------------- derivation

def derivation():
    nb = load("derivation.ipynb")
    cells = nb["cells"]
    c = cells[2]
    s = "".join(c["source"])
    for old in ("* **12 COFOG expenditure lines** — `GF01`–`GF10` at COFOG Level I, plus the",
                "* **14 COFOG expenditure lines** — `GF01`–`GF10` at COFOG Level I, plus the"):
        s = s.replace(old, "* **17 COFOG expenditure lines** — `GF01`–`GF10` at COFOG Level I, plus the")
    if "* **9 ESA economic expenditure lines**" not in s:
        s = s.replace("* **10 ESA revenue lines** — `R01`–`R10`, from VAT through to other transfers",
                      "* **9 ESA economic expenditure lines** — `E01`–`E09`, the same total\n"
                      "  expenditure cut by ESA transaction (compensation, intermediate consumption,\n"
                      "  social benefits in cash, social transfers in kind, interest, subsidies, other\n"
                      "  current, capital formation, capital transfers), summing to `TE_ESA`\n"
                      "* **10 ESA revenue lines** — `R01`–`R10`, from VAT through to other transfers")
    s = s.replace("* **10 ESA revenue lines** — `R01`–`R10`, from VAT through to other transfers",
                  "* **15 ESA revenue lines** — `R01`–`R10`, from VAT through to other transfers,\n"
                  "  plus the excise-duty split of `R02` and the employers'/households' split of\n"
                  "  social contributions, each with its remainder")
    for old in ("That is the 66 line series of the specification (3 countries × 22 lines), plus",
                "That is the 99 line series (3 countries × 33 lines: the specification's 66 plus\n"
                "the pension split `GF10_2`/`GF10_X` and the nine-line economic tree, D-S13-001), plus"):
        s = s.replace(old, "That is the 123 line series (3 countries × 41 lines: the specification's 66 plus\n"
                           "the Level II splits — interest, old age, unemployment, transport, excise duties,\n"
                           "employers' and households' contributions, each with its remainder — and the\n"
                           "nine-line economic tree, D-S13-001/005), plus")
    c["source"] = s
    c = cells[15]
    s = "".join(c["source"])
    for old in ("The loop below prints the derivation of all published series — 12 COFOG lines",
                "The loop below prints the derivation of all published series — 14 COFOG lines"):
        s = s.replace(old, "The loop below prints the derivation of all published series — 17 COFOG lines")
    s = s.replace("and total expenditure, 10 ESA revenue lines and total revenue, for each of the",
                  "and total expenditure, 9 ESA economic lines and their total, 15 ESA revenue\n"
                  "lines and total revenue, for each of the")
    s = s.replace("and total expenditure, 9 ESA economic lines and their total, 10 ESA revenue\n"
                  "lines and total revenue, for each of the",
                  "and total expenditure, 9 ESA economic lines and their total, 15 ESA revenue\n"
                  "lines and total revenue, for each of the")
    c["source"] = s
    return nb


def main():
    cb = chartbook()
    save("chartbook.ipynb", cb)
    save("chartbook_esa.ipynb", chartbook_esa(cb))
    save("chartbook_revenue.ipynb", chartbook_revenue(cb))
    for iso3 in COUNTRIES:
        for tree in ("expenditure", "revenue"):
            save(f"forecasts_{iso3}_{tree}.ipynb", forecast_book(iso3, tree))
        save(f"forecasts_{iso3}_esa.ipynb", forecast_esa(iso3))
    save("derivation.ipynb", derivation())
    print("notebooks updated")


if __name__ == "__main__":
    sys.exit(main())
