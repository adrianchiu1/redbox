#!/usr/bin/env python3
"""Build a single-file, phone-first browser for the notebook charts.

`notebooks/chartbook.ipynb`, `notebooks/chartbook_revenue.ipynb`,
`notebooks/chartbook_esa.ipynb` and `notebooks/debtbook.ipynb` are committed
already executed: every figure is stored in the .ipynb as a base64 PNG. This
script reads those files and the series catalogue and nothing else -- no
pandas, no matplotlib, no kernel, stdlib only -- so the site rebuilds in a
fresh container without installing the project.

    python tools/build_chartsite.py                  # -> reports/charts.html
    python tools/build_chartsite.py --format artifact -o /tmp/frag.html

Two output shapes:

  standalone  a complete document. This is what `reports/charts.html` holds,
              what GitHub Pages serves, and what opens from the filesystem.
  artifact    the same page without the <!doctype>/<html>/<head>/<body>
              wrapper, for hosts that supply their own skeleton (a published
              Claude artifact does).

Because the PNGs come out of the notebooks, re-running a notebook and
re-running this script is the whole refresh path. The notebooks currently
render at dpi 72 with a quantised palette -- a compromise made for GitHub's
notebook renderer, which this page does not use. Raising `figure.dpi` in the
notebook setup cell gives sharper charts here at no cost to this script.

Markdown prose is passed through a small renderer rather than escaped: the
notebook markdown is repository content that Jupyter and GitHub already
render as HTML, and two cells rely on inline <span style="color:..."> to
name the series colours.
"""

from __future__ import annotations

import argparse
import ast
import base64
import csv
import html
import json
import posixpath
import re
import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/adrianchiu1/redbox"

BOOKS = [
    ("chartbook", "Chartbook", "notebooks/chartbook.ipynb",
     "Every COFOG, ESA and ledger series plotted, then reconciled to the IMF WEO."),
    ("chartbook_revenue", "Revenue", "notebooks/chartbook_revenue.ipynb",
     "The ESA revenue tree (ESA_REV) -- ten revenue types reconciled to TR, "
     "plus the excise-duty and contributions splits."),
    ("chartbook_esa", "ESA", "notebooks/chartbook_esa.ipynb",
     "The ESA economic-type expenditure tree (ESA_EXP) -- nine lines "
     "reconciled to TE_ESA, a second cut of total expenditure alongside COFOG."),
    ("debtbook", "Debtbook", "notebooks/debtbook.ipynb",
     "The debt-securities register and the interest and financing chains."),
]

import sys as _sys

_sys.path.insert(0, str(ROOT / "src"))
from ggfiscal import config as _config  # noqa: E402

# The countries come from config/countries.yaml (R0, D-S15-001): the names
# for headings, the prose form for joined titles, the aliases a chart title
# may use. A fourth country needs no edit here.
COUNTRY = _config.country_names()

# Ledger line codes are not in series_catalogue.csv; these are the readings
# used in balance_ledger.csv and §1.3 of the chartbook.
LEDGER_LABELS = {
    "TR": "Total revenue", "TE": "Total expenditure",
    "NLB": "Net lending / borrowing", "NI": "Net interest",
    "PB": "Primary balance",
}
WEO_TOPICS = {"revenue": "Revenue vs WEO", "expenditure": "Expenditure vs WEO",
              "nlb": "Net lending / borrowing vs WEO"}


# --------------------------------------------------------------------------
# notebook model
# --------------------------------------------------------------------------

@dataclass
class Figure:
    png: str
    label: str
    iso: str = ""
    code: str = ""
    width: int = 0
    height: int = 0
    index: int = 0


@dataclass
class Section:
    title: str
    level: int
    slug: str
    nodes: list = field(default_factory=list)   # ("prose", html) | ("fig", Figure) | ("table", html)

    @property
    def figures(self):
        return [n[1] for n in self.nodes if n[0] == "fig"]


# --------------------------------------------------------------------------
# markdown
# --------------------------------------------------------------------------

def _resolve(href: str, base: str) -> str:
    """Rewrite a notebook-relative link to a URL the standalone page can use."""
    if re.match(r"^(https?:|mailto:|#)", href):
        return href
    path = posixpath.normpath(posixpath.join(base, href)).lstrip("/")
    return f"{REPO_URL}/blob/main/{path}"


def _inline(text: str, base: str) -> str:
    holds: list[str] = []

    def stash(markup: str) -> str:
        holds.append(markup)
        return f"\x00{len(holds) - 1}\x00"

    text = re.sub(r"`([^`]+)`",
                  lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
                  lambda m: stash('<a href="%s" rel="noopener">%s</a>'
                                  % (html.escape(_resolve(m.group(2), base), quote=True),
                                     m.group(1))), text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", text)
    # Placeholders nest -- a link label may itself hold a code span --
    # and re.sub does not rescan what it substitutes, so unwind to a
    # fixed point rather than resolving a single layer.
    while "\x00" in text:
        text = re.sub(r"\x00(\d+)\x00",
                      lambda m: holds[int(m.group(1))], text)
    return text


def _row_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def md_to_html(md: str, base: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        if re.fullmatch(r"\s*-{3,}\s*", line):
            out.append("<hr>")
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = min(len(m.group(1)) + 2, 6)
            out.append(f"<h{lvl}>{_inline(m.group(2).strip(), base)}</h{lvl}>")
            i += 1
            continue

        # table: a header row followed by a delimiter row
        if (line.lstrip().startswith("|") and i + 1 < len(lines)
                and re.fullmatch(r"\s*\|[\s:|-]+\|\s*", lines[i + 1])):
            head = _row_cells(line)
            i += 2
            body = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                body.append(_row_cells(lines[i]))
                i += 1
            cells = "".join(f"<th>{_inline(c, base)}</th>" for c in head)
            rows = "".join(
                "<tr>" + "".join(f"<td>{_inline(c, base)}</td>" for c in r) + "</tr>"
                for r in body)
            out.append('<div class="scroller"><table><thead><tr>' + cells
                       + "</tr></thead><tbody>" + rows + "</tbody></table></div>")
            continue

        bullet = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if bullet:
            ordered = bullet.group(2)[0].isdigit()
            items: list[str] = []
            while i < len(lines):
                m2 = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if m2:
                    items.append(m2.group(3))
                    i += 1
                elif lines[i].strip() and lines[i].startswith((" ", "\t")) and items:
                    items[-1] += " " + lines[i].strip()   # continuation line
                    i += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(t, base)}</li>"
                                            for t in items) + f"</{tag}>")
            continue

        para: list[str] = []
        while i < len(lines) and lines[i].strip() \
                and not re.match(r"^(#{1,6}\s|\s*\||\s*([-*]|\d+\.)\s)", lines[i]) \
                and not re.fullmatch(r"\s*-{3,}\s*", lines[i]):
            para.append(lines[i].strip())
            i += 1
        if para:
            out.append("<p>" + _inline(" ".join(para), base) + "</p>")
        else:
            i += 1
    return "".join(out)


# --------------------------------------------------------------------------
# figure labelling
# --------------------------------------------------------------------------

def load_catalogue() -> dict:
    path = ROOT / "deliverables" / "series_catalogue.csv"
    labels: dict[tuple[str, str], str] = {}
    if not path.exists():
        return labels
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            labels[(row["iso3"], row["line_code"])] = row["line_label"]
    return labels


CALL_RE = re.compile(
    r'^(chart|ledger_chart|weo_chart)\(\s*"(\w{3})"\s*,\s*"([^"]+)"\s*\)', re.M)
WATERFALL_RE = re.compile(r'waterfall_page\(\s*\w+\s*,\s*"(\w{3})"[^)]*?"(\w+)"\s*\)', re.S)

# Calls whose string arguments are never a chart title.
DENY = {"print", "legend", "set_ylabel", "set_xlabel", "set_label", "text",
        "annotate", "query", "eval", "format", "join", "get", "fill",
        "pivot_table", "groupby", "merge", "isin", "sort_values", "reindex",
        "astype", "rename", "read_csv", "strftime", "set_index", "dropna",
        "agg", "apply", "replace", "startswith", "endswith", "split",
        "plot", "bar", "barh", "scatter", "stackplot", "axhline", "axvline",
        "fill_between", "step", "set_yscale", "set_xscale"}
TITLE_FUNCS = ("set_title", "suptitle", "set_suptitle")
TRAILING = re.compile(r"[\s,;:\u2014\u2013\-(]+$")
DANGLING = re.compile(r"\s+(?:at|on|in|of|for|to|vs|from|by)$", re.I)


JOIN_NAMES = _config.prose_names()
ISO_ALIASES = _config.country_aliases()


def _join_names(isos: list[str]) -> str:
    names = [JOIN_NAMES.get(i, COUNTRY.get(i, i)) for i in isos]
    if len(names) < 2:
        return names[0] if names else ""
    return ", ".join(names[:-1]) + " and " + names[-1]


def _tidy(text: str, trimmed: bool) -> str:
    """Tidy a rendered title; `trimmed` says a placeholder was dropped from it.

    A title that resolved in full is left verbatim -- trailing punctuation is
    the notebook's own (`..., 2009-` means "2009 onwards"). Only the wreckage
    of a dropped placeholder is cleaned up.
    """
    text = re.sub(r"\s{2,}", " ", text).strip()
    if not trimmed:
        return text
    text = re.sub(r"\(\s*\)", "", text)          # the placeholder was all of it
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = TRAILING.sub("", DANGLING.sub("", TRAILING.sub("", text)))
    return text.strip().lstrip(":\u00b7\u2014\u2013- ").strip()


def _template(node) -> str | None:
    """Render a string constant or an f-string as a title template.

    Placeholders survive as {NAME[var]} / {var} so a loop can resolve them;
    anything else becomes an empty {} that _resolve_template drops.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for piece in node.values:
            if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
                parts.append(piece.value)
            elif isinstance(piece, ast.FormattedValue):
                parts.append("{%s}" % _placeholder(piece.value))
        return "".join(parts)
    return None


def _placeholder(node) -> str:
    """The subset of expressions a title template can substitute later."""
    if isinstance(node, ast.Name):
        return node.id
    if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
            and node.value.id in ("NAME", "COUNTRY")
            and isinstance(node.slice, ast.Name)):
        return f"{node.value.id}[{node.slice.id}]"
    return ""


def _resolve_template(tpl: str, names: list[str], isos: list[str]) -> str:
    if isos:
        joined = _join_names(isos)
        bare = isos[0] if len(isos) == 1 else "/".join(isos)
        for var in names:
            tpl = re.sub(r"\{(?:NAME|COUNTRY)\[%s\]\}" % re.escape(var), joined, tpl)
            tpl = tpl.replace("{%s}" % var, bare)
    stripped = re.sub(r"\{[^{}]*\}", "", tpl)
    return _tidy(stripped, stripped != tpl)


def _iter_isos(node) -> list[str]:
    """ISO codes a for-loop iterates over, including `zip(axes, [...])`."""
    candidates = [node]
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "zip":
        candidates = list(node.args)
    for cand in candidates:
        if isinstance(cand, (ast.List, ast.Tuple)):
            values = [e.value for e in cand.elts
                      if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if values and all(v in COUNTRY for v in values):
                return values
    return []


def _loop_vars(target) -> list[str]:
    """Names a for-target binds; a `zip(...)` target binds several at once."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Tuple):
        return [e.id for e in target.elts if isinstance(e, ast.Name)]
    return []


def _func_name(node) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    return getattr(func, "attr", "")


def _scan(tree: ast.AST):
    """Titles and figure-emit points, each tagged with its enclosing ISO loop."""
    titles, emits = [], []

    def walk(node, ctx):
        for child in ast.iter_child_nodes(node):
            inner = ctx
            if isinstance(child, ast.For):
                isos = _iter_isos(child.iter)
                if isos:
                    inner = (_loop_vars(child.target), isos)
            elif isinstance(child, ast.Call):
                name = _func_name(child)
                if name == "show":
                    emits.append((child.lineno, ctx))
                elif name not in DENY:
                    args = list(child.args) + [k.value for k in child.keywords
                                               if k.arg == "title"]
                    for arg in args:
                        tpl = _template(arg)
                        titled = name.endswith(TITLE_FUNCS)
                        if tpl and (titled or (" " in tpl.strip()
                                               and len(tpl.strip()) >= 8)):
                            titles.append((child.lineno, tpl, ctx, titled))
                            break
            walk(child, inner)

    walk(tree, None)
    return titles, emits


def labels_from_ast(src: str, n: int) -> list[tuple[str, str]]:
    """(label, iso) for the n figures a cell emitted, or [] if unreadable."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    titles, emits = _scan(tree)
    if not titles:
        return []

    if not emits:                       # inline display: the cell is one figure
        emits = [(max(t[0] for t in titles) + 1, titles[-1][2])]

    groups: list[tuple[list, object]] = []
    previous = 0
    for lineno, ctx in emits:
        group = [t for t in titles if previous < t[0] <= lineno]
        groups.append((group, ctx))
        previous = lineno

    out: list[tuple[str, str]] = []
    for group, ctx in groups:
        names, isos = ctx if ctx else ([], [])
        preferred = [t for t in group if t[3]]
        group = preferred or group
        # A loop only multiplies figures when the emit itself sits inside it.
        repeats = isos if (ctx and len(groups) * len(isos) == n) else [None]
        for iso in repeats:
            scope = [iso] if iso else isos
            texts, seen = [], set()
            for _, tpl, _, _ in group:
                text = _resolve_template(tpl, names, scope)
                if text and text not in seen:
                    seen.add(text)
                    texts.append(text)
            if len(texts) > 1:                      # one figure, several panels
                head = posixpath.commonprefix(texts)
                head = head[:head.rfind(" ") + 1] if " " in head else ""
                texts = [head + " \u00b7 ".join(t[len(head):] for t in texts)]
            label = texts[0] if texts else ""
            if label:
                out.append((label, iso or (isos[0] if len(isos) == 1 else "")))
    return out if len(out) == n else []


def labels_for_cell(src: str, n: int, catalogue: dict, fallback: str) -> list[Figure]:
    """Best-effort human labels for the n figures a code cell emitted."""
    out: list[tuple[str, str, str]] = []                # (label, iso, code)

    for fn, iso, code in CALL_RE.findall(src):
        if fn == "weo_chart":
            out.append((f"{COUNTRY.get(iso, iso)} \u00b7 "
                        + WEO_TOPICS.get(code, code), iso, code.upper()))
        else:
            name = catalogue.get((iso, code)) or LEDGER_LABELS.get(code) or code
            suffix = " (ledger)" if fn == "ledger_chart" else ""
            out.append((f"{code} \u00b7 {name}{suffix}", iso, code))

    if not out:
        for iso, chain in WATERFALL_RE.findall(src):
            out.append((f"{COUNTRY.get(iso, iso)} \u2014 {chain} chain, "
                        "bridge by year", iso, chain))

    if not out:
        for label, iso in labels_from_ast(src, n):
            if not iso:
                # Only when the title names exactly one country: a figure
                # covering several must not be hidden by a country filter.
                hits = [k for k, aliases in ISO_ALIASES.items()
                        if any(re.search(r"\b%s\b" % a, label) for a in aliases)]
                iso = hits[0] if len(hits) == 1 else ""
            out.append((label, iso, ""))

    while len(out) < n:
        ordinal = f" ({len(out) + 1})" if n > 1 else ""
        out.append((f"{fallback}{ordinal}", "", ""))
    return [Figure(png="", label=lab, iso=iso, code=code) for lab, iso, code in out[:n]]


# --------------------------------------------------------------------------
# notebook -> sections
# --------------------------------------------------------------------------

def png_size(b64: str) -> tuple[int, int]:
    raw = base64.b64decode(b64[:120] + "=" * (-len(b64[:120]) % 4))
    if raw[12:16] == b"IHDR":
        return struct.unpack(">II", raw[16:24])
    return (0, 0)


def slugify(text: str, taken: set) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "section"
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    taken.add(slug)
    return slug


def parse_notebook(path: Path, catalogue: dict) -> list[Section]:
    nb = json.loads(path.read_text(encoding="utf-8"))
    base = posixpath.dirname(path.relative_to(ROOT).as_posix())
    taken: set = set()
    sections: list[Section] = [Section("Front matter", 1, slugify("front-matter", taken))]
    counter = 0

    for cell in nb["cells"]:
        src = "".join(cell["source"])

        if cell["cell_type"] == "markdown":
            chunk: list[str] = []
            for line in src.split("\n"):
                head = re.match(r"^(#{1,3})\s+(.*)$", line)
                if head:
                    body = "\n".join(chunk).strip()
                    if body:
                        sections[-1].nodes.append(("prose", md_to_html(body, base)))
                    chunk = []
                    title = head.group(2).strip()
                    sections.append(Section(title, len(head.group(1)),
                                            slugify(title, taken)))
                else:
                    chunk.append(line)
            body = "\n".join(chunk).strip()
            if body:
                sections[-1].nodes.append(("prose", md_to_html(body, base)))
            continue

        pngs, tables = [], []
        for output in cell.get("outputs", []):
            data = output.get("data", {})
            if "image/png" in data:
                blob = data["image/png"]
                pngs.append(blob if isinstance(blob, str) else "".join(blob))
            elif "text/html" in data:
                markup = data["text/html"]
                tables.append(markup if isinstance(markup, str) else "".join(markup))

        if pngs:
            figs = labels_for_cell(src, len(pngs), catalogue, sections[-1].title)
            for fig, blob in zip(figs, pngs):
                fig.png = blob.replace("\n", "")
                fig.width, fig.height = png_size(fig.png)
                counter += 1
                fig.index = counter
                sections[-1].nodes.append(("fig", fig))
        for markup in tables:
            sections[-1].nodes.append(("table", f'<div class="scroller">{markup}</div>'))

    return [s for s in sections if s.nodes]


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

CSS = """
:root{
  --paper:#f7f4ee; --surface:#fffdf8; --raised:#efeae0;
  --ink:#1a1713; --muted:#6f6659; --rule:#ded6c7;
  --accent:#8c1d2b; --accent-ink:#fff; --accent-soft:#f2e3e2;
  --plate:#fcfcfb; --plate-rule:#e3ded1; --shadow:0 1px 2px rgba(40,30,14,.07);
  --wide:56rem;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --paper:#141210; --surface:#1e1b16; --raised:#272219;
  --ink:#f0ebe0; --muted:#9d9484; --rule:#342e25;
  --accent:#e2707b; --accent-ink:#22110f; --accent-soft:#3a2023;
  --plate:#fcfcfb; --plate-rule:#3b352b; --shadow:0 1px 2px rgba(0,0,0,.4);
}}
:root[data-theme="dark"]{
  --paper:#141210; --surface:#1e1b16; --raised:#272219;
  --ink:#f0ebe0; --muted:#9d9484; --rule:#342e25;
  --accent:#e2707b; --accent-ink:#22110f; --accent-soft:#3a2023;
  --plate:#fcfcfb; --plate-rule:#3b352b; --shadow:0 1px 2px rgba(0,0,0,.4);
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font:400 16px/1.6 "Source Serif 4",Georgia,"Times New Roman",serif;
  -webkit-text-size-adjust:100%;}
code,kbd,.mono{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace}
.ui{font-family:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
a{color:var(--accent);text-underline-offset:2px}
h2,h3,h4,h5,h6{text-wrap:balance;line-height:1.25;margin:0}
hr{border:0;border-top:1px solid var(--rule);margin:0}

/* ---- top bar ---- */
.bar{position:sticky;top:env(safe-area-inset-top,0px);z-index:40;
  background:color-mix(in srgb,var(--paper) 92%,transparent);
  backdrop-filter:blur(12px);border-bottom:1px solid var(--rule)}
.bar-in{max-width:var(--wide);margin:0 auto;padding-block:8px;padding-inline:16px;
  display:flex;flex-direction:column;gap:8px}
.row{display:flex;align-items:center;gap:8px}
.brand{font-family:"IBM Plex Sans",sans-serif;font-weight:600;font-size:12px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--accent);
  white-space:nowrap;display:flex;align-items:center;gap:7px}
.brand::before{content:"";width:9px;height:12px;border-radius:1.5px;
  background:var(--accent);box-shadow:inset 0 0 0 1.5px var(--paper)}
.tabs{display:flex;gap:2px;margin-left:auto;background:var(--raised);
  border-radius:999px;padding:2px}
.tab{appearance:none;border:0;background:none;cursor:pointer;color:var(--muted);
  font:500 13px/1 "IBM Plex Sans",sans-serif;padding:7px 13px;border-radius:999px}
.tab[aria-selected="true"]{background:var(--surface);color:var(--ink);box-shadow:var(--shadow)}
.search{flex:1;min-width:0;display:flex;align-items:center;gap:7px;
  background:var(--surface);border:1px solid var(--rule);border-radius:9px;padding:0 10px}
.search{padding:0 9px}
.search input{flex:1;min-width:0;border:0;background:none;color:var(--ink);
  font:400 15px/1 "IBM Plex Sans",sans-serif;padding:10px 0}
.search input:focus{outline:none}
.search svg{flex:none;color:var(--muted)}
.btn{appearance:none;cursor:pointer;flex:none;background:var(--surface);
  border:1px solid var(--rule);border-radius:9px;color:var(--muted);
  font:500 13px/1 "IBM Plex Sans",sans-serif;padding:10px 9px;white-space:nowrap}
.btn[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.btn:focus-visible,.tab:focus-visible,input:focus-visible,a:focus-visible,
.hit:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.count{font:400 12px/1 "IBM Plex Mono",monospace;color:var(--muted);white-space:nowrap}

/* ---- chips ---- */
.chips{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;padding-bottom:1px}
.chips::-webkit-scrollbar{display:none}
.chip{appearance:none;cursor:pointer;flex:none;background:var(--surface);
  border:1px solid var(--rule);border-radius:999px;color:var(--muted);
  font:500 12px/1 "IBM Plex Sans",sans-serif;padding:7px 12px}
.chip[aria-pressed="true"]{background:var(--ink);border-color:var(--ink);color:var(--paper)}

/* ---- body ---- */
main{max-width:var(--wide);margin:0 auto;padding-inline:16px;padding-block:8px 64px}
.sec{padding-block:20px 8px;scroll-margin-top:140px}
.sec > h2{font-size:24px;font-weight:600;letter-spacing:-.01em}
.sec > h3{font-size:19px;font-weight:600;color:var(--ink)}
.eyebrow{font:500 11px/1 "IBM Plex Sans",sans-serif;letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted);margin-bottom:9px}
.lead .sec > h2{border-top:2px solid var(--accent);padding-top:14px}
.prose{max-width:36em;margin-block:14px}
.prose p{margin:0 0 .85em}
.prose li{margin-bottom:.4em}
.prose h4,.prose h5{font-size:16px;font-weight:600;margin:1.2em 0 .4em}
.prose code{font-size:.86em;background:var(--raised);padding:.1em .34em;border-radius:4px}
.prose table{border-collapse:collapse;font-size:14px;
  font-family:"IBM Plex Sans",sans-serif;min-width:100%}
.prose th,.prose td{border-bottom:1px solid var(--rule);padding:7px 10px;
  text-align:left;vertical-align:top}
.prose th{font-weight:600;font-size:12px;letter-spacing:.04em;text-transform:uppercase;
  color:var(--muted);white-space:nowrap}
.scroller{overflow-x:auto;-webkit-overflow-scrolling:touch;margin-block:14px}
.scroller table{border-collapse:collapse;font:400 13px/1.45 "IBM Plex Mono",monospace}
.scroller td,.scroller th{border-bottom:1px solid var(--rule);padding:5px 9px;
  text-align:left;white-space:nowrap}

/* ---- figures ---- */
.figs{display:grid;gap:12px;margin-block:14px}
.card{display:block;width:100%;background:var(--surface);
  border:1px solid var(--rule);border-radius:12px;padding:10px;box-shadow:var(--shadow)}
.hit{display:block;width:100%;margin:0;padding:0;border:0;background:none;
  text-align:left;appearance:none;cursor:zoom-in;color:inherit;font:inherit}
.plate{display:block;background:var(--plate);border:1px solid var(--plate-rule);
  border-radius:7px;overflow:hidden;line-height:0}
.plate img{display:block;width:100%;height:auto}
figcaption{display:flex;gap:8px;align-items:baseline;margin-top:9px;
  font-family:"IBM Plex Sans",sans-serif;font-size:13px;line-height:1.35;color:var(--muted)}
.n{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--accent);
  flex:none;padding-top:1px;font-variant-numeric:tabular-nums}
figure{margin:0}
body.grid .figs{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
body.grid .card{padding:6px;border-radius:9px}
body.grid figcaption{font-size:11px;margin-top:6px}
body.grid .prose,body.notes-off .prose{display:none}
body.grid .scroller{display:none}
@media (min-width:680px){ .figs{grid-template-columns:repeat(2,1fr)}
  body.grid .figs{grid-template-columns:repeat(auto-fill,minmax(190px,1fr))} }
.empty{display:none;color:var(--muted);font-family:"IBM Plex Sans",sans-serif;
  padding:48px 0;text-align:center}
body.searching .sec[data-hits="0"]{display:none}
body.searching .prose,body.searching .scroller,body.searching .eyebrow{display:none}
figure[hidden]{display:none}

/* ---- drawer ---- */
.scrim{position:fixed;inset:0;z-index:50;background:rgba(20,15,8,.42);
  opacity:0;pointer-events:none;transition:opacity .18s}
body.drawer .scrim{opacity:1;pointer-events:auto}
.drawer{position:fixed;z-index:51;top:0;bottom:0;right:0;width:min(22rem,86vw);
  background:var(--surface);border-left:1px solid var(--rule);
  transform:translateX(100%);transition:transform .2s ease;
  overflow-y:auto;-webkit-overflow-scrolling:touch;
  padding:calc(14px + env(safe-area-inset-top,0px)) 14px
          calc(24px + env(safe-area-inset-bottom,0px))}
body.drawer .drawer{transform:none}
.drawer h2{font:600 12px/1 "IBM Plex Sans",sans-serif;letter-spacing:.14em;
  text-transform:uppercase;color:var(--muted);margin-bottom:12px}
.drawer a{display:flex;gap:10px;align-items:baseline;padding:9px 8px;margin-inline:-8px;
  border-radius:7px;text-decoration:none;color:var(--ink);
  font-family:"IBM Plex Sans",sans-serif;font-size:14px;line-height:1.3}
.drawer a:active{background:var(--raised)}
.drawer a.l2{padding-left:20px;font-size:13px;color:var(--muted)}
.drawer a .k{margin-left:auto;font:400 11px/1 "IBM Plex Mono",monospace;
  color:var(--muted);flex:none}

/* ---- lightbox ---- */
.lb{position:fixed;inset:0;z-index:60;background:var(--paper);
  display:flex;flex-direction:column;
  padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
.lb[hidden]{display:none!important}
.lb-bar{display:flex;align-items:center;gap:8px;padding:8px 12px;
  border-bottom:1px solid var(--rule)}
.lb-cap{flex:1;min-width:0;font:500 13px/1.3 "IBM Plex Sans",sans-serif;color:var(--ink);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lb-stage{flex:1;overflow:auto;-webkit-overflow-scrolling:touch;
  display:flex;align-items:center;justify-content:center;background:var(--plate)}
.lb-stage img{display:block;width:var(--zoom,100%);max-width:none;height:auto;
  image-rendering:auto;cursor:zoom-in}
.lb-foot{display:flex;align-items:center;gap:8px;padding:10px 12px;
  border-top:1px solid var(--rule)}
.lb-foot .btn{flex:1}
.hint{font:400 11px/1.3 "IBM Plex Sans",sans-serif;color:var(--muted);text-align:center;
  padding:6px 12px 0}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

JS = r"""
(function(){
  var body=document.body, bar=document.getElementById('bar');
  var q=document.getElementById('q'), count=document.getElementById('count');
  function store(k,v){try{localStorage.setItem('redbox.'+k,v);}catch(e){}}
  function recall(k){try{return localStorage.getItem('redbox.'+k);}catch(e){return null;}}

  /* ---- books ---- */
  function setBook(id){
    document.querySelectorAll('[data-book]').forEach(function(s){
      s.hidden = s.getAttribute('data-book')!==id; });
    document.querySelectorAll('.tab').forEach(function(t){
      t.setAttribute('aria-selected', String(t.dataset.target===id)); });
    document.querySelectorAll('.drawer [data-for]').forEach(function(g){
      g.hidden = g.getAttribute('data-for')!==id; });
    store('book',id); filter();
  }
  document.querySelectorAll('.tab').forEach(function(t){
    t.addEventListener('click',function(){ setBook(t.dataset.target); scrollTo(0,0); }); });

  /* ---- toggles ---- */
  function toggle(id, cls, key){
    var b=document.getElementById(id); if(!b) return;
    function apply(on){ body.classList.toggle(cls,on); b.setAttribute('aria-pressed',String(on)); }
    b.addEventListener('click',function(){
      var on=b.getAttribute('aria-pressed')!=='true'; apply(on); store(key,on?'1':'0'); });
    if(recall(key)==='1') apply(true);
  }
  toggle('grid','grid','grid');
  toggle('notes','notes-off','notesOff');

  /* ---- country filter ---- */
  var iso='';
  document.querySelectorAll('.chip').forEach(function(c){
    c.addEventListener('click',function(){
      iso = (iso===c.dataset.iso) ? '' : c.dataset.iso;
      document.querySelectorAll('.chip').forEach(function(o){
        o.setAttribute('aria-pressed',String(o.dataset.iso===iso)); });
      filter();
    });
  });

  /* ---- search + filter ---- */
  var figs=[].slice.call(document.querySelectorAll('figure'));
  function filter(){
    var term=(q.value||'').trim().toLowerCase();
    body.classList.toggle('searching', !!term || !!iso);
    var shown=0;
    document.querySelectorAll('.sec').forEach(function(sec){
      var hits=0;
      sec.querySelectorAll('figure').forEach(function(f){
        var ok=(!term || f.dataset.s.indexOf(term)>-1) && (!iso || f.dataset.iso===iso);
        f.hidden=!ok; if(ok){hits++;}
      });
      sec.setAttribute('data-hits', String(hits));
      if(sec.closest('[data-book]').hidden) return;
      shown+=hits;
    });
    count.textContent = shown + (shown===1?' chart':' charts');
    document.getElementById('empty').style.display = shown?'none':'block';
  }
  q.addEventListener('input', filter);
  q.addEventListener('search', filter);

  /* ---- drawer ---- */
  var drawer=document.getElementById('drawer');
  function setDrawer(on){ body.classList.toggle('drawer',on);
    document.getElementById('index').setAttribute('aria-expanded',String(on)); }
  document.getElementById('index').addEventListener('click',function(){
    setDrawer(!body.classList.contains('drawer')); });
  document.getElementById('scrim').addEventListener('click',function(){ setDrawer(false); });
  drawer.addEventListener('click',function(e){ if(e.target.closest('a')) setDrawer(false); });

  /* ---- lightbox ---- */
  var lb=document.getElementById('lb'), lbImg=document.getElementById('lb-img'),
      lbCap=document.getElementById('lb-cap'), stage=document.getElementById('lb-stage'),
      zooms=['100%','210%','330%'], z=0, cur=-1;
  function visible(){ return figs.filter(function(f){
      return !f.hidden && !f.closest('[data-book]').hidden; }); }
  function open(fig){
    var list=visible(); cur=list.indexOf(fig); if(cur<0) return;
    show(list[cur]); lb.hidden=false; body.style.overflow='hidden';
    document.getElementById('lb-close').focus();
  }
  function show(fig){
    var img=fig.querySelector('img');
    lbImg.src=img.src; lbImg.alt=img.alt;
    lbCap.textContent=fig.querySelector('.n').textContent+' \u00b7 '+img.alt;
    z=0; stage.style.setProperty('--zoom',zooms[0]); stage.scrollTop=0; stage.scrollLeft=0;
  }
  function step(d){ var list=visible(); if(!list.length) return;
    cur=(cur+d+list.length)%list.length; show(list[cur]); }
  function close(){ lb.hidden=true; body.style.overflow=''; }
  figs.forEach(function(f){
    f.addEventListener('click',function(){ open(f); });
  });
  lbImg.addEventListener('click',function(){
    z=(z+1)%zooms.length; stage.style.setProperty('--zoom',zooms[z]);
    lbImg.style.cursor = z===zooms.length-1 ? 'zoom-out':'zoom-in';
  });
  document.getElementById('lb-close').addEventListener('click',close);
  document.getElementById('lb-prev').addEventListener('click',function(){ step(-1); });
  document.getElementById('lb-next').addEventListener('click',function(){ step(1); });
  document.addEventListener('keydown',function(e){
    if(lb.hidden) return;
    if(e.key==='Escape') close();
    if(e.key==='ArrowLeft') step(-1);
    if(e.key==='ArrowRight') step(1);
  });

  /* ---- boot ---- */
  var start=recall('book');
  setBook(start && document.querySelector('[data-book="'+start+'"]') ? start : 'chartbook');
  if(location.hash){ var t=document.querySelector(location.hash);
    if(t){ var bk=t.closest('[data-book]'); if(bk) setBook(bk.dataset.book);
           t.scrollIntoView(); } }
})();
"""

FONTS = ('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&'
         'family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">')

ICON = ('<svg width="15" height="15" viewBox="0 0 16 16" fill="none" '
        'stroke="currentColor" stroke-width="1.6" aria-hidden="true">'
        '<circle cx="7" cy="7" r="4.5"/><path d="M10.4 10.4 14 14"/></svg>')


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def render_figure(fig: Figure) -> str:
    haystack = " ".join([fig.label, fig.iso, fig.code,
                         COUNTRY.get(fig.iso, "")]).lower()
    ratio = f"{fig.width}/{fig.height}" if fig.width and fig.height else "auto"
    return (
        f'<figure class="card" data-s="{esc(haystack)}" data-iso="{esc(fig.iso)}">'
        f'<button class="hit" type="button" aria-label="Enlarge {esc(fig.label)}">'
        f'<span class="plate" style="aspect-ratio:{ratio}">'
        f'<img src="data:image/png;base64,{fig.png}" alt="{esc(fig.label)}" '
        f'width="{fig.width}" height="{fig.height}" loading="lazy" decoding="async">'
        f"</span></button>"
        f'<figcaption><span class="n">{fig.index:03d}</span>'
        f"<span>{esc(fig.label)}</span></figcaption>"
        f"</figure>")


def render_book(book_id: str, sections: list[Section]) -> str:
    parts = []
    for sec in sections:
        tag = "h2" if sec.level == 1 else "h3"
        figs = sec.figures
        eyebrow = (f'<p class="eyebrow">{len(figs)} '
                   f'{"chart" if len(figs) == 1 else "charts"}</p>') if figs else ""
        parts.append(f'<section class="sec" id="{sec.slug}">{eyebrow}'
                     f"<{tag}>{esc(sec.title)}</{tag}>")
        buffer: list[str] = []
        for kind, value in sec.nodes:
            if kind == "fig":
                buffer.append(render_figure(value))
                continue
            if buffer:
                parts.append('<div class="figs">' + "".join(buffer) + "</div>")
                buffer = []
            parts.append(f'<div class="prose">{value}</div>' if kind == "prose" else value)
        if buffer:
            parts.append('<div class="figs">' + "".join(buffer) + "</div>")
        parts.append("</section>")
    return (f'<div data-book="{book_id}" class="lead">' + "".join(parts) + "</div>")


def render_index(book_id: str, title: str, sections: list[Section]) -> str:
    rows = []
    for sec in sections:
        n = len(sec.figures)
        cls = "" if sec.level == 1 else " class=\"l2\""
        badge = f'<span class="k">{n}</span>' if n else ""
        rows.append(f'<a href="#{sec.slug}"{cls}><span>{esc(sec.title)}</span>{badge}</a>')
    return (f'<div data-for="{book_id}"><h2>{esc(title)}</h2>' + "".join(rows) + "</div>")


def render(books: list[tuple], standalone: bool) -> str:
    total = sum(len([f for s in secs for f in s.figures]) for _, _, secs, _ in books)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    tabs = "".join(f'<button class="tab ui" type="button" data-target="{bid}" '
                   f'role="tab" aria-selected="false">{esc(name)}</button>'
                   for bid, name, _, _ in books)
    chips = "".join(f'<button class="chip" type="button" data-iso="{iso}" '
                    f'aria-pressed="false">{esc(name)}</button>'
                    for iso, name in COUNTRY.items())

    head = f"""<div class="bar" id="bar"><div class="bar-in">
<div class="row"><span class="brand ui">Redbox</span>
<div class="tabs" role="tablist">{tabs}</div></div>
<div class="row"><label class="search">{ICON}
<input id="q" type="search" placeholder="Search {total} charts…"
 autocomplete="off" autocapitalize="off" spellcheck="false"
 aria-label="Search charts"></label>
<button class="btn ui" id="grid" type="button" aria-pressed="false"
 title="Thumbnail grid">Grid</button>
<button class="btn ui" id="notes" type="button" aria-pressed="false"
 title="Hide the notebook commentary">Notes</button>
<button class="btn ui" id="index" type="button" aria-expanded="false"
 title="Section index">Index</button></div>
<div class="row"><div class="chips">{chips}</div>
<span class="count ui" id="count">{total} charts</span></div>
</div></div>"""

    main = ("<main>" + "".join(render_book(bid, secs) for bid, _, secs, _ in books)
            + '<p class="empty ui" id="empty">No chart matches that.</p></main>')

    drawer = ('<div class="scrim" id="scrim"></div>'
              '<nav class="drawer" id="drawer" aria-label="Section index">'
              + "".join(render_index(bid, name, secs) for bid, name, secs, _ in books)
              + f'<p class="hint">Built {stamp} from the committed notebooks.</p></nav>')

    lightbox = """<div class="lb" id="lb" hidden role="dialog" aria-modal="true"
 aria-label="Chart viewer">
<div class="lb-bar"><span class="lb-cap ui" id="lb-cap"></span>
<button class="btn ui" id="lb-close" type="button">Close</button></div>
<div class="lb-stage" id="lb-stage"><img id="lb-img" src="" alt=""></div>
<p class="hint">Tap the chart to step through zoom levels · turn the phone
sideways for more width</p>
<div class="lb-foot"><button class="btn ui" id="lb-prev" type="button">← Prev</button>
<button class="btn ui" id="lb-next" type="button">Next →</button></div></div>"""

    inner = (head + main + drawer + lightbox + f"<script>{JS}</script>")

    if not standalone:
        # The host supplies <!doctype>/<html>/<head>/<body>; a page fragment
        # may still carry its own <title>, stylesheet link and <style>, which
        # the parser hoists into the document head.
        return (f"<title>Redbox Chartbook</title>{FONTS}<style>{CSS}</style>"
                + inner)

    return (
        '<!doctype html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,'
        'viewport-fit=cover">\n'
        '<meta name="color-scheme" content="light dark">\n'
        '<meta name="description" content="Every chart in the redbox chartbook, '
        'its revenue and ESA companions, and the debtbook, on one page.">\n'
        '<meta name="apple-mobile-web-app-capable" content="yes">\n'
        f"<title>Redbox Chartbook</title>\n{FONTS}\n<style>{CSS}</style>\n"
        "</head>\n<body>\n" + inner + "\n</body>\n</html>\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", default=str(ROOT / "reports" / "charts.html"))
    ap.add_argument("--format", choices=("standalone", "artifact"), default="standalone")
    args = ap.parse_args()

    catalogue = load_catalogue()
    books = []
    for bid, name, rel, blurb in BOOKS:
        path = ROOT / rel
        if not path.exists():
            raise SystemExit(f"missing notebook: {rel}")
        books.append((bid, name, parse_notebook(path, catalogue), blurb))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(books, args.format == "standalone"), encoding="utf-8")

    for bid, name, secs, _ in books:
        print(f"{name:<10} {len([f for s in secs for f in s.figures]):>4} charts, "
              f"{len(secs):>3} sections")
    print(f"-> {out} ({out.stat().st_size / 1024:.0f} KB, {args.format})")


if __name__ == "__main__":
    main()
