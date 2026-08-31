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
        typer.echo(f"OK    {rec['source_id']}  sha256={rec['sha256'][:12]}  {rec['size']} bytes")
    for rec in failed:
        typer.echo(f"FAIL  {rec['source_id']}  {rec['error']}: {rec['detail']}")
    if failed:
        blocked = [r for r in failed if r["error"] == "FetchBlocked"]
        if blocked:
            typer.echo(f"\n{len(blocked)} source(s) denied by egress policy — see OPEN_QUESTIONS.md OQ-1.")
        raise typer.Exit(code=1)


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
    if counts.get("ERROR"):
        raise typer.Exit(code=1)


@app.command()
def coverage():
    """Write the coverage matrix (v0 shape until the harvest lands)."""
    from ggfiscal.coverage import build_v0

    typer.echo(f"wrote {build_v0()}")


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
    """Raw → standard tidy tables (Stage 1)."""
    _not_yet(1)


@app.command()
def build():
    """Standard → canonical deliverables (Stage 1)."""
    _not_yet(1)


@app.command()
def reconcile():
    """§8 reconciliation module (Stage 5; base bridge from Stage 0 harvest)."""
    _not_yet(5)


@app.command()
def report():
    """Validation and reconciliation reports (Stage 1+)."""
    _not_yet(1)


@app.command("detect-vintages")
def detect_vintages():
    """Compare live source metadata against the register (§11.7)."""
    _not_yet(6)


if __name__ == "__main__":
    app()
