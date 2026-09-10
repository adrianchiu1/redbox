"""ggfiscal CLI (§11.2): fetch | standardise | build | reconcile | validate |
report | flatten | detect-vintages, plus register/coverage helpers."""

from __future__ import annotations

import sys

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def fetch(all: bool = typer.Option(False, "--all", help="Pull every Stage 0 probe endpoint")):
    """Pull registered sources into the immutable snapshot store (D8)."""
    from ggfiscal.ingest.fetch import fetch_all

    ok, failed = fetch_all()
    for rec in ok:
        typer.echo(f"OK    {rec['source_id']}/{rec.get('part', '')}  "
                   f"sha256={rec['sha256'][:12]}  {rec['size']} bytes")
    for rec in failed:
        typer.echo(f"FAIL  {rec['source_id']}/{rec.get('part', '')}  {rec['error']}: {rec['detail']}")
    if failed:
        blocked = [r for r in failed if r["error"] == "FetchBlocked"]
        if blocked:
            typer.echo(f"\n{len(blocked)} source(s) denied by egress policy — see OPEN_QUESTIONS.md OQ-1.")
        raise typer.Exit(code=1)


@app.command("ingest-file")
def ingest_file(path: str,
                source_id: str = typer.Option(..., "--source-id"),
                part: str = typer.Option(..., "--part"),
                url: str = typer.Option(..., "--url",
                                        help="Publication landing URL"),
                note: str = typer.Option("", "--note")):
    """Store a hand-retrieved file as a D8 snapshot (for publishers no
    client here can reach — obr.uk, OQ-6). Committed to git, unlike
    refetchable snapshots (D-S7-001)."""
    from ggfiscal.ingest.fetch import ingest_local

    rec = ingest_local(path, source_id, part, url, note)
    typer.echo(f"OK    {rec['source_id']}/{rec['part']}  "
               f"sha256={rec['sha256'][:12]}  {rec['size']} bytes  -> {rec['path']}")


@app.command()
def validate():
    """Run the validation suite; exit 1 on any ERROR (§10)."""
    from ggfiscal.validate.runner import run_all, write_exceptions

    findings = run_all()
    dest = write_exceptions(findings)
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    for f in findings:
        if f.severity in ("ERROR", "WARN"):
            typer.echo(f"{f.severity:5s} {f.check_id:12s} {f.scope}: {f.message}")
    typer.echo(f"\n{' '.join(f'{k}={v}' for k, v in sorted(counts.items()))}  -> {dest}")
    from ggfiscal import manifest as M
    M.update_deliverables()
    if counts.get("ERROR"):
        raise typer.Exit(code=1)


@app.command()
def coverage():
    """Measure first/last usable year per (country, line, source) from the
    harvested snapshots into coverage_matrix_v0.csv (pre-harvest: empty frame)."""
    from ggfiscal.coverage import gate0_line_coverage, measure

    dest = measure()
    covered, uncovered = gate0_line_coverage()
    typer.echo(f"wrote {dest}  ({covered}/66 lines covered)")
    for iso3, classification, line in uncovered:
        typer.echo(f"  NO_COVERAGE {iso3}/{classification}/{line}")


@app.command()
def register():
    """Regenerate source_register.csv from config/sources.yaml."""
    from ggfiscal.register import build

    typer.echo(f"wrote {build()}")


def _not_yet(stage: int) -> None:
    typer.echo(f"not built yet: arrives with Stage {stage} (see COFOG_KICKOFF.md §12 and HANDOFF.md)")
    sys.exit(2)


@app.command()
def standardise():
    """Raw snapshots → tidy per-country anchor tables in data/standard/."""
    from ggfiscal.standardise.materialise import write

    for p in write():
        typer.echo(f"wrote {p}")


@app.command()
def build():
    """Anchors → canonical history, both trees + balance ledger (§5 schema).
    Also refreshes the standard layer and the §8.3 history decomposition."""
    from ggfiscal.build import build as run_build
    from ggfiscal.reconcile.dynamics import write as write_dynamics
    from ggfiscal.standardise.materialise import write as write_standard

    for p in write_standard():
        typer.echo(f"wrote {p}")
    for name, p in run_build().items():
        typer.echo(f"wrote {name}: {p}")
    typer.echo(f"wrote {write_dynamics()}")


@app.command()
def reconcile():
    """§8 reconciliation: the §8.2 base-year bridge, the §8.3-8.5 forecast
    decomposition (weo_explanation, net_interest_check, weo_residual_history)
    for both variants and every harvested WEO vintage, plus the anchor-vs-IMF
    / anchor-vs-OECD-RS diagnostics."""
    from ggfiscal.reconcile import bridge, explanation, recon_v0

    dest, summaries = bridge.compute()
    typer.echo(f"wrote {dest}")
    for s in summaries:
        typer.echo(f"  {s['iso3']} WEO {s['weo_vintage']}: base={s['base_year']} "
                   f"overlap={s['n_overlap']}"
                   + (f" mean_gap_nlb={s['mean_gap_nlb_pct_te']}%TE"
                      f" sigma={s['sigma_gap_nlb_pct_te']}"
                      f" unexplained={s['n_unexplained']}"
                      if s.get("base_year") else ""))
    for name, p in explanation.write().items():
        typer.echo(f"wrote {name}: {p}")
    for p in recon_v0.compute():
        typer.echo(f"wrote {p}")
    from ggfiscal import manifest as M
    M.update_deliverables()


@app.command()
def report():
    """Reports: small multiples (Stage 1), the reconciliation report with
    contribution charts (Stage 5, §10), and the Stage 6 packaging set —
    validation_report.html, the regenerated source register, the generated
    README (§11.6 deliverable 10) and the completed run manifest."""
    from ggfiscal import manifest as M
    from ggfiscal.register import build as write_register
    from ggfiscal.report.readme import write as write_readme
    from ggfiscal.report.reconciliation import write as write_recon
    from ggfiscal.report.small_multiples import write
    from ggfiscal.report.validation import write as write_validation

    typer.echo(f"wrote {write()}")
    typer.echo(f"wrote {write_recon()}")
    typer.echo(f"wrote {write_validation()}")
    typer.echo(f"wrote {write_register()}")
    typer.echo(f"wrote {write_readme()}")
    typer.echo(f"updated {M.update_deliverables()}")
    # The flat-file bundle is packaging too: rendering it here keeps
    # deliverables/ in lockstep with every reported run.
    from ggfiscal.publish.flatten import write as write_flat
    for name, path in write_flat().items():
        typer.echo(f"wrote deliverables/{name}: {path}")


@app.command()
def flatten():
    """Render the plain flat-file bundle in `deliverables/` from the gated
    canonical layer: the COFOG and ESA trees, the balance ledger, the WEO
    levels bridge and dynamics reconciliation, a per-series catalogue and a
    data dictionary — every row carrying the derivation behind its value."""
    from ggfiscal.publish.flatten import write

    for name, path in write().items():
        typer.echo(f"wrote {name}: {path}")


@app.command("detect-vintages")
def detect_vintages(hash: bool = typer.Option(
        False, "--hash",
        help="Also re-download every machine-readable pull and compare "
             "content hashes against the latest snapshots (a full re-harvest "
             "in bandwidth; nothing is saved)")):
    """Compare live source metadata against the register (§11.7); write
    reports/vintage_diff.md. A new vintage is a config change plus rebuild,
    never a code change."""
    from ggfiscal.vintages import detect, write_report

    findings = detect(hash_tier=hash)
    dest = write_report(findings, hash_tier=hash)
    from ggfiscal import manifest as M
    M.update_deliverables()
    for f in findings:
        if f.status != "unchanged":
            typer.echo(f"{f.status.upper():13s} {f.source_id}: {f.detail}")
    n_action = sum(f.status in ("new_vintage", "changed", "error") for f in findings)
    typer.echo(f"\nwrote {dest}  ({n_action} finding(s) need action)")


# ---------- debt extension (DEBT_KICKOFF.md) ----------

debt_app = typer.Typer(no_args_is_help=True, add_completion=False,
                       help="Debt securities register, interest/financing "
                            "reconciliation, maturity profile (DEBT_KICKOFF.md).")
app.add_typer(debt_app, name="debt")


@debt_app.command("fetch")
def debt_fetch(family: list[str] = typer.Option(None, "--family",
                                                help="Restrict to these families")):
    """Pull every debt-extension source into the snapshot store (Stage D0).
    Blocked hosts (OQ-8) are reported, not skipped silently."""
    from ggfiscal.debt.fetch import fetch_all as debt_fetch_all

    ok, failed = debt_fetch_all(tuple(family) if family else None)
    for rec in ok:
        typer.echo(f"OK    {rec['source_id']}/{rec.get('part', '')}  "
                   f"sha256={rec['sha256'][:12]}  {rec['size']} bytes")
    for rec in failed:
        typer.echo(f"FAIL  {rec['source_id']}/{rec.get('part', '')}  {rec['error']}: {rec['detail']}")
    blocked = [r for r in failed if r["error"] == "FetchBlocked"]
    if blocked:
        typer.echo(f"\n{len(blocked)} pull(s) denied by egress policy — see OPEN_QUESTIONS.md OQ-8.")
    if failed:
        raise typer.Exit(code=1)


@debt_app.command("build")
def debt_build(no_curves: bool = typer.Option(False, "--no-curves",
                                              help="Skip the BoE yield-curve series")):
    """Reference series and official intermediate totals -> data/canonical/debt_*.csv (Stage D1)."""
    from ggfiscal.debt.build import build as debt_build_

    for name, p in debt_build_(include_curves=not no_curves).items():
        typer.echo(f"wrote {name}: {p}")


@debt_app.command("validate")
def debt_validate():
    """V29-V40 on the built debt tables -> data/canonical/debt_exceptions.csv (SKIP where the register is pending)."""
    import csv
    from ggfiscal import config as C
    from ggfiscal.debt.validate import run_all as debt_run_all

    findings = debt_run_all()
    dest = C.repo_root() / "data" / "canonical" / "debt_exceptions.csv"
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["check_id", "severity", "scope", "message"])
        for x in findings:
            w.writerow([x.check_id, x.severity, x.scope, x.message])
    counts: dict[str, int] = {}
    for x in findings:
        counts[x.severity] = counts.get(x.severity, 0) + 1
    for x in findings:
        if x.severity in ("ERROR", "WARN"):
            typer.echo(f"{x.severity:5s} {x.check_id:5s} {x.scope}: {x.message}")
    typer.echo(f"\n{' '.join(f'{k}={v}' for k, v in sorted(counts.items()))}  -> {dest}")
    if counts.get("ERROR"):
        raise typer.Exit(code=1)


@debt_app.command("ingest-incoming")
def debt_ingest_incoming(folder: str = typer.Option("data/incoming", "--folder")):
    """Store hand-downloaded debt-office files as D8 snapshots (D-S7-001 route).
    Layout: {folder}/{SOURCE_ID}/{part}.{ext}; the part must match a pull
    definition in families/debt_offices.py (or a documented part name) so the
    publication URL is recorded from it."""
    from pathlib import Path
    from ggfiscal import config as C
    from ggfiscal.debt.families import debt_offices as DO
    from ggfiscal.ingest.fetch import ingest_local

    known = {(p.source_id, p.part): p.url for p in DO.pulls()}
    known.update({(p.source_id, p.part): p.url for p in DO.cob_pulls()})
    known.update({(sid, part): url for (sid, part, url) in DO.HAND_PARTS})
    root = C.repo_root() / folder
    n = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        sid, part = path.parent.name, path.stem
        url = known.get((sid, part))
        if url is None:
            typer.echo(f"SKIP  {sid}/{part}: unknown part name (see families/debt_offices.py)")
            continue
        head = path.read_bytes()[:30000]
        text = head.decode("utf-8", "ignore")
        if any(m in text for m in DO.CHALLENGE_MARKERS):
            typer.echo(f"SKIP  {sid}/{part}: bot-challenge page, not data")
            continue
        if len(head) < 400 and any(m in text for m in DO.STUB_MARKERS):
            typer.echo(f"SKIP  {sid}/{part}: server stub ({text.strip()[:60]!r}), not data")
            continue
        rec = ingest_local(path, sid, part, url, note="hand-downloaded by the committee (OQ-8, bot-challenged host)")
        typer.echo(f"OK    {rec['source_id']}/{rec['part']}  sha256={rec['sha256'][:12]}  {rec['size']} bytes")
        n += 1
    typer.echo(f"\n{n} file(s) ingested from {root}")


if __name__ == "__main__":
    app()
