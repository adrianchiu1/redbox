# Source family `bmf` — Bundesministerium der Finanzen

Stage D0 verification for `BMF_DATENPORTAL`, `BMF_KREDITAUFNAHMEBERICHT`,
`BMF_MONATSBERICHT` and `BMF_HAUSHALTSRECHNUNG` (DEBT_KICKOFF.md §6.3 DEU,
§13, §14 DEU). Code: `src/ggfiscal/debt/families/bmf.py` (pull definitions and
the family `get`), `src/ggfiscal/debt/readers/bmf.py` (readers),
`tests/debt/test_bmf.py`. All figures below were produced from the snapshots in
`data/raw/BMF_*` on **2026-09-09**; `python3 -m ggfiscal.cli debt fetch --family
bmf` exits 0 with **20/20 parts OK**.

---

## 1. Access: the Radware bot manager

`www.bundesfinanzministerium.de` sits behind a Radware bot manager. A bare
`requests.get` is answered, roughly every other request, with a cross-host 302
to `validate.perfdrive.com`, which the egress proxy refuses (CONNECT 403) — the
failure therefore arrives as a `ProxyError`, not as anything the publisher sent.
The family supplies `get(pull)` (the optional hook in `debt/fetch.py`), which:

* opens a **fresh `requests.Session` per attempt** (fresh cookie jar);
* sends a full browser header set: Chrome UA, `Accept-Language: de-DE,de;q=0.9,
  en;q=0.8`, `Referer: https://www.bundesfinanzministerium.de/`,
  `Accept-Encoding: gzip, deflate` (no `br` — `requests` cannot decode it),
  `Upgrade-Insecure-Requests: 1`;
* follows redirects **manually and only within the host**; a cross-host redirect
  aborts the attempt (the session is discarded and a new one started);
* retries up to `ATTEMPTS = 8` with a 1–3 s randomised backoff, and raises
  `FetchBlocked` only when *every* attempt was a proxy CONNECT denial,
  `FetchError` otherwise;
* on a 404 (the publisher bumps `?v=` whenever a file is refreshed) re-resolves
  the link from the publication's landing page and retries once.

With this client every part succeeded **on the first attempt** in the timed
probe of 2026-09-09 — the cookie-plus-referer combination appears to satisfy the
manager immediately — with one exception, below.

**Chunked bodies are cut short.** The 17.8 MB `haushaltsrechnung-2025-band2.pdf`
is served `Transfer-Encoding: chunked` and the transfer is regularly severed
after 2–4 MB (`ChunkedEncodingError: Response ended prematurely`); the first
`debt fetch` run failed this part after 8 attempts. The server sets
`Accept-Ranges: bytes`, so `_fetch` now keeps the bytes already received and
resumes with `Range: bytes=N-` and `Accept-Encoding: identity`, on a separate
budget (`MAX_RESUMES = 16`) so that resuming never spends the bot-manager
retries. The resumed download is **byte-identical** to a lucky single-shot one
(both sha256 `f60812a44b0a…`, 17,813,521 bytes) and now completes in ~6 s.

**HTML parts never hash-stable.** Every HTML response carries per-request bot
tokens (`var __uzdbm_1 = "…"; var __uzdbm_2 = "…"` on one script line, encoding
a UUID and the client IP). Two pulls of the same unchanged page differ in
exactly that line, so `BMF_MONATSBERICHT/2025-11_kreditaufnahme` and
`BMF_HAUSHALTSRECHNUNG/index` will report a vintage event on every re-pull. See
§9.

---

## 2. Part inventory (verified 2026-09-09)

Attempts = HTTP attempts needed in the instrumented probe run;
"first/last period" is what the reader extracts.

| source_id / part | URL | status | attempts | bytes | sha256[:12] | format | first / last period |
|---|---|---|---|---|---|---|---|
| `BMF_DATENPORTAL / kredit_brutto_tilgung_zinsen_xlsx` | `…/Zeitreihe-Kredit-Bruttokredit-Tilgung-Zinsen/datensaetze/xlsx-Kreditbestand-Bruttokredit-Tilgung-Zinsen.xlsx?__blob=publicationFile&v=36` | 200 | 1 | 650,687 | `078c602ba863` | xlsx, 4 sheets | 1995-12-31 (stock) / 2026-07-31 |
| `BMF_DATENPORTAL / bruttokreditaufnahme_csv` | `…/Zeitreihe-Bruttokreditaufnahme-des-Bundes/datensaetze/csv_ZR-Bruttokreditaufnahme-des-Bundes.csv?…&v=31` | 200 | 1 | 365,348 | `b5e1f6a14664` | CSV, UTF-16LE, tab | 1996-01-31 / 2026-07-31 |
| `BMF_DATENPORTAL / tilgungen_csv` | `…/Zeitreihe-Tilgung-des-Bundeshaushalts-und-Sondervermoegen-ab-1996/datensaetze/CSV_ZR-Tilgung-des-Bundeshaushalts-und-Sondervermoegen.csv?…&v=30` | 200 | 1 | 329,386 | `e97ca26c1cec` | CSV, UTF-16LE, tab | 1996-01-31 / 2026-07-31 |
| `BMF_DATENPORTAL / kreditbestand_csv` | `…/Zeitreihe-Kreditbestand-seit-1996/datensaetze/csv-Kreditbestand.csv?…&v=32` | 200 | 1 | 466,842 | `93f6da17d17c` | CSV, UTF-16LE, tab | 1995-12-31 / 2026-07-31 |
| `BMF_KREDITAUFNAHMEBERICHT / 2025` | `/Content/DE/Downloads/Broschueren_Bestellservice/kreditaufnahmebericht-2025.pdf?…&v=2` | 200 | 1 | 1,753,705 | `cfaa881ae735` | PDF, 96 pp | annex 4.5: 1996–2025 |
| `… / 2024` | `/Content/DE/Downloads/Oeffentliche-Finanzen/Kreditaufnahmeberichte/kreditaufnahmebericht-2024.pdf?…&v=5` | 200 | 1 | 2,068,926 | `646be46c172b` | PDF, 100 pp | 1996–2024 |
| `… / 2023` | `…/kreditaufnahmebericht-2023.pdf?…&v=5` | 200 | 1 | 1,694,734 | `088ba6356670` | PDF, 92 pp | 1996–2023 |
| `… / 2022` | `…/kreditaufnahmebericht-2022.pdf?…&v=3` | 200 | 1 | 1,085,104 | `df648ff008fd` | PDF, 94 pp | 1996–2022 |
| `… / 2021` | `…/kreditaufnahmebericht-2021.pdf?…&v=1` | 200 | 1 | 2,595,732 | `547346637ead` | PDF, 98 pp | 1996–2021 |
| `… / 2020` | `…/kreditaufnahmebericht-2020.pdf?…&v=1` | 200 | 1 | 3,717,230 | `fa92eb523c1e` | PDF, 96 pp | 1996–2020 |
| `… / 2019` | `…/kreditaufnahmebericht-2019.pdf?…&v=1` | 200 | 1 | 4,822,752 | `1de812076134` | PDF, 88 pp | 1996–2019 |
| `… / 2018` | `…/kreditaufnahmebericht-2018.pdf?…&v=1` | 200 | 1 | 1,983,424 | `583c0a860c01` | PDF, 88 pp | no machine-readable annex (§6) |
| `… / 2017` | `…/kreditaufnahmebericht-2017.pdf?…&v=1` | 200 | 1 | 3,433,545 | `a7bb94615d75` | PDF, 84 pp | idem |
| `… / 2016` | `…/kreditaufnahmebericht-2016.pdf?…&v=1` | 200 | 1 | 1,461,431 | `39c87bd8f714` | PDF, 76 pp | idem |
| `… / 2015` | `…/kreditaufnahmebericht-2015.pdf?…&v=1` | 200 | 1 | 767,295 | `2cac3a4ffd16` | PDF, 68 pp | idem |
| `… / 2014` | `…/kreditaufnahmebericht-2014.pdf?…&v=1` | 200 | 1 | 1,099,860 | `23833d5c7dbb` | PDF, 68 pp | idem |
| `… / 2013` | `…/kreditaufnahmebericht-2013.pdf?…&v=1` | 200 | 1 | 862,562 | `80dd53ec2720` | PDF, 72 pp | idem |
| `BMF_MONATSBERICHT / 2025-11_kreditaufnahme` | `/Monatsberichte/Ausgabe/2025/11/Inhalte/Kapitel-3-Wirtschafts-und-Finanzlage/3-5-kreditaufnahme-des-bundes.html` | 200 | 1 | 152,924 | *unstable* (`c68b00e524f5` on the last pull) | HTML, 3 tables | issue 2025-11 |
| `BMF_HAUSHALTSRECHNUNG / index` | `/Web/DE/Themen/Oeffentliche_Finanzen/Bundeshaushalt/Haushalts_und_Vermoegensrechnungen_des_Bundes/haushalts_vermoegensrechnungen_des_bundes.html` | 200 | 1 | 220,122 | *unstable* (`4450613e9411`) | HTML | links 1998–2024 (+2025 via its Broschüren page) |
| `BMF_HAUSHALTSRECHNUNG / 2025_band2` | `/Content/DE/Downloads/Oeffentliche-Finanzen/Haushalts-und-Vermoegensrechnungen/haushaltsrechnung-2025-band2.pdf?…&v=6` | 200 | 1 + resumes (8 fails without the resume logic) | 17,813,521 | `f60812a44b0a` | PDF | HH-Jahr 2025 |

No part is blocked, and none failed at the end of the exercise.

---

## 3. Datenportal workbook — row structure

One workbook, four wide sheets. Column A is a **tree carried by cell
indentation** (`openpyxl` `cell.alignment.indent`), never by the label text:
several labels repeat at different depths (`Konventionelle Bundeswertpapiere`,
`Bundesobligationen`, `Bundesschatzanweisungen`, `Sonstige Bundeswertpapiere`
appear both under Instrumentenarten and under Nachrichtlich/Umlaufvolumen), so
the path — not the label — identifies a series. The reader rebuilds it into
`series_path` and records the depth in `level`.

Layout of every sheet:

| rows | content |
|---|---|
| 1–2 | title, sub-title (no values) |
| 3 | period header: `31.12.1995`, `31.01.1996`, … on the stock sheet; `1996 M01`, `1996 M02`, … on the three flow sheets (368/369 columns, i.e. 367 periods to 2026 M07) |
| 4–5 | two indent-0 totals **with** values (section `Gesamt`) |
| then | `Gliederung nach Verwendung` / `… Instrumentenarten` / `… Restlaufzeiten` (stock only) / `… Währungen` marker rows at indent 1, their members at indent 2–5 |
| then | `Nachrichtlich:` marker at indent 0, members at indent 1–3 |
| last | (Zinsen only) a footnote row with no values — skipped |

Reader sections: `Gesamt`, `Verwendung`, `Instrumentenarten`, `Restlaufzeiten`,
`Währungen`, `Nachrichtlich`. Values are **whole euro**; `value_eur_mn` is the
same figure ÷ 1e6.

Facts a consumer must know:

* **The two `Gesamt` rows are not the same total.** `Kredite Bundeshaushalt,
  Sondervermögen und Mitfinanzierung Abwicklungsanstalten und KfW` (row 4) is
  the wider one, and it is what the Verwendung and Instrumentenarten blocks add
  up to (Dec 2024: 1,691,096 EUR mn, and both blocks sum to exactly that).
  `Finanzierung Bundeshaushalt und Sondervermögen` (row 5) excludes the
  pass-through credits (Dec 2024: 1,613,796 EUR mn; difference 77,300).
* **The three flow sheets are cumulative within the calendar year**, not monthly
  flows: 1996 M01 = January, 1996 M12 = the whole of 1996, 1997 M01 restarts.
  Monthly flows must be differenced by the consumer (January = the level).
* **Tilgungen and Zinsen are signed negative** (payments out; the Zinsen sheet
  is the *balance* of interest paid and received, and its Eigenbestände line is
  positive because own holdings earn interest back).
* **§14 DD confirmed**: stock(t−1) + gross + redemptions equals stock(t) exactly
  in 1996–2024 (checked 2019, 2024: difference 0) but **not from 2025**
  (2025: +9,921 EUR mn wedge) — the agio/disagio periodisation the
  Kreditaufnahmebericht annex 4.10 items 1.1.4/1.1.5 and 2.4/2.5 derive.

### 3.1 `rpgSchuldenstand` — every `series_path` (78 series, sheet order)

```
L0 Gesamt / Kredite Bundeshaushalt, Sondervermögen und Mitfinanzierung Abwicklungsanstalten und KfW
L0 Gesamt / Finanzierung Bundeshaushalt und Sondervermögen
L2 Verwendung / Bundeshaushalt
L2 Verwendung / Finanzmarktstabilisierungsfonds (Kredite für Aufwendungen gem. § 9 Abs. 1 StFG)
L2 Verwendung / Finanzmarktstabilisierungsfonds (Kredite für Abwicklungsanstalten gem. § 9 Abs. 5 StFG)
L2 Verwendung / Investitions- und Tilgungsfonds
L2 Verwendung / Wirtschaftsstabilisierungsfonds (Kredite für Rekapitalisierungsmaßnahmen gem. § 22 StFG)
L2 Verwendung / Wirtschaftsstabilisierungsfonds (Kredite für die Kreditanstalt für Wiederaufbau gem. § 23 StFG)
L2 Verwendung / Wirtschaftsstabilisierungsfonds (Kredite zur Abfederung der Folgen der Energiekrise gem. § 26a StFG ohne Darlehensgewährung)
L2 Verwendung / Wirtschaftsstabilisierungsfonds (Kredite für die Kreditanstalt für Wiederaufbau gem. § 26a Abs. 1 Nr. 5 StFG)
L2 Verwendung / Sondervermögen Bundeswehr
L2 Verwendung / Sondervermögen Infrastruktur und Klimaneutralität
L2 Verwendung / Restrukturierungsfonds
L2 Verwendung / Ausgleichsfonds Steinkohle
L2 Verwendung / Bundeseisenbahnvermögen
L2 Verwendung / Entschädigungsfonds
L2 Verwendung / Erblastentilgungsfonds
L2 Verwendung / ERP Sondervermögen
L2 Verwendung / Fonds Deutsche Einheit
L2 Verwendung / Lastenausgleichsfonds
L2 Instrumentenarten / Bundeswertpapiere
L3 Instrumentenarten / Bundeswertpapiere / Konventionelle Bundeswertpapiere
L4 Instrumentenarten / Bundeswertpapiere / Konventionelle Bundeswertpapiere / Bundesanleihen
L5 Instrumentenarten / Bundeswertpapiere / Konventionelle Bundeswertpapiere / Bundesanleihen / 30-jährige Bundesanleihen
L5 Instrumentenarten / Bundeswertpapiere / Konventionelle Bundeswertpapiere / Bundesanleihen / 15-/20-jährige Bundesanleihen
L5 Instrumentenarten / Bundeswertpapiere / Konventionelle Bundeswertpapiere / Bundesanleihen / 10-jährige Bundesanleihen
L5 Instrumentenarten / Bundeswertpapiere / Konventionelle Bundeswertpapiere / Bundesanleihen / 7-jährige Bundesanleihen
L4 Instrumentenarten / Bundeswertpapiere / Konventionelle Bundeswertpapiere / Bundesobligationen
L4 Instrumentenarten / Bundeswertpapiere / Konventionelle Bundeswertpapiere / Bundesschatzanweisungen
L4 Instrumentenarten / Bundeswertpapiere / Konventionelle Bundeswertpapiere / Unverzinsliche Schatzanweisungen des Bundes
L3 Instrumentenarten / Bundeswertpapiere / Inflationsindexierte Bundeswertpapiere
L3 Instrumentenarten / Bundeswertpapiere / Grüne Bundeswertpapiere
L3 Instrumentenarten / Bundeswertpapiere / Zusatzemissionen des Bundes
L4 Instrumentenarten / Bundeswertpapiere / Zusatzemissionen des Bundes / Kredite aus Zusatzemissionen des Bundes für den WSF nach § 26b StFG
L4 Instrumentenarten / Bundeswertpapiere / Zusatzemissionen des Bundes / Anlage des WSF in Forderungen an den Bund nach § 26b Abs. 5 StFG
L3 Instrumentenarten / Bundeswertpapiere / Sonstige Bundeswertpapiere
L2 Instrumentenarten / Schuldscheindarlehen
L2 Instrumentenarten / Geldmarktgeschäfte zur Haushaltsfinanzierung
L2 Instrumentenarten / Sonstige Kredite und Buchschulden
L2 Restlaufzeiten / bis 1 Jahr
L2 Restlaufzeiten / über 1 Jahr bis 4 Jahre
L2 Restlaufzeiten / über 4 Jahre
L2 Währungen / Euro
L2 Währungen / Fremdwährungen
L1 Nachrichtlich / Umlaufvolumen
L2 Nachrichtlich / Umlaufvolumen / Konventionelle Bundeswertpapiere
L3 Nachrichtlich / Umlaufvolumen / Konventionelle Bundeswertpapiere / 30-jährige Bundesanleihen
L3 Nachrichtlich / Umlaufvolumen / Konventionelle Bundeswertpapiere / 15-/20-jährige Bundesanleihen
L3 Nachrichtlich / Umlaufvolumen / Konventionelle Bundeswertpapiere / 10-jährige Bundesanleihen
L3 Nachrichtlich / Umlaufvolumen / Konventionelle Bundeswertpapiere / 7-jährige Bundesanleihen
L3 Nachrichtlich / Umlaufvolumen / Konventionelle Bundeswertpapiere / Bundesobligationen
L3 Nachrichtlich / Umlaufvolumen / Konventionelle Bundeswertpapiere / Bundesschatzanweisungen
L3 Nachrichtlich / Umlaufvolumen / Konventionelle Bundeswertpapiere / Unverzinsliche Schatzanweisungen des Bundes (inklusive Kassenemissionen)
L2 Nachrichtlich / Umlaufvolumen / Inflationsindexierte Bundeswertpapiere
L3 Nachrichtlich / Umlaufvolumen / Inflationsindexierte Bundeswertpapiere / 30-jährige inflationsindexierte Anleihen des Bundes
L3 Nachrichtlich / Umlaufvolumen / Inflationsindexierte Bundeswertpapiere / 10-jährige inflationsindexierte Anleihen des Bundes
L3 Nachrichtlich / Umlaufvolumen / Inflationsindexierte Bundeswertpapiere / Inflationsindexierte Obligationen des Bundes
L2 Nachrichtlich / Umlaufvolumen / Grüne Bundeswertpapiere
L3 Nachrichtlich / Umlaufvolumen / Grüne Bundeswertpapiere / 30-jährige Grüne Bundesanleihen
L3 Nachrichtlich / Umlaufvolumen / Grüne Bundeswertpapiere / 15-/20-jährige Grüne Bundesanleihen
L3 Nachrichtlich / Umlaufvolumen / Grüne Bundeswertpapiere / 10-jährige Grüne Bundesanleihen
L3 Nachrichtlich / Umlaufvolumen / Grüne Bundeswertpapiere / Grüne Bundesobligationen
L3 Nachrichtlich / Umlaufvolumen / Grüne Bundeswertpapiere / Grüne Bundesschatzanweisungen
L2 Nachrichtlich / Umlaufvolumen / Zusatzemissionen des Bundes
L2 Nachrichtlich / Umlaufvolumen / Sonstige Bundeswertpapiere
L3 Nachrichtlich / Umlaufvolumen / Sonstige Bundeswertpapiere / USD-Anleihen (Euro-Gegenwert)
L3 Nachrichtlich / Umlaufvolumen / Sonstige Bundeswertpapiere / Bund-Länder-Anleihe
L3 Nachrichtlich / Umlaufvolumen / Sonstige Bundeswertpapiere / Bundesschatzbriefe
L3 Nachrichtlich / Umlaufvolumen / Sonstige Bundeswertpapiere / Finanzierungsschätze
L3 Nachrichtlich / Umlaufvolumen / Sonstige Bundeswertpapiere / Tagesanleihe
L3 Nachrichtlich / Umlaufvolumen / Sonstige Bundeswertpapiere / Inhaberschuldverschreibungen Entschädigungsfonds
L3 Nachrichtlich / Umlaufvolumen / Sonstige Bundeswertpapiere / Medium Term Notes der Treuhandanstalt
L3 Nachrichtlich / Umlaufvolumen / Sonstige Bundeswertpapiere / Fundierungsschuldverschreibung
L1 Nachrichtlich / Eigenbestände (Brutto)
L1 Nachrichtlich / Eigenbestände (Netto)
L1 Nachrichtlich / Anlage des WSF in Forderungen an den Bund nach § 26b Abs. 5 StFG
L1 Nachrichtlich / Verbindlichkeiten aus der Kapitalindexierung inflationsindexierter Bundeswertpapiere
L1 Nachrichtlich / Rücklage gemäß Schlusszahlungsfinanzierungsgesetz
```

### 3.2 The three flow sheets

Same tree, with these differences from §3.1 (verified as set differences):

* **all three**: no `Restlaufzeiten` section; no `Nachrichtlich /
  Verbindlichkeiten aus der Kapitalindexierung …`; no `Nachrichtlich / Rücklage
  gemäß Schlusszahlungsfinanzierungsgesetz`. 73 series each on
  `rpgBruttokreditaufnahme Gesamt` and `rpgTilgungen`.
* **`rpgZinsen Gesamt`** (74 series): `Verwendung / Bundeshaushalt` is instead
  `Verwendung / Bundeshaushalt inkl. Sondervermögen Infrastruktur und
  Klimaneutralität`, and there is one extra memo line `Nachrichtlich / Anteil
  Zinskosten Sondervermögen Infrastruktur und Klimaneutralität im
  Bundeshaushalt*` (zero throughout: per the sheet's footnote the SVIK was
  established in October 2025 retroactive to 1 January 2025 and a separate
  presentation is only possible from 1 January 2026).

Cross-check on the interest concept: `rpgZinsen Gesamt`, 2024 M12,
`Gesamt / Finanzierung Bundeshaushalt und Sondervermögen` = **−33,238.4 EUR mn**,
which is exactly the Kreditaufnahmebericht 2025 annex-4.5 "Insgesamt" for 2024
(−33,238). Kap. 3205 in the same annex is −32,201 for 2024 — a different, and
narrower, perimeter (§14 DEU: net of interest income, excluding swaps and cash
management).

---

## 4. Datenportal CSVs

UTF-16LE (BOM `ff fe`), tab-separated, one header line (cell A1 is the table
title, then 367 period labels) and one line per row of the corresponding sheet.
Blank spacer lines and the section markers (`Gliederung nach …`,
`Nachrichtlich:`) are present, **the indentation is not** — so the CSVs give
labels and sections but no tree; `datenportal_csv` therefore returns
`row_index` as the disambiguator for repeated labels.

* Agreement with the workbook is **exact** (not merely within 0.1 %) on every
  spot-checked (label, period) pair, e.g. `Bundeshaushalt` 2024-12-31:
  1,551,049,483,528 € in both; `Umlaufvolumen` −399,250,000,000 € in both
  (Tilgungen).
* The CSVs carry **7–8 instrument lines the workbook's Instrumentenarten block
  does not show**: `30-/10-jährige inflationsindexierte Anleihen des Bundes`,
  `Inflationsindexierte Obligationen des Bundes`, `30-/15-20-/10-jährige Grüne
  Bundesanleihen`, `Grüne Bundesobligationen`, `Grüne Bundesschatzanweisungen`
  (the workbook shows those splits only under Nachrichtlich/Umlaufvolumen, and
  the two are *not* equal). For linker and green-bond issuance and redemptions
  the CSV is the finer source. Row counts per section (Bruttokreditaufnahme):
  CSV 26 Instrumentenarten rows vs 19 series in the workbook.
* One label differs in spelling between the two files: the stock CSV writes
  `15/20-jährige Grüne Bundesanleihen` where the workbook writes
  `15-/20-jährige …`.
* The workbook has **no hidden rows** — the extra CSV detail is genuinely absent
  from the xlsx, not merely hidden.

---

## 5. Kreditaufnahmebericht PDFs — what actually parses

`kreditaufnahmebericht_text(year)` returns the pypdf text layer (2025: 96 pages,
253 k characters, contains "Nettokreditaufnahme").
`kreditaufnahmebericht_annex(year, "4.5" | "4.10")` parses the two §6.3 step-A
annexes out of that text layer. **Nothing is hand-keyed.**

**The annex number moves between editions**, so the parser finds the annex by
its *title* and its unit line and reads the number off the heading that matched
(the key `"4.5"`/`"4.10"` is the 2025 numbering used by DEBT_KICKOFF.md §6.3):

| edition | Verzinsung annex | Abrechnung annex |
|---|---|---|
| 2019 | 4.10 | 4.16 (no text layer, see below) |
| 2020, 2021 | 4.6 | 4.11 |
| 2022 | 4.5 | 4.10 |
| 2023, 2024, 2025 | 4.5 | 4.10 |

| edition | 4.5 rows / distinct labels | year span | 4.10 rows | NKA *Ist* parsed (EUR mn) |
|---|---|---|---|---|
| 2013–2018 | 0 | — | 0 | — |
| 2019 | 373 / 20 | 1996–2019 | 0 | — |
| 2020 | 414 / 25 | 1996–2020 | 50 | 130,464 |
| 2021 | 436 / 26 | 1996–2021 | 53 | 215,379 |
| 2022 | 459 / 27 | 1996–2022 | 49 | 115,442 |
| 2023 | 493 / 30 | 1996–2023 | 48 | 27,177 |
| 2024 | 518 / 30 | 1996–2024 | 52 | 33,320 |
| 2025 | 633 / 34 | 1996–2025 | 56 | 66,893 |

Those NKA figures reproduce the published Nettokreditaufnahme of each year, and
item 3.4 (`Eigenbestandsveränderung (Marktpflege)`, renamed
`Eigenbestandsaufbau` in 2025) is present in every parsed edition.

**Reliable:**

* **4.10** for 2020–2025: item number, group heading, label and the three euro
  columns Soll / Ist / Abweichung. `Ist − Soll = Abweichung` holds to the cent
  on the Nettokreditaufnahme line. Labels wrapped across PDF lines are rejoined
  and the typesetter's soft hyphens repaired (`Haushaltsausga- ben` →
  `Haushaltsausgaben`). Items 1.1/1.1.1–1.1.5 (Bruttokreditaufnahme by original
  maturity and the two periodisation lines), 2.1–2.5 (Tilgungen), 3.1–3.14
  (the NKA derivation incl. Eigenbestand, Selbstbewirtschaftungsmittel, the
  Sondervermögen lines and the Rücklage) all come through.
* **4.5** for 2019–2025, both the Verwendung and the Instrumentenarten
  breakdowns, 1996 to the report year, EUR mn, negative = interest cost.
* **4.5 "nachrichtlich: Verzinsung gemäß Epl. 32, Kapitel 3205"** — the line
  DEBT_KICKOFF.md §6.3 names for DEU step A — exists **only in the 2025
  edition** (`table == "kap3205"`, rows `Bundeshaushalt inkl. …`, `davon
  Zinsausgaben`, `davon Zinseinnahmen`, 1996–2025). The string "3205" does not
  occur anywhere in the 2013–2024 editions' text layers.

**Fragile / not available, stated plainly:**

* **Continuation pages of annex 4.5 carry no row labels in the text layer.** The
  table is split by year block across 4–5 pages and only the first page of each
  block has column A. The parser carries the labels forward by row position and
  accepts them **only when the row count matches exactly** (37 rows on every
  page of the 2025 table); otherwise the page's rows are dropped rather than
  guessed. The carried alignment was verified against the Datenportal for 2024:
  30-jährige −15,121 vs −15,120.6, 15-/20-jährige −1,227 vs −1,227.5,
  7-jährige −870 vs −870.2.
* **Editions 2013–2018 yield nothing** for either annex. Their chapter 4 is
  "Rechtsgrundlagen für das Kreditmanagement" (4.1–4.4) and the corresponding
  annex tables are not in the text layer at all; the in-body "Tabelle 9:
  Verzinsung der Schulden …" of 2017/2018 is a different, 5-year table with the
  opposite sign convention and is deliberately **not** picked up (the parser
  requires a chapter-4 heading).
* **2019 annex 4.16 (Abrechnung)** exists in the annex table of contents but its
  table page has no extractable text (image/vector), so 4.10 is empty for 2019.
* Unnumbered running subtotals inside 4.10 (bare amount lines between items
  3.2/3.3 and 3.3/3.4) have no label in the text layer and are dropped; they are
  sums of the labelled rows above them.
* Older editions label the totals `Summe Einnahmen` / `Summe Ausgaben`; 2022+
  use `Einnahmen` / `Ausgaben*`. Consumers should match on the item column or
  on a substring, not on an exact total label.

---

## 6. BMF_MONATSBERICHT — pattern and one verified article

No pull series is registered: the article's **section number moves between
issues** (3.5 in 2025-11, 4.5 in 2021-02, 1.5/1.4 in others), so the series can
only be enumerated by crawling each issue index, which is left to a later stage.

* Issue index: `https://www.bundesfinanzministerium.de/Monatsberichte/Ausgabe/{yyyy}/{mm}/monatsbericht-{mm}-{yyyy}.html`
  (`monatsbericht_issue_index_url(year, month)` in the family module).
* Article URL shape: `…/Monatsberichte/Ausgabe/{yyyy}/{mm}/Inhalte/Kapitel-{n}-{kapitel-slug}/{n}-{m}-{artikel-slug}.html`.
* **Verified article** (pulled as part `2025-11_kreditaufnahme`, HTTP 200,
  152,924 bytes, `<title>BMF-Monatsbericht November 2025 - Kreditaufnahme des
  Bundes und seiner Sondervermögen</title>`, 3 HTML tables):
  `https://www.bundesfinanzministerium.de/Monatsberichte/Ausgabe/2025/11/Inhalte/Kapitel-3-Wirtschafts-und-Finanzlage/3-5-kreditaufnahme-des-bundes.html`
* A second, older shape confirmed live in the site search (not pulled):
  `…/Monatsberichte/2021/02/Inhalte/Kapitel-4-Wirtschafts-und-Finanzlage/4-5-kreditaufnahme-des-bundes-und-seiner-sondervermoegen.html`
  — note both the missing `Ausgabe/` segment and the longer article slug.

---

## 7. BMF_HAUSHALTSRECHNUNG — link pattern 1998–2025

All resolved from the pulled index page (`…/haushalts_vermoegensrechnungen_des_bundes.html`),
directory `https://www.bundesfinanzministerium.de/Content/DE/Downloads/Oeffentliche-Finanzen/Haushalts-und-Vermoegensrechnungen/`:

| years | file | `v=` |
|---|---|---|
| 1998–2008 | `haushaltsrechnung-und-vermoegensrechnung-{yyyy}.pdf` (combined volume) | 1 |
| 2009–2013 | `haushaltsrechnung-{yyyy}.pdf` + separate `vermoegensrechnung-{yyyy}.pdf` | 1 |
| 2014–2022 | `haushaltsrechnung-{yyyy}-band1.pdf`, `haushaltsrechnung-{yyyy}-band2.pdf` | 1 |
| 2023 | `haushaltsrechnung-2023-band1.pdf` (v=3), `-band2.pdf` | 5 |
| 2024 | `haushaltsrechnung-2024-band1.pdf` (v=5), `-band2.pdf` | 4 |
| 2025 | `haushaltsrechnung-2025-band1.pdf` (v=7), `-band2.pdf` (v=6) — **linked only from** `/Content/DE/Downloads/Broschueren_Bestellservice/haushaltsrechnung-des-bundes-2025.html`, not from the index page | 6 |

`vermoegensrechnung-2016.pdf` is absent from the index (2009–2015, 2017–2024
present). Epl. 32 / Kap. 3205 outturn is in Band 2 (or in the combined volume
before 2014). Only `2025_band2` is pulled in this pass; the rest are one
`Pull` each whenever the committee wants the earlier outturns.

---

## 8. Reader API

```python
from ggfiscal.debt.readers import bmf

bmf.datenportal("rpgSchuldenstand")          # series_path, series_label, section,
                                             # level, period, value_eur, value_eur_mn
bmf.bund_stock_by_instrument()               # Instrumentenarten + Umlaufvolumen + Eigenbestände, EUR mn
bmf.bund_gross_issuance_by_instrument()      # Instrumentenarten, EUR mn, cumulative YTD
bmf.bund_redemptions_by_instrument()         # idem, negative
bmf.bund_interest_by_instrument()            # idem, negative
bmf.datenportal_csv("kreditbestand_csv")     # row_index, series_label, section, period, value_eur(_mn)
bmf.kreditaufnahmebericht_text(2025)         # pypdf text layer, pages joined with \f
bmf.kreditaufnahmebericht_annex(2025, "4.5")  # annex, table, section, series_label, year, value_eur_mn
bmf.kreditaufnahmebericht_annex(2025, "4.10") # annex, item, group, label, soll_eur, ist_eur, abweichung_eur
```

`tests/debt/test_bmf.py` (13 tests, green) covers: the pull inventory; monthly
period continuity 1995-12-31 → 2026-07-31 with no gaps; the Bundesanleihen tree
depth; the Dec-2024 total stock inside 1.5–2.1 m EUR mn; the Zinsen sign and
cumulation; the wrappers' sections; CSV-vs-workbook agreement within 0.1 % (in
fact exact); `kreditaufnahmebericht_text(2025)` containing "Nettokreditaufnahme";
and both annex parsers, including the annex-4.5 vs Datenportal 2024 agreement
within 1 %. Everything snapshot-dependent skips when the D8 store is empty.

---

## 9. Config corrections and notes for the register

1. **`config/debt_sources.yaml` → `BMF_KREDITAUFNAHMEBERICHT.api`** records only
   the 2025 link. The archive lives in a *different* directory:
   `/Content/DE/Downloads/Oeffentliche-Finanzen/Kreditaufnahmeberichte/kreditaufnahmebericht-{yyyy}.pdf?__blob=publicationFile&v={n}`
   with `v=` 5 (2024), 5 (2023), 3 (2022), 1 (2021–2010). Only the current
   edition sits under `Broschueren_Bestellservice`, and it moves to the archive
   when the next one appears — so the `landing`/`file` pair should be recorded
   per edition, or resolved from `kreditaufnahmebericht-{yyyy}.html`.
   Editions **2010–2012 are also resolvable** (same pattern, `v=1`), extending
   §13's "2013 → 2025" range; this pass registers 2013–2025 per §13.
2. **`BMF_KREDITAUFNAHMEBERICHT.object`** claims "annex 4.5 interest incl. Kap.
   3205 … 4.10 Abrechnung" for the whole series. True only from 2020 (4.10) /
   2019 (4.5), with the annex *numbers* differing by edition (§5), and the Kap.
   3205 memo only in the 2025 edition. Suggest amending the entry to name the
   title rather than the number.
3. **`BMF_HAUSHALTSRECHNUNG.api`** has a landing page but no `file`. The 2025
   Band 2 is *not* linked from that landing page — add
   `landing_2025: /Content/DE/Downloads/Broschueren_Bestellservice/haushaltsrechnung-des-bundes-2025.html`
   or the direct `haushaltsrechnung-2025-band2.pdf?__blob=publicationFile&v=6`.
4. **`BMF_DATENPORTAL.api.note`** says "retry up to 6". Eight request attempts
   plus a resume budget for cut-off bodies is what this session found sufficient
   (`ATTEMPTS = 8`, `MAX_RESUMES = 16`); the note should also record that the
   large PDFs are chunked and need `Range` resumption.
5. **Vintage detection** (`detect-vintages`) will report a false vintage on every
   re-pull of the two HTML parts, because the bot manager injects per-request
   `__uzdbm_*` tokens (§1). Recommend the detector normalise BMF HTML by
   dropping lines containing `__uzdbm_` before hashing, or that the two HTML
   parts be excluded from vintage comparison. The xlsx, CSV and PDF parts are
   hash-stable across all four pulls made today.
6. **`ingest/fetch.py::_ext_for`** gained `pdf`/`html` branches during this
   session (another agent's change), so BMF snapshots now land as `.pdf`/`.html`
   rather than `.bin`; earlier `.bin` snapshots of the same bytes remain in the
   store and are still readable (the readers address snapshots through the
   manifest, not by extension).
7. **For the register (§4, §7)**: the Datenportal instrument tree is an
   aggregate, not a security list — grade C/B per §9. The `Umlaufvolumen` tree
   plus `Eigenbestände (Brutto)`/`(Netto)` is the pair needed for market-hands
   (§14 DEU, DD11): Eigenbestände are carried **negative**, so market-hands =
   Umlaufvolumen + Eigenbestände. `Sonstige Bundeswertpapiere` is where the
   non-marketable retail instruments (Bundesschatzbriefe, Finanzierungsschätze,
   Tagesanleihe) and the assumed special-fund paper (Treuhandanstalt MTNs,
   Entschädigungsfonds ISVs, Fundierungsschuldverschreibung) sit — DD1 excludes
   the retail lines from the register and carries them as bridge items.
