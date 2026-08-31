"""§11.1 standard layer: tidy per-country anchor tables materialised from the
raw snapshots (via readers). The canonical build consumes the same reader
functions; this layer pins what the anchors said at build time so V1 and
diffing across runs have a stable artifact."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ggfiscal import config


def write(dir_: Path | None = None) -> list[Path]:
    from ggfiscal.build import anchor_series, gdp_series

    standard = dir_ or config.repo_root() / "data" / "standard"
    standard.mkdir(parents=True, exist_ok=True)
    out = []
    for iso3 in config.COUNTRIES:
        rows = []
        for (classification, line_code), meta in anchor_series(iso3).items():
            for year, value in meta["series"].items():
                rows.append({"iso3": iso3, "classification": classification,
                             "line_code": line_code, "year": int(year),
                             "value_lcu_mn": float(value),
                             "source_id": meta["source_id"],
                             "observation_type": meta.get("per_year", {})
                             .get(int(year), {})
                             .get("observation_type", meta["observation_type"])})
        gdp, gdp_src = gdp_series(iso3)
        for year, value in gdp.items():
            rows.append({"iso3": iso3, "classification": "DENOMINATOR",
                         "line_code": "GDP", "year": int(year),
                         "value_lcu_mn": float(value), "source_id": gdp_src,
                         "observation_type": "anchor_actual"})
        dest = standard / f"anchors_{iso3}.parquet"
        pd.DataFrame(rows).to_parquet(dest, index=False)
        out.append(dest)
    return out
