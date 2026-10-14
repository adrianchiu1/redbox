"""The France fiscal brief as a picture book (D-S19-004): every chart of the
briefing note at full width with its caption, a cover, a one-page summary
and a sources page — and nothing about any meeting or any person.

Reads the filled template through `ggfiscal.report.france_brief` (the same
values and figures the note and the notebook use), keeps the section
headings, the key-figure tiles, the bottom-line points, the figures with
their captions and the loop diagram, drops every paragraph, table and
"ask" box, and removes any sentence that refers to the meeting, the people
or what to ask. A banned-term check runs on the final text and fails the
build if anything slips through.

    python3 tools/build_france_picture_book.py            # -> reports/briefing_FRA_AFT_2026-09/picture_book.html
    python3 tools/build_france_picture_book.py --pdf OUT  # also prints it with headless Chromium
"""
from __future__ import annotations

import argparse
import base64
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ggfiscal.report import france_brief as fb  # noqa: E402

OUT_DIR = fb.BRIEF_DIR
FIG = OUT_DIR / "figures"
SECTIONS = [("s1", 1), ("s2", 2), ("s3", 3), ("s4", 4), ("s5", 5), ("s6", 6), ("s9", 7)]
CHROME = next((p for p in Path("/opt/pw-browsers").glob("chromium*/chrome-linux*/chrome")), None)

# Sentences containing any of these are dropped from every piece of text kept.
BANNED = re.compile(
    r"Maserak|Chief Economist|Head of Research|Chief Investment|\bmeeting\b|in the room|the room\b|ask the AFT|"
    r"to ask\b|worth asking|press the AFT|press on\b|AFT will|the AFT itself|numbers to get|questions? to put|"
    r"research agent|unreachable|before being quoted|costs nothing|the AFT could give", re.I)
STRIP_TAGS = re.compile(r"<[^>]+>")


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", STRIP_TAGS.sub("", html)).strip()


def drop_banned_sentences(html: str) -> str:
    """Remove every sentence that matches BANNED, keeping the inline markup of the rest."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z<€])", html)
    kept = [p for p in parts if not BANNED.search(text_of(p))]
    return " ".join(kept)


def clean_inline(html: str) -> str:
    html = re.sub(r'<span class="tag ext">ext</span>', "", html)
    html = re.sub(r'<span class="tag rb">Redbox</span>', "", html)
    html = re.sub(r"<sup>\[(ext|Redbox)\]</sup>", "", html)
    html = re.sub(r"\(section \d\)", "", html)
    html = re.sub(r"sections? \d(?: and \d)?", "the charts", html)
    return html


def figure_img(key: str) -> str:
    path = FIG / f"{key}.png"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{b64}" alt="{key}">'


def ladder_table(s9: str) -> str:
    """The line-by-line ladder table of section 7, every column, with the
    header row repeated on each printed page and the notes kept."""
    m = re.search(r'<table style="font-size:\.78rem">(.*?)</table>', s9, re.S)
    if not m:
        raise SystemExit("ladder table not found in section 7")
    inner = clean_inline(m.group(1))
    head, rest = re.match(r"\s*(<tr>.*?</tr>)(.*)", inner, re.S).groups()
    return (f'<div class="ladder-wrap"><p class="tabhead">Figure 21, the table: every line of the ladder, with its valuation basis, '
            f'who holds it, whether the État can sell it, how fast, what it pays the État, and what each run sells (the rule under each amount).</p>'
            f'<table class="ladder"><thead>{head}</thead><tbody>{rest}</tbody></table></div>')


def build() -> str:
    b = fb.builder()
    V = b.values()
    filled = b.fill(b.template(), V, inline=False, figures=False)

    def section_html(sid):
        return re.search(rf'<section id="{sid}"[^>]*>(.*?)</section>', filled, re.S).group(1)

    TITLES = {"s6": "Other things that matter: ratings, the EDP, the 2027 budget, the social perimeter"}

    def title(sid):
        if sid in TITLES:
            return TITLES[sid]
        h = re.search(r"<h2>(.*?)</h2>", section_html(sid), re.S).group(1)
        return text_of(re.sub(r'<span class="num">\d+</span>', "", h))

    # --- summary: tiles and the bottom line, sentence-filtered ---------------
    s0 = section_html("s0")
    tiles = re.findall(r'<div class="k">(.*?)</div><div class="v">(.*?)</div><div class="s">(.*?)</div>', s0, re.S)
    tiles_html = "".join(f'<div class="tile"><div class="k">{k}</div><div class="v">{v}</div><div class="s">{clean_inline(c)}</div></div>'
                         for k, v, c in tiles)
    items = re.findall(r"<li>(.*?)</li>", s0, re.S)

    def short(it, keep=2):
        """The bold lead and the first `keep` sentences after it (sentence-filtered)."""
        it = drop_banned_sentences(clean_inline(it))
        m = re.match(r"\s*(<b>.*?</b>)\s*(.*)", it, re.S)
        lead, rest = (m.group(1), m.group(2)) if m else ("", it)
        sents = re.split(r"(?<=[.!?])\s+(?=[A-Z€])", rest)
        return lead + " " + " ".join(sents[:keep])

    points = "".join(f"<li>{short(it)}</li>" for it in items)

    # --- plates: every figure with its caption, in the note's order ------------
    plates = []
    n = 0
    for sid, num in SECTIONS:
        chunks = fb.chunks(sid)
        figs = [(k, v) for k, v in chunks if k in ("fig", "svg")]
        caps = [v for k, v in chunks if k == "html" and v.startswith("<p><small>")]
        body = []
        if sid == "s6":                      # context, no charts: the bold leads with their sentences, filtered
            for para in re.findall(r"<p>(.*?)</p>", section_html("s6"), re.S):
                t = drop_banned_sentences(clean_inline(para))
                if text_of(t):
                    body.append(f"<p class='ctx'>{t}</p>")
        ci = 0
        for k, v in figs:
            n += 1
            if k == "fig":
                cap = text_of(caps[ci]) if ci < len(caps) else ""
                ci += 1
                cap = drop_banned_sentences(clean_inline(cap))
                body.append(f'<figure class="plate">{figure_img(v)}<figcaption>{cap}</figcaption></figure>')
                if v == "bs_ladder":             # the whole Figure 21 table follows its plate
                    body.append(ladder_table(section_html("s9")))
            else:
                body.append(f'<figure class="plate loop">{v}<figcaption>The wrong-way loop: the interest bill feeds the deficit, '
                            f'the deficit the issuance, the issuance the next year\'s interest; the market-pricing loop (spread, ratings, index '
                            f'eligibility) runs alongside it.</figcaption></figure>')
        plates.append(f'<section class="chapter"><h2><span class="num">{num}</span>{title(sid)}</h2>{"".join(body)}</section>')

    sources = f"""
<section class="chapter sources"><h2><span class="num">8</span>Sources and method</h2>
<p>Every chart is drawn from the flat files of the Redbox debt book (run {V.get('benchmark_run', '20260911')}): the per-security register of French
negotiable debt at the debt office's snapshot of 10 September 2026, the interest and financing chains, the balance ledger and the strict
expenditure and revenue matrix, with the Eurostat debt history, the general-government financial balance sheet (gov_10a_ggfa, updated
{V['bs_updated_ggfa']}), the property-income flows and the non-financial balance sheet retrieved on 12 October 2026.</p>
<p>The forward paths come from <code>ggfiscal.debt.simulate</code>: the register rolled forward year by year under declared scenarios
(a primary-balance path, real growth, an OAT–Bund spread path and a Bund curve, a constant maturity profile for issuance), the
interest bill feeding the deficit and the deficit the issuance. The six paths are Redbox's statistical benchmark and five 2027
political configurations declared by the committee on 11 October 2026; the asset-side runs sell the lines of the ladder under the
committee's rules of 14 October 2026, the proceeds retiring debt and the income forgone coming off the primary balance.</p>
<p>Valuations on the asset side: the Compte général de l'État 2025 (unlisted holdings at the État's share of own funds, loans, cash,
tangible assets), the APE's portfolio valuation at 30 June 2025 (listed lines), the schemes' own 2025 accounts and the Cour des comptes'
2022 report (pension reserves), the Caisse des dépôts' and the Banque de France's 2025 accounts. Market facts (spreads, ratings,
holder shares, political programmes) are from public sources as of 11 October 2026 and are not verified against primary releases.</p>
<p class="fine">Redbox debt book · France · October 2026. Interest on the accrual basis, general government; EUR bn unless stated; calendar years.</p>
</section>"""

    css = """
:root{--ink:#0b0b0b;--muted:#6b6a64;--line:#d9d7cf;--soft:#f3f2ec;--accent:#0055A4;--risk:#A51E22}
@page{size:A4;margin:14mm 13mm 16mm}
*{box-sizing:border-box}
body{font-family:"Source Sans 3","Segoe UI",Helvetica,Arial,sans-serif;color:var(--ink);margin:0;font-size:10pt;line-height:1.38}
.cover{height:255mm;display:flex;flex-direction:column;justify-content:flex-end;break-after:page;border-left:6px solid var(--accent);padding-left:14mm}
.cover .eyebrow{font-size:9pt;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:10mm}
.cover h1{font-size:30pt;line-height:1.08;margin:0 0 8mm;font-weight:700;max-width:150mm}
.cover .lede{font-size:12.5pt;color:#333;max-width:150mm;margin:0 0 14mm}
.cover .date{font-size:9.5pt;color:var(--muted)}
.summary{break-after:page}
h2{font-size:17pt;margin:0 0 5mm;padding-bottom:2mm;border-bottom:2px solid var(--ink)}
h2 .num{display:inline-block;min-width:9mm;color:var(--accent);font-weight:700}
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:4mm;margin:0 0 6mm}
.tile{background:var(--soft);padding:3mm 4mm;border-radius:2mm}
.tile .k{font-size:7.5pt;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.tile .v{font-size:18pt;font-weight:700;margin:1mm 0}
.tile .s{font-size:7.8pt;color:var(--muted)}
ol.points{padding-left:5mm;margin:0}
ol.points li{margin:0 0 2.6mm;font-size:9.4pt}
.chapter{break-before:page}
.plate{margin:0 0 7mm;break-inside:avoid}
.plate img{width:100%;height:auto;display:block;border:1px solid var(--line)}
.plate.loop svg{width:100%;height:auto;max-height:110mm;display:block}
figcaption{font-size:8.8pt;color:#333;margin-top:2mm;line-height:1.35}
p.ctx{font-size:9.4pt;margin:0 0 3mm}
.sources p{font-size:9.2pt}
.ladder-wrap{break-before:page}
p.tabhead{font-size:8.8pt;color:#333;margin:0 0 3mm}
table.ladder{width:100%;border-collapse:collapse;table-layout:fixed;font-size:6.2pt;line-height:1.25}
table.ladder th,table.ladder td{padding:1.6px 2px;vertical-align:top;border-bottom:1px solid var(--line);text-align:right;overflow-wrap:anywhere}
table.ladder th{background:var(--soft);text-align:right;font-weight:600}
table.ladder th.l,table.ladder td.l{text-align:left}
table.ladder thead{display:table-header-group}
table.ladder tr{break-inside:avoid}
table.ladder tr.hl td{background:#f6f5f0;font-weight:600}
table.ladder th:nth-child(1){width:12%} table.ladder th:nth-child(2){width:8%} table.ladder th:nth-child(3){width:5%}
table.ladder th:nth-child(4){width:15%} table.ladder th:nth-child(5){width:4.5%} table.ladder th:nth-child(6){width:6.5%}
table.ladder th:nth-child(7){width:5%} table.ladder th:nth-child(8){width:4%} table.ladder th:nth-child(9){width:9%} table.ladder th:nth-child(10){width:31%}
table.ladder small{color:var(--muted)}
p.fine{font-size:8pt;color:var(--muted);margin-top:8mm}
code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:8.5pt}
"""
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>France · the fiscal picture</title><style>{css}</style></head><body>
<section class="cover">
  <div class="eyebrow">Redbox debt book · France</div>
  <h1>France: the fiscal picture</h1>
  <p class="lede">The debt, the interest bill, the shortening stock, who holds it, what the 2027 election does to it, and what the state owns against it — in charts.</p>
  <div class="date">October 2026 · data to 10 September 2026, spreads to 11 October 2026</div>
</section>
<section class="summary">
  <h2>In six numbers and seven points</h2>
  <div class="tiles">{tiles_html}</div>
  <ol class="points">{points}</ol>
</section>
{"".join(plates)}
{sources}
</body></html>"""
    bad = [m.group(0) for m in BANNED.finditer(text_of(html))]
    if bad:
        raise SystemExit(f"banned terms left in the picture book: {sorted(set(bad))}")
    return html


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, default=None, help="also print to this PDF with headless Chromium")
    a = ap.parse_args()
    html = build()
    out = OUT_DIR / "picture_book.html"
    out.write_text(html, encoding="utf-8")
    n = html.count("<figure")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.2f} MB, {n} plates)")
    if a.pdf:
        if CHROME is None:
            raise SystemExit("no Chromium found under /opt/pw-browsers")
        subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
                        f"--print-to-pdf={a.pdf}", "--virtual-time-budget=20000", out.resolve().as_uri()],
                       check=True, capture_output=True)
        print(f"wrote {a.pdf} ({a.pdf.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
