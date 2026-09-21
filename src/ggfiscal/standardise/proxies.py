"""Secondary-national Level II proxies (REPLICATION_KICKOFF.md D26; Stage
U0, D-S16-007).

A country whose anchor family publishes no COFOG Level II table names, in
`countries.yaml`, the secondary national table that serves its Level II
lines (`level2_source: BEA_NIPA_T316` for the USA: NIPA Table 3.16
sub-functions via `standardise.readers_bea`). This registry maps that id
to the register source_id, the lines.yaml cell key of the line's cells and
the reader; the build and the coverage matrix ask here, so no site names a
country. A `level2_source` with no entry raises — never a fall-through.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from ggfiscal import config
from ggfiscal.standardise import readers_bea

# level2_source (countries.yaml) -> (register source_id, lines.yaml cell key,
# reader(line_code, cell spec) -> (series, concept note))
LEVEL2_PROXY_READERS: dict[str, tuple[str, str, Callable[[str, dict], tuple[pd.Series, str]]]] = {
    "BEA_NIPA_T316": ("BEA_NIPA", "bea_nipa", readers_bea.level2_proxy),
}

CONCEPT_FLAG = "level2_bea_function"   # kickoff §5: new concept_flag value


def level2_proxy(iso3: str, line_code: str, meta: dict) -> tuple[pd.Series, str, str] | None:
    """(series, source_id, concept note) of the D26 proxy of one COFOG Level
    II line, or None where the country names no `level2_source` or the line
    has no cell for it. `meta` is the line's level2_splits meta (carries the
    cell keys)."""
    src = config.level2_source(iso3)
    if not src:
        return None
    if src not in LEVEL2_PROXY_READERS:
        raise LookupError(f"{iso3}: level2_source {src!r} has no reader in "
                          f"standardise.proxies.LEVEL2_PROXY_READERS "
                          f"({', '.join(LEVEL2_PROXY_READERS)})")
    source_id, cell_key, reader = LEVEL2_PROXY_READERS[src]
    spec = meta.get(cell_key)
    if not spec:
        return None
    series, note = reader(line_code, spec)
    return series, source_id, note
