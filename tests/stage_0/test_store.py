"""Snapshot store: content-addressing, immutability, manifest integrity (D8)."""

import hashlib
import json

import pytest

from ggfiscal.ingest.store import SnapshotStore


@pytest.fixture()
def store(tmp_path):
    return SnapshotStore(root=tmp_path / "data")


def test_save_layout_and_hash(store):
    content = b"REF_AREA,TIME_PERIOD,OBS_VALUE\nFR,2024,123.4\n"
    snap = store.save("EUROSTAT_GOV10A_EXP", content, url="https://example/x", ext="csv")
    assert snap.sha256 == hashlib.sha256(content).hexdigest()
    assert snap.path.name.endswith(f"_{snap.sha256[:12]}.csv")
    assert snap.path.parent.name == "EUROSTAT_GOV10A_EXP"
    assert snap.path.read_bytes() == content


def test_manifest_appends_full_hash(store):
    store.save("SRC_A", b"one", url="u1", ext="csv")
    store.save("SRC_B", b"two", url="u2", ext="csv", extra={"http_status": 200})
    entries = store.entries()
    assert len(entries) == 2
    assert entries[0]["sha256"] == hashlib.sha256(b"one").hexdigest()
    assert entries[1]["http_status"] == 200


def test_verify_detects_mutation(store):
    snap = store.save("SRC_A", b"immutable", url="u", ext="csv")
    assert store.verify(snap.path, snap.sha256)
    snap.path.write_bytes(b"mutated")
    assert not store.verify(snap.path, snap.sha256)


def test_manifest_is_valid_jsonl(store):
    store.save("SRC_A", b"x", url="u", ext="csv")
    lines = store.manifest.read_text().strip().splitlines()
    for line in lines:
        json.loads(line)
