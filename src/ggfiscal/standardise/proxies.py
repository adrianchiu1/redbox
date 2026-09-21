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

from typing import Callable, NamedTuple

import pandas as pd

from ggfiscal import config
from ggfiscal.standardise import readers_bea


class Level2Proxy(NamedTuple):
    """One `level2_source` id's routing: where the cells come from, which
    lines.yaml key holds them, which reader reads them, and the §11.5
    crosswalk that documents the mapping (Stage U1, D-S17-005)."""
    source_id: str      # register source_id of the secondary national table
    cell_key: str       # lines.yaml key holding a line's cells for it
    reader: Callable[[str, dict], tuple[pd.Series, str]]
    crosswalk: str      # crosswalks/<stem>.csv documenting the mapping


# level2_source (countries.yaml) -> Level2Proxy
LEVEL2_PROXY_READERS: dict[str, Level2Proxy] = {
    "BEA_NIPA_T316": Level2Proxy("BEA_NIPA", "bea_nipa", readers_bea.level2_proxy,
                                 "BEA_NIPA_to_COFOG"),
}

CONCEPT_FLAG = "level2_bea_function"   # kickoff §5: new concept_flag value


def level2_routing(iso3: str) -> Level2Proxy | None:
    """The country's D26 Level II routing, or None where it names no
    `level2_source` (its anchor family publishes Level II itself). A
    `level2_source` with no entry raises — never a fall-through."""
    src = config.level2_source(iso3)
    if not src:
        return None
    if src not in LEVEL2_PROXY_READERS:
        raise LookupError(f"{iso3}: level2_source {src!r} has no reader in "
                          f"standardise.proxies.LEVEL2_PROXY_READERS "
                          f"({', '.join(LEVEL2_PROXY_READERS)})")
    return LEVEL2_PROXY_READERS[src]


def level2_crosswalk_stamp(iso3: str) -> str | None:
    """`<crosswalk stem>:<version>` for the country's D26 Level II rows —
    what their `crosswalk_version` column carries (D-S17-005) — or None
    where the country names no `level2_source`."""
    routing = level2_routing(iso3)
    if routing is None:
        return None
    return f"{routing.crosswalk}:{config.crosswalk_version(routing.crosswalk)}"


def level2_proxy(iso3: str, line_code: str, meta: dict) -> tuple[pd.Series, str, str] | None:
    """(series, source_id, concept note) of the D26 proxy of one COFOG Level
    II line, or None where the country names no `level2_source` or the line
    has no cell for it. `meta` is the line's level2_splits meta (carries the
    cell keys)."""
    routing = level2_routing(iso3)
    if routing is None:
        return None
    spec = meta.get(routing.cell_key)
    if not spec:
        return None
    series, note = routing.reader(line_code, spec)
    return series, routing.source_id, note
