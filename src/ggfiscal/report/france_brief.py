"""The France fiscal brief as notebook cells (D-S18-003).

`notebooks/France_fiscal_brief_20261013.ipynb` reproduces the AFT briefing
note (`reports/briefing_FRA_AFT_2026-09/briefing_inline.html`) from the
flat files: it renders every chart, fills the note's template with the same
values the HTML builder uses, and displays each section in order, with the
text and tables as HTML and the charts as images. The questions for the AFT
(section 7 and the "To ask the AFT" boxes) are left out of the notebook;
the HTML keeps them.

`chunks(section_id)` returns a section as a list of ("html", str),
("fig", key) and ("svg", str) items; `title(section_id)` its heading.
"""
from __future__ import annotations

import importlib.util
import re
from functools import lru_cache

from ggfiscal.debt import simulate as sim

BRIEF_DIR = sim.ROOT / "reports" / "briefing_FRA_AFT_2026-09"
SECTIONS = ("s0", "s1", "s2", "s3", "s4", "s5", "s6", "s8")   # s7 is the AFT questions


def builder():
    """The note builder in tools/build_briefing_fra.py, imported by path."""
    spec = importlib.util.spec_from_file_location(
        "build_briefing_fra", sim.ROOT / "tools" / "build_briefing_fra.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@lru_cache(maxsize=1)
def filled() -> str:
    """The template with every value filled and the {{fig:key}} markers kept."""
    b = builder()
    return b.fill(b.template(), b.values(), inline=False, figures=False)


def clear_cache() -> None:
    filled.cache_clear()


def _section(sid: str) -> str:
    m = re.search(rf'<section id="{sid}"[^>]*>(.*?)</section>', filled(), re.S)
    if not m:
        raise KeyError(sid)
    return m.group(1)


def title(sid: str) -> str:
    h = re.search(r"<h2>(.*?)</h2>", _section(sid), re.S).group(1)
    num = re.search(r'<span class="num">(\d+)</span>', h)
    text = re.sub(r"<[^>]+>", "", re.sub(r'<span class="num">\d+</span>', "", h)).strip()
    return f"{num.group(1)}. {text}" if num else text


def _tiles(html: str) -> str:
    """The key-figure tiles as a plain table (the note's CSS is not in a notebook).
    The tiles block closes the bottom-line section."""
    i = html.find('<div class="tiles">')
    if i < 0:
        return html
    rows = re.findall(r'<div class="k">(.*?)</div><div class="v">(.*?)</div><div class="s">(.*?)</div>',
                      html[i:], re.S)
    body = "".join(f"<tr><td style='text-align:left'>{k}</td><td><b>{v}</b></td>"
                   f"<td style='text-align:left'>{c}</td></tr>" for k, v, c in rows)
    return html[:i] + f"<table><tr><th>Key figure</th><th>Value</th><th>Context</th></tr>{body}</table>"


def _clean(html: str) -> str:
    html = re.sub(r'<div class="ask">.*?</div>', "", html, flags=re.S)       # questions for the AFT
    html = re.sub(r"<h2>.*?</h2>", "", html, count=1, flags=re.S)            # the heading is a markdown cell
    html = re.sub(r'<span class="tag ext">ext</span>', "<sup>[ext]</sup>", html)
    html = re.sub(r'<span class="tag rb">Redbox</span>', "<sup>[Redbox]</sup>", html)
    html = re.sub(r'<div class="risk-box">(.*?)</div>', r"<blockquote>\1</blockquote>", html, flags=re.S)
    return _tiles(html)


def chunks(sid: str) -> list[tuple[str, str]]:
    """A section in display order: text and tables, figures, the loop diagram."""
    html = _clean(_section(sid))
    token = re.compile(r'<figure>\{\{fig:([a-z_0-9]+)\}\}<figcaption>(.*?)</figcaption></figure>'
                       r'|<div class="loop">\s*(<svg.*?</svg>)\s*</div>', re.S)
    out, pos = [], 0
    for m in token.finditer(html):
        text = html[pos:m.start()].strip()
        if text:
            out.append(("html", text))
        if m.group(1):
            out.append(("fig", m.group(1)))
            out.append(("html", f"<p><small>{m.group(2)}</small></p>"))
        else:
            out.append(("svg", m.group(3)))
        pos = m.end()
    rest = html[pos:].strip()
    if rest:
        out.append(("html", rest))
    return out


def figures() -> list[str]:
    """Every figure key the notebook shows, in order."""
    return [v for sid in SECTIONS for k, v in chunks(sid) if k == "fig"]
