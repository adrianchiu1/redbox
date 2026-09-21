"""Byte-identity gate (REPLICATION_KICKOFF.md §12 Stage R0; every later
stage's "no number moves for GBR/FRA/DEU"): compare data/canonical/*.csv
and deliverables/* against a baseline copy, ignoring only run ids (the
run_id column of CSVs and the run-id / timestamp stamps of the generated
README).

    # before the change
    mkdir -p /tmp/gg_baseline && cp -r data/canonical /tmp/gg_baseline/canonical \
        && cp -r deliverables /tmp/gg_baseline/deliverables
    # after the chain (build, reconcile, validate, report, flatten)
    python3 tools/byte_identity.py /tmp/gg_baseline

Stage R0 (D-S15-009) allowed exactly two additions, which are the options:
`--new-checks V41,V42` (exceptions.csv may gain OK rows of those checks)
and `--new-file fy_cy_bridge.csv` (a new, empty deliverable with its
data-dictionary and README rows). Exit 1 on any other difference.

Stage U0 (D-S16-010) adds `--countries GBR,FRA,DEU`: the comparison is
restricted to those countries' rows — every CSV with an `iso3` column is
filtered on both sides, `exceptions.csv` drops the findings scoped to
another country and compares the unscoped OK rows on (check_id, severity)
only (their messages carry country counts), `crosswalks.csv` drops the
crosswalks named by `--new-crosswalk`, and the READMEs are compared with
row counts and the excluded countries' lines normalised. A new country's
rows are therefore invisible to the gate; the existing countries' values
must still match byte for byte. `--new-file` may then name a non-empty
per-country file (strict_USA.csv).
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

RUN_RE = re.compile(r"\d{8}T\d{6}Z")
REPO = Path(__file__).resolve().parents[1]
BASE = Path()
NEW_CHECKS: set[str] = set()
NEW_FILES: set[str] = set()
NEW_CROSSWALKS: set[str] = set()
NEW_SCOPES: set[str] = set()         # exceptions.csv rows allowed to appear (any severity but ERROR)
CHECK_NOW_SCOPED: set[str] = set()   # checks whose unscoped OK row an excluded country's findings replace
COUNTRIES: set[str] = set()          # empty = compare everything
EXCLUDED_NAMES: list[str] = []       # display names / iso3 of the countries left out


def norm_text(t: str) -> str:
    return RUN_RE.sub("<RUN>", t)


def _restrict(df: pd.DataFrame) -> pd.DataFrame:
    if COUNTRIES and "iso3" in df.columns:
        df = df[df.iso3.isin(COUNTRIES)]
    return df.reset_index(drop=True)


def compare_exceptions(a: Path, b: Path) -> str | None:
    da, db = pd.read_csv(a, dtype=str, keep_default_na=False), pd.read_csv(b, dtype=str, keep_default_na=False)
    new = db[db.check_id.isin(NEW_CHECKS)]
    rest = db[~db.check_id.isin(NEW_CHECKS)].reset_index(drop=True)
    if (new.severity != "OK").any():
        return f"new check rows not OK: {new[new.severity != 'OK'].values.tolist()}"
    if COUNTRIES:
        def scoped_out(scope: str) -> bool:
            head = scope.split("/")[0]
            return bool(re.fullmatch(r"[A-Z]{3}", head)) and head not in COUNTRIES
        excluded = db[db.scope.map(scoped_out)]
        rest = rest[~rest.scope.map(scoped_out)].reset_index(drop=True)
        da = da[~da.scope.map(scoped_out)].reset_index(drop=True)
        # --new-scope: rows the register gained (a blocked host's V18 WARN);
        # --check-now-scoped: a check whose unscoped OK row is replaced by
        # scoped findings of an excluded country (V24 for the USA); both
        # are listed by the caller, never inferred
        new_rows = rest[rest.scope.isin(NEW_SCOPES)]
        if (new_rows.severity == "ERROR").any():
            return f"new scoped rows at ERROR: {new_rows.values.tolist()}"
        rest = rest[~rest.scope.isin(NEW_SCOPES)].reset_index(drop=True)
        for chk in CHECK_NOW_SCOPED:
            gone = da[(da.check_id == chk) & (da.scope == "-") & (da.severity == "OK")]
            if len(gone) == 1 and not (rest.check_id == chk).any() \
                    and (excluded.check_id == chk).any():
                da = da[~((da.check_id == chk) & (da.scope == "-"))].reset_index(drop=True)
        # unscoped rows carry counts in their messages ("4 countries x 41")
        cols = ["check_id", "severity", "scope"]
        ka, kb = da[cols].reset_index(drop=True), rest[cols].reset_index(drop=True)
        if not ka.equals(kb):
            return "rows other than the new OK checks differ (check/severity/scope, other countries' rows excluded)"
        scoped = da.scope != "-"
        if not da[scoped].reset_index(drop=True).equals(rest[scoped.values].reset_index(drop=True)):
            return "scoped rows of the retained countries differ"
        return None
    if not da.reset_index(drop=True).equals(rest):
        return "rows other than the new OK checks differ"
    return None


def compare_csv(a: Path, b: Path) -> str | None:
    ta, tb = a.read_bytes(), b.read_bytes()
    if ta == tb:
        return None
    if a.name == "exceptions.csv":
        return compare_exceptions(a, b)
    if a.name == "data_dictionary.csv":
        da = pd.read_csv(a, dtype=str, keep_default_na=False)
        db = pd.read_csv(b, dtype=str, keep_default_na=False)
        db = db[~db.iloc[:, 0].isin(NEW_FILES)].reset_index(drop=True)
        if da.equals(db):
            return None
        diff = pd.concat([da, db]).drop_duplicates(keep=False)
        return f"rows other than the new files' differ:\n{diff.to_string()[:2000]}"
    da, db = pd.read_csv(a, low_memory=False, dtype=str, keep_default_na=False), \
             pd.read_csv(b, low_memory=False, dtype=str, keep_default_na=False)
    if a.name == "crosswalks.csv" and NEW_CROSSWALKS and "crosswalk" in db.columns:
        db = db[~db.crosswalk.isin(NEW_CROSSWALKS)].reset_index(drop=True)
    da, db = _restrict(da), _restrict(db)
    for d in (da, db):
        for c in list(d.columns):
            if c == "run_id":
                d[c] = "<RUN>"
            elif d[c].str.contains(r"\d{8}T\d{6}Z", regex=True).any():
                d[c] = d[c].str.replace(r"\d{8}T\d{6}Z", "<RUN>", regex=True)
    if da.shape != db.shape:
        return f"shape {db.shape} vs baseline {da.shape}"
    if list(da.columns) != list(db.columns):
        return f"columns differ: {set(da.columns) ^ set(db.columns)}"
    if not da.equals(db):
        diff = (da != db)
        cols = diff.sum()[diff.sum() > 0].to_dict()
        return f"values differ in {cols}"
    if COUNTRIES:
        return None      # the restricted frames are equal; raw text differs by the other rows
    # only run_id differed; but check byte equality after normalising the raw text
    if norm_text(ta.decode()) != norm_text(tb.decode()):
        return "raw text differs beyond run_id normalisation (formatting?)"
    return None


def _readme_norm(t: str) -> str:
    lines = []
    for line in norm_text(t).splitlines():
        if any(f in line for f in NEW_FILES):
            continue
        if COUNTRIES and any(n in line for n in EXCLUDED_NAMES):
            continue
        if COUNTRIES:
            line = re.sub(r"\| \d[\d,]* \|", "| N |", line)          # row counts
            line = re.sub(r"(ERROR|WARN|OK|SKIP)=\d+", r"\1=N", line)   # validate counts
            line = re.sub(r"\b\d+ (line series|lines?|countries|series|rows)\b", r"N \1", line)
        else:
            line = re.sub(r"\| `data_dictionary.csv` \| \d+ \|", "| `data_dictionary.csv` | N |", line)
        lines.append(line)
    return "\n".join(lines)


def compare_readme(a: Path, b: Path) -> str | None:
    ra, rb = _readme_norm(a.read_text()), _readme_norm(b.read_text())
    if ra == rb:
        return None
    import difflib
    d = [l for l in difflib.unified_diff(ra.splitlines(), rb.splitlines(), lineterm="", n=0)
         if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
    return "text differs beyond the new files' rows:\n  " + "\n  ".join(d[:20])


def main() -> int:
    global BASE, NEW_CHECKS, NEW_FILES, NEW_CROSSWALKS, NEW_SCOPES, CHECK_NOW_SCOPED, COUNTRIES, EXCLUDED_NAMES
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("baseline", help="directory holding canonical/ and deliverables/ copies")
    ap.add_argument("--new-checks", default="", help="check ids whose OK rows exceptions.csv may gain")
    ap.add_argument("--new-file", action="append", default=[], help="a new deliverable allowed (empty, or per-country with --countries)")
    ap.add_argument("--new-crosswalk", action="append", default=[], help="a new crosswalk whose rows crosswalks.csv may gain")
    ap.add_argument("--countries", default="", help="restrict the comparison to these iso3 codes (U0: GBR,FRA,DEU)")
    ap.add_argument("--new-scope", action="append", default=[],
                    help="an exceptions.csv scope allowed to appear (e.g. register/CBO_SITE), never at ERROR")
    ap.add_argument("--check-now-scoped", default="",
                    help="checks whose unscoped OK row may be replaced by an excluded country's scoped findings (V24)")
    args = ap.parse_args()
    BASE = Path(args.baseline)
    NEW_CHECKS = {c for c in args.new_checks.split(",") if c}
    NEW_FILES = set(args.new_file)
    NEW_CROSSWALKS = set(args.new_crosswalk)
    NEW_SCOPES = set(args.new_scope)
    CHECK_NOW_SCOPED = {c for c in args.check_now_scoped.split(",") if c}
    COUNTRIES = {c for c in args.countries.split(",") if c}
    if COUNTRIES:
        sys.path.insert(0, str(REPO / "src"))
        from ggfiscal import config
        for iso3, cfg in config.countries().items():
            if iso3 not in COUNTRIES:
                EXCLUDED_NAMES += [iso3, cfg["name"]]
    bad = 0
    pairs = [("canonical", REPO / "data" / "canonical"), ("deliverables", REPO / "deliverables")]
    for name, live in pairs:
        base = BASE / name
        names = sorted(set(p.name for p in base.iterdir()) | set(p.name for p in live.iterdir()))
        for n in names:
            a, b = base / n, live / n
            if not a.exists() or not b.exists():
                # parquet twins are local-only; new deliverables are reported
                print(f"ONLY_IN_{'LIVE' if b.exists() else 'BASE'} {name}/{n}")
                if n in NEW_FILES and b.exists():
                    rows = pd.read_csv(b)
                    if COUNTRIES and "iso3" in rows.columns:
                        rows = rows[rows.iso3.isin(COUNTRIES)]
                        print(f"  (allowed new file; {len(rows)} rows of the retained countries - must be 0)")
                    elif COUNTRIES and n.startswith("strict_"):
                        print(f"  (allowed new per-country file, {len(rows)} rows)")
                        rows = rows.iloc[0:0]
                    else:
                        print(f"  (allowed new file, {len(rows)} rows - must be 0)")
                    bad += 1 if len(rows) else 0
                elif n.endswith(".csv") or n.endswith(".md"):
                    bad += 1
                continue
            if n.endswith(".parquet"):
                continue
            if n.endswith(".csv"):
                r = compare_csv(a, b)
            elif n == "README.md":
                r = compare_readme(a, b)
            else:
                r = None if norm_text(a.read_text()) == norm_text(b.read_text()) else "text differs"
            if r:
                print(f"DIFF {name}/{n}: {r}")
                bad += 1
    scope = f" for {','.join(sorted(COUNTRIES))}" if COUNTRIES else ""
    print(f"BYTE-IDENTITY{scope} (run_id excepted):", "OK" if bad == 0 else f"{bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
