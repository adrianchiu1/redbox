"""§11.7 vintage detection: compare live source metadata against the register
and write reports/vintage_diff.md.

Check paths per source (D-S6-002):
  - IMF_WEO       — diff the live IMF.RES dataflow catalog against the vintage
                    register in config/sources.yaml (IMF_WEO.api.vintages).
                    A NEW edition is registered by adding a config entry and
                    re-running fetch/build/reconcile/report — a config change
                    plus rebuild, never a code change (§11.7). Editions VANISH
                    from the API (D-S0-007), so a vanished edition is expected
                    once superseded: its snapshots are the archive.
  - IMF_GFS       — diff the live IMF.STA catalog against the pinned GFS
                    dataflow versions (structural revisions, not vintages).
  - EUROSTAT_*    — SDMX 2.1 dataflow annotations (UPDATE_DATA,
                    OBS_PERIOD_OVERALL_LATEST) vs the register's
                    last_update_observed / last_observation.
  - ONS_*         — the dataset landing JSON's releaseDate vs the register.
  - hash tier     — every other machine-readable pull (AMECO, EC documents,
                    Steuerschätzung, OECD, and the pulls above too) can be
                    re-downloaded and content-hashed against the latest
                    manifest entry: `detect-vintages --hash`. Off by default
                    (it is a full re-harvest in bandwidth terms).
  - blocked / PDF-only sources are reported as unreachable with their OQ
    reference; no detection is possible until access exists (OQ-5/OQ-6).

The command never mutates config or snapshots: it detects and names the exact
config change + rebuild the finding calls for. Rebuild remains explicit
(fetch → build → reconcile → report) so that registering a vintage stays a
recorded decision, not a side effect.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from pathlib import Path
from xml.etree import ElementTree

from ggfiscal import config
from ggfiscal.ingest import endpoints
from ggfiscal.ingest.store import SnapshotStore

REBUILD = ("register the new vintage in config/sources.yaml, then "
           "`ggfiscal fetch --all && ggfiscal build && ggfiscal reconcile && "
           "ggfiscal report` — config change plus rebuild, no code change "
           "(§11.7); snapshot promptly, the IMF API drops old editions "
           "(D-S0-007)")
REFRESH = ("update the register's verification fields in config/sources.yaml "
           "to the observed values, then re-run `ggfiscal fetch --all` and "
           "the build so the new release is snapshotted (D8)")


@dataclasses.dataclass
class VintageFinding:
    source_id: str
    status: str    # unchanged | new_vintage | vanished | changed | unreachable
    #              # | no_check_path | error
    detail: str
    action: str = ""


# ---------- pure comparison functions (fixture-testable, §11.7) ----------

def weo_catalog_flows(catalog: dict) -> set[tuple[str, str]]:
    """(dataflow id, version) pairs for WEO editions in an IMF.RES catalog
    document (editions appear both as WEO versions and as *_VINTAGE flows)."""
    flows = (catalog.get("data") or {}).get("dataflows") or []
    return {(str(f.get("id")), str(f.get("version"))) for f in flows
            if str(f.get("id", "")) == "WEO"
            or str(f.get("id", "")).startswith("WEO_")}


def diff_weo_catalog(catalog: dict,
                     registered: dict[str, tuple[str, str]] | None = None
                     ) -> list[VintageFinding]:
    """Diff a live (or fixture) IMF.RES catalog against the config register."""
    registered = registered if registered is not None else endpoints.weo_vintages()
    reg_pairs = {tuple(v) for v in registered.values()}
    live = weo_catalog_flows(catalog)
    names = {(str(f.get("id")), str(f.get("version"))): str(f.get("name", ""))
             for f in (catalog.get("data") or {}).get("dataflows") or []}
    out = []
    for flow, version in sorted(live - reg_pairs):
        out.append(VintageFinding(
            "IMF_WEO", "new_vintage",
            f"unregistered WEO edition exposed by the API: {flow}/{version} "
            f"({names.get((flow, version), '?')})", REBUILD))
    for flow, version in sorted(reg_pairs - live):
        label = next(k for k, v in registered.items() if tuple(v) == (flow, version))
        out.append(VintageFinding(
            "IMF_WEO", "vanished",
            f"registered vintage {label} ({flow}/{version}) no longer exposed "
            "by the API — expected once superseded (D-S0-007)",
            "keep the register entry and the D8 snapshots; they are the archive"))
    if not out:
        out.append(VintageFinding(
            "IMF_WEO", "unchanged",
            f"live catalog exposes exactly the {len(reg_pairs)} registered "
            f"editions: {', '.join(sorted(registered))}"))
    return out


def diff_gfs_catalog(catalog: dict) -> list[VintageFinding]:
    """Newer versions of the pinned GFS dataflows (structural revisions)."""
    flows = (catalog.get("data") or {}).get("dataflows") or []
    out = []
    for _, flow_id, pinned in (endpoints.GFS_COFOG_FLOW, endpoints.GFS_SOO_FLOW):
        versions = sorted(str(f.get("version")) for f in flows
                          if str(f.get("id")) == flow_id)
        newer = [v for v in versions
                 if tuple(map(int, v.split("."))) > tuple(map(int, pinned.split(".")))]
        if newer:
            out.append(VintageFinding(
                "IMF_GFS", "changed",
                f"{flow_id}: live versions beyond the pinned {pinned}: "
                f"{', '.join(newer)}",
                "review the new dataflow version (structural revision, not a "
                "vintage) before repointing the pull"))
        else:
            out.append(VintageFinding(
                "IMF_GFS", "unchanged",
                f"{flow_id}: pinned {pinned} is the latest exposed"))
    return out


def eurostat_annotations(xml_text: str) -> dict[str, str]:
    """AnnotationType -> AnnotationTitle from an SDMX 2.1 dataflow document."""
    root = ElementTree.fromstring(xml_text)
    out = {}
    for ann in root.iter():
        if not ann.tag.endswith("}Annotation"):
            continue
        title = ann_type = None
        for child in ann:
            if child.tag.endswith("}AnnotationTitle"):
                title = child.text
            elif child.tag.endswith("}AnnotationType"):
                ann_type = child.text
        if ann_type and title:
            out[ann_type] = title
    return out


def diff_eurostat(source_id: str, xml_text: str) -> VintageFinding:
    ver = config.sources()[source_id].get("verification") or {}
    ann = eurostat_annotations(xml_text)
    update = (ann.get("UPDATE_DATA") or "")[:10]
    latest_obs = ann.get("OBS_PERIOD_OVERALL_LATEST", "")
    recorded = str(ver.get("last_update_observed", "") or "")
    recorded_obs = str(ver.get("last_observation", "") or "")
    if not update:
        return VintageFinding(source_id, "error",
                              "no UPDATE_DATA annotation in dataflow metadata")
    if update != recorded or (recorded_obs and latest_obs != recorded_obs):
        return VintageFinding(
            source_id, "changed",
            f"live UPDATE_DATA {update} (latest observation {latest_obs}) vs "
            f"register {recorded or '—'} ({recorded_obs or '—'})", REFRESH)
    return VintageFinding(source_id, "unchanged",
                          f"UPDATE_DATA {update}, latest observation {latest_obs}")


def diff_ons(source_id: str, meta: dict) -> VintageFinding:
    ver = config.sources()[source_id].get("verification") or {}
    release = str((meta.get("description") or {}).get("releaseDate", ""))[:10]
    recorded = str(ver.get("last_update_observed", "") or "")
    if not release:
        return VintageFinding(source_id, "error",
                              "no description.releaseDate in dataset JSON")
    if release != recorded:
        return VintageFinding(
            source_id, "changed",
            f"live releaseDate {release} vs register {recorded or '—'}", REFRESH)
    return VintageFinding(source_id, "unchanged", f"releaseDate {release}")


# ---------- live checks ----------

# ONS register entries -> dataset slug whose landing JSON carries releaseDate.
# ONS_PSF_INTEREST resolved into the ESA Table 2 file (D-S0-006), so it rides
# that dataset's release metadata.
_ONS_SLUGS = {sid: slug for sid, (slug, _) in endpoints.ONS_FILES.items()}
_ONS_SLUGS["ONS_PSF_INTEREST"] = _ONS_SLUGS["ONS_GG_RECEIPTS"]

_EUROSTAT_DATASETS = {
    "EUROSTAT_GOV10A_EXP": "gov_10a_exp",
    "EUROSTAT_GOV10A_MAIN": "gov_10a_main",
    "EUROSTAT_GOV10A_TAXAG": "gov_10a_taxag",
    "EUROSTAT_NAMA10_GDP": "nama_10_gdp",
}

# machine-readable pulls with no metadata path: content-hash tier only
_HASH_ONLY = ("EC_AMECO", "EC_AGEING_2024", "EC_DSM", "DEU_STEUERSCHAETZUNG",
              "OECD_RS", "OECD_T11", "ONS_GDP")


def eurostat_dataflow_meta_url(dataset: str) -> str:
    return (f"https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/"
            f"dataflow/ESTAT/{dataset}?detail=full")


def _fetch(url: str, accept: str = "", headers: tuple = ()):
    from ggfiscal.ingest.fetch import _get
    return _get(url, accept, headers)


def _check_live(source_id: str) -> list[VintageFinding]:
    from ggfiscal.ingest.fetch import FetchBlocked, FetchError
    try:
        if source_id == "IMF_WEO":
            cat = json.loads(_fetch(
                endpoints.imf_dataflow_catalog_url(),
                "application/vnd.sdmx.structure+json").content)
            return diff_weo_catalog(cat)
        if source_id == "IMF_GFS":
            cat = json.loads(_fetch(
                endpoints.imf_dataflow_catalog_url("IMF.STA"),
                "application/vnd.sdmx.structure+json").content)
            return diff_gfs_catalog(cat)
        if source_id in _EUROSTAT_DATASETS:
            xml_text = _fetch(eurostat_dataflow_meta_url(
                _EUROSTAT_DATASETS[source_id])).text
            return [diff_eurostat(source_id, xml_text)]
        if source_id in _ONS_SLUGS:
            meta = json.loads(_fetch(
                endpoints.ons_dataset_meta_url(_ONS_SLUGS[source_id])).content)
            return [diff_ons(source_id, meta)]
    except (FetchBlocked, FetchError) as e:
        return [VintageFinding(source_id, "unreachable", str(e))]
    return []


def _check_hashes(store: SnapshotStore) -> list[VintageFinding]:
    """Re-download every machine-readable pull and compare content hashes
    against the latest manifest entry (nothing is saved — detection only)."""
    import hashlib

    from ggfiscal.ingest.fetch import FetchBlocked, FetchError

    latest: dict[tuple[str, str], dict] = {}
    for e in store.entries():
        latest[(e["source_id"], e.get("part", ""))] = e
    out = []
    for pull in endpoints.all_stage0_pulls() + endpoints.all_stage3_pulls():
        if (pull.source_id, pull.part) == ("IMF_WEO", "catalog"):
            # the catalog document embeds a per-request prepared timestamp, so
            # its bytes always differ; diff_weo_catalog compares it semantically
            continue
        prev = latest.get((pull.source_id, pull.part))
        try:
            resp = _fetch(pull.url, pull.accept, pull.headers)
        except (FetchBlocked, FetchError) as e:
            out.append(VintageFinding(pull.source_id, "unreachable",
                                      f"{pull.part}: {e}"))
            continue
        sha = hashlib.sha256(resp.content).hexdigest()
        if prev is None:
            out.append(VintageFinding(
                pull.source_id, "changed",
                f"{pull.part}: no prior snapshot in the manifest "
                f"(live sha {sha[:12]})",
                "run `ggfiscal fetch --all` to snapshot it (D8)"))
        elif sha != prev["sha256"]:
            out.append(VintageFinding(
                pull.source_id, "changed",
                f"{pull.part}: content hash {sha[:12]} differs from the "
                f"latest snapshot {prev['sha256'][:12]} "
                f"({prev['retrieved_at']})", REFRESH))
        else:
            out.append(VintageFinding(pull.source_id, "unchanged",
                                      f"{pull.part}: content identical to the "
                                      f"latest snapshot ({prev['retrieved_at']})"))
    return out


def detect(hash_tier: bool = False) -> list[VintageFinding]:
    findings: list[VintageFinding] = []
    checked: set[str] = set()
    for sid in ("IMF_WEO", "IMF_GFS", *_EUROSTAT_DATASETS, *_ONS_SLUGS):
        if sid in checked:
            continue
        checked.add(sid)
        findings += _check_live(sid)
    for sid, src in config.sources().items():
        if sid in checked:
            continue
        ver = src.get("verification") or {}
        status = ver.get("status", "")
        if status == "blocked":
            findings.append(VintageFinding(
                sid, "unreachable",
                "publisher or egress policy blocks every available client "
                "(OQ-6); no vintage check possible until access exists"))
        elif status in ("not_machine_readable", "unverified"):
            findings.append(VintageFinding(
                sid, "no_check_path",
                "PDF-only or unexercised source (§11.4 / OQ-5); vintage "
                "detection needs a machine-readable endpoint"))
        elif sid in _HASH_ONLY:
            if not hash_tier:
                findings.append(VintageFinding(
                    sid, "no_check_path",
                    "no metadata endpoint; content-hash comparison available "
                    "via `ggfiscal detect-vintages --hash`"))
    if hash_tier:
        findings += _check_hashes(SnapshotStore())
    return findings


def write_report(findings: list[VintageFinding],
                 path: Path | None = None, hash_tier: bool = False) -> Path:
    dest = path or config.repo_root() / "reports" / "vintage_diff.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    order = {"new_vintage": 0, "changed": 1, "vanished": 2, "error": 3,
             "unreachable": 4, "no_check_path": 5, "unchanged": 6}
    findings = sorted(findings, key=lambda f: (order.get(f.status, 9), f.source_id))
    n_action = sum(f.status in ("new_vintage", "changed", "error") for f in findings)
    lines = [
        "# vintage_diff.md — §11.7 vintage detection",
        "",
        f"Checked {now} (`ggfiscal detect-vintages"
        + (" --hash" if hash_tier else "") + "`). "
        "Live source metadata vs the register "
        "(`config/sources.yaml`). A new vintage is a **config change plus "
        "rebuild, never a methodology change** (§11.7); WEO editions vanish "
        "from the IMF API, so new editions must be snapshotted promptly "
        "(D-S0-007).",
        "",
        ("**Action needed on "
         f"{n_action} finding(s).**" if n_action else
         "**No new vintages; nothing to re-run.**"),
        "",
        "| source | status | detail | action |",
        "|---|---|---|---|",
    ]
    for f in findings:
        lines.append("| {} | {} | {} | {} |".format(
            f.source_id, f.status,
            f.detail.replace("|", "\\|"), (f.action or "—").replace("|", "\\|")))
    lines += [
        "",
        "Statuses: `new_vintage` (unregistered edition live), `changed` "
        "(release/metadata drifted from the register), `vanished` (registered "
        "edition gone from the API — snapshots are the archive), "
        "`unreachable` (blocked host, OQ-6), `no_check_path` (no metadata "
        "endpoint or PDF-only, OQ-5), `unchanged`.",
        "",
        "Re-run after registering a vintage: `ggfiscal fetch --all && "
        "ggfiscal build && ggfiscal reconcile && ggfiscal report` "
        "(reconciliation re-runs for every registered vintage, §8.5).",
    ]
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest
