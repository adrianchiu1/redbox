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

def norm_text(t: str) -> str:
    return RUN_RE.sub("<RUN>", t)

def compare_exceptions(a: Path, b: Path) -> str | None:
    da, db = pd.read_csv(a, dtype=str, keep_default_na=False), pd.read_csv(b, dtype=str, keep_default_na=False)
    new = db[db.check_id.isin(NEW_CHECKS)]
    rest = db[~db.check_id.isin(NEW_CHECKS)].reset_index(drop=True)
    if (new.severity != "OK").any():
        return f"new check rows not OK: {new[new.severity != 'OK'].values.tolist()}"
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
        return None if da.equals(db) else "rows other than the new files' differ"
    da, db = pd.read_csv(a, low_memory=False, dtype=str, keep_default_na=False), \
             pd.read_csv(b, low_memory=False, dtype=str, keep_default_na=False)
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
    # only run_id differed; but check byte equality after normalising the raw text
    if norm_text(ta.decode()) != norm_text(tb.decode()):
        return "raw text differs beyond run_id normalisation (formatting?)"
    return None

def main() -> int:
    global BASE, NEW_CHECKS, NEW_FILES
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("baseline", help="directory holding canonical/ and deliverables/ copies")
    ap.add_argument("--new-checks", default="", help="check ids whose OK rows exceptions.csv may gain")
    ap.add_argument("--new-file", action="append", default=[], help="a new deliverable allowed (empty)")
    args = ap.parse_args()
    BASE = Path(args.baseline)
    NEW_CHECKS = {c for c in args.new_checks.split(",") if c}
    NEW_FILES = set(args.new_file)
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
                # the bridge's own row, and the dictionary row count (14 rows describe the bridge)
                strip = lambda t: "\n".join(re.sub(r"\| `data_dictionary.csv` \| \d+ \|", "| `data_dictionary.csv` | N |", l)
                                            for l in norm_text(t).splitlines()
                                            if not any(f in l for f in NEW_FILES))
                r = None if strip(a.read_text()) == strip(b.read_text()) else "text differs beyond the new files' rows"
            else:
                r = None if norm_text(a.read_text()) == norm_text(b.read_text()) else "text differs"
            if r:
                print(f"DIFF {name}/{n}: {r}")
                bad += 1
    print("BYTE-IDENTITY (run_id excepted):", "OK" if bad == 0 else f"{bad} problem(s)")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
