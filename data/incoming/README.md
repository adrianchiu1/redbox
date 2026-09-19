Transfer folder for files the two bot-challenged debt offices (DMO, AFT; OQ-8)
will not hand to a headless client. `tools/harvest_offices_local.py` fills it on
a desktop as `{SOURCE_ID}/{part}.{ext}` (parts as in DOWNLOAD_LIST.md); commit
and push it, then run `ggfiscal debt ingest-incoming` on the build box. The
snapshots that command writes under data/raw/ are the record (D-S7-001); the
files here are only the carrier and may be deleted once ingested. Stub bodies
("Unable to fulfil the report request") and challenge pages are refused.
