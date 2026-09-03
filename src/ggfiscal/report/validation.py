"""reports/validation_report.html (§11.6 deliverable 10, Stage 6).

Runs the full §10 suite fresh and renders it: severity summary, the per-check
outcome table with the §10 test descriptions, every ERROR (the gate breakers,
none expected), and the WARN tiers grouped with examples — the WARNs are
intended visibility (documented wedges, blocked sources OQ-6, the withheld
DSM join OQ-7, unsynced raw bytes D-S0-004), not defects. exceptions.csv
remains `ggfiscal validate`'s deliverable; this report renders the same
findings for a reader.
"""

from __future__ import annotations

import datetime as dt
import html
from collections import defaultdict
from pathlib import Path

from ggfiscal import config

# §10 one-line test descriptions (the table's Test column, abridged)
CHECK_LABELS = {
    "S0_LINES": "structural: the 66-line universe enumerates",
    "S0_REGISTER": "structural: register entries carry status + endpoint",
    "S0_SNAPSHOTS": "D8: manifest snapshots verify byte-for-byte where present",
    "S0_COVERAGE": "Gate 0: every line has measured coverage from ≥1 source",
    "S0_BRIDGE": "Gate 0: §8.2 bridge computed, all countries, latest vintage",
    "V1": "anchor years reproduce anchor values; IMF GFS within 0.5%",
    "V2": "history: Σ GF01–GF10 = TE (0.1%)",
    "V3": "history: shares sum to 100 ± tol",
    "V4": "values ≥ 0 except legitimately negative lines",
    "V5": "overlap-growth diagnostic per stitch (bias, RMSE)",
    "V6": "boundary growth equals recorded source growth",
    "V7": "every forecast row has source, release date, URL, snapshot hash",
    "V8": "interpolated / converted rows labelled",
    "V9": "observation_type consistent with variant; no C/D in strict",
    "V10": "no forecast beyond source horizon",
    "V11": "no superseded source where a newer vintage applies",
    "V12": "S13 everywhere; non-GG sources carry a perimeter note",
    "V13": "concept compatibility note per stitch",
    "V14": "missing stays missing",
    "V15": "forecast: covered sums ≤ envelope × (1 + tol)",
    "V16": "short/long-term overlap divergence",
    "V17": "coverage_share_year on every proxy/composite row",
    "V18": "register URLs resolve or archived copy present",
    "V19": "GF01_X + GF01_7 = GF01; GF01_X never forecast",
    "V20": "interest rows carry concept_flag; strict rows gross",
    "V21": "Level II GF01.7 vs D.41 payable within 5%",
    "V22": "history: Σ R01–R10 = TR (0.1%)",
    "V23": "history: TR − TE = anchor B.9 (0.1%)",
    "V24": "base-year bridge gaps within tolerance; GBR perimeter stable",
    "V25": "OECD RS reconciliation on tax lines within tolerance",
    "V26": "decomposition additivity exact (history and forecast)",
    "V27": "net-interest cross-check reported everywhere",
    "V28": "reconciliation tables keyed by both vintages",
}

MAX_EXAMPLES = 25


def write(path: Path | None = None) -> Path:
    from ggfiscal.validate.runner import current_stage, run_all

    dest = path or config.repo_root() / "reports" / "validation_report.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    findings = run_all()
    stage = current_stage()
    by_sev: dict[str, int] = defaultdict(int)
    by_check: dict[str, list] = defaultdict(list)
    for f in findings:
        by_sev[f.severity] += 1
        by_check[f.check_id].append(f)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def esc(s: str) -> str:
        return html.escape(str(s))

    parts = [
        "<html><head><meta charset='utf-8'>"
        "<title>gg-fiscal validation report</title><style>"
        "body{font-family:sans-serif;margin:2em;max-width:75em}"
        "table{border-collapse:collapse;margin:1em 0}"
        "td,th{border:1px solid #ccc;padding:0.3em 0.6em;text-align:left;"
        "font-size:0.9em}"
        ".ERROR{background:#fdd}.WARN{background:#ffedcc}.OK{background:#e8f5e9}"
        ".SKIP{background:#eee}</style></head><body>",
        "<h1>Validation report — §10 suite</h1>",
        f"<p>Generated {now} by <code>ggfiscal report</code>; pipeline stage "
        f"{stage}. ERROR blocks the gate; WARN does not (§10). "
        "The machine-readable twin is <code>data/canonical/exceptions.csv</code> "
        "(written by <code>ggfiscal validate</code>).</p>",
        "<h2>Summary</h2><table><tr>"
        + "".join(f"<th>{s}</th>" for s in ("ERROR", "WARN", "OK", "SKIP"))
        + "</tr><tr>"
        + "".join(f"<td class='{s}'>{by_sev.get(s, 0)}</td>"
                  for s in ("ERROR", "WARN", "OK", "SKIP"))
        + "</tr></table>",
        ("<p><b>No ERROR findings: the gate holds.</b></p>"
         if not by_sev.get("ERROR") else
         "<p><b>ERROR findings present — the gate is failing.</b></p>"),
        "<p>The WARN tiers are intended visibility, not defects: documented "
        "concept wedges (V1/V21/V25 crosswalk and perimeter differences), the "
        "withheld AMECO→DSM interest join flagged for the committee (V16, "
        "OQ-7), blocked register URLs (V18, OQ-6), stitch diagnostics at "
        "their measured C/D grades (V5), and raw snapshot bytes of earlier "
        "sessions not synced into this container (S0_SNAPSHOTS, by design "
        "D-S0-004 — provenance lives in the hash manifest).</p>",
        "<h2>Per-check outcomes</h2>",
        "<table><tr><th>check</th><th>test</th><th>worst</th><th>ERROR</th>"
        "<th>WARN</th><th>OK</th><th>SKIP</th></tr>",
    ]
    order = {"ERROR": 0, "WARN": 1, "SKIP": 2, "OK": 3}
    for check in sorted(by_check, key=lambda c: (c[0] != "S", c)):
        fs = by_check[check]
        sevs = defaultdict(int)
        for f in fs:
            sevs[f.severity] += 1
        worst = min((f.severity for f in fs), key=lambda s: order.get(s, 9))
        parts.append(
            f"<tr><td>{esc(check)}</td><td>{esc(CHECK_LABELS.get(check, ''))}"
            f"</td><td class='{worst}'>{worst}</td>"
            + "".join(f"<td>{sevs.get(s, 0) or ''}</td>"
                      for s in ("ERROR", "WARN", "OK", "SKIP"))
            + "</tr>")
    parts.append("</table>")

    errors = [f for f in findings if f.severity == "ERROR"]
    if errors:
        parts.append("<h2>ERROR findings</h2><table>"
                     "<tr><th>check</th><th>scope</th><th>message</th></tr>")
        parts += [f"<tr class='ERROR'><td>{esc(f.check_id)}</td>"
                  f"<td>{esc(f.scope)}</td><td>{esc(f.message)}</td></tr>"
                  for f in errors]
        parts.append("</table>")

    parts.append("<h2>WARN findings (examples per check)</h2>")
    for check in sorted(by_check):
        warns = [f for f in by_check[check] if f.severity == "WARN"]
        if not warns:
            continue
        parts.append(f"<h3>{esc(check)} — {len(warns)} WARN"
                     f"{'' if len(warns) == 1 else 's'}: "
                     f"{esc(CHECK_LABELS.get(check, ''))}</h3><table>"
                     "<tr><th>scope</th><th>message</th></tr>")
        for f in warns[:MAX_EXAMPLES]:
            parts.append(f"<tr class='WARN'><td>{esc(f.scope)}</td>"
                         f"<td>{esc(f.message)}</td></tr>")
        if len(warns) > MAX_EXAMPLES:
            parts.append(f"<tr><td colspan='2'>… {len(warns) - MAX_EXAMPLES} "
                         "more in exceptions.csv</td></tr>")
        parts.append("</table>")

    tol = config.tolerances()
    parts.append("<h2>Tolerances in force (Q4 space)</h2><table>"
                 "<tr><th>key</th><th>value</th></tr>")
    parts += [f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>"
              for k, v in sorted(tol.items())]
    parts.append("</table></body></html>")
    dest.write_text("\n".join(parts), encoding="utf-8")
    return dest
