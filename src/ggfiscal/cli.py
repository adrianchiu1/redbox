"""ggfiscal CLI (§11.2): fetch | standardise | build | reconcile | validate |
report | detect-vintages, plus register/coverage helpers."""

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


if __name__ == "__main__":
    app()
