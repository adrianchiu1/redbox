# DEU per-security register — Bundesrepublik Deutschland – Finanzagentur

Stage D2 build of the German securities register (DEBT_KICKOFF.md §3–§5, §7.1,
§14 DEU) from the `DEU_FINANZAGENTUR` snapshots. Code:
`src/ggfiscal/debt/readers/finanzagentur.py` (readers),
`src/ggfiscal/debt/register_deu.py` (`build`, `reconciliation`),
`tests/debt/test_register_deu.py` (28 tests, all green). All figures below come
from the snapshots in `data/raw/DEU_FINANZAGENTUR/` pulled **2026-09-09**;
`register_deu.build()` runs in ≈ 3 s.

| table | rows | key |
|---|---|---|
| `debt_securities` | **1,654** | ISIN |
| `debt_positions` | **5,348** | ISIN × as-of (31 Dec 1995…2025 + 31 Aug 2026) |
| `debt_flows` | **6,163** | 2,293 `auction`, 27 `syndication`, 2,282 `retention`, 1,561 `redemption` |
| `debt_index_ratios` | **31,102** | 9 linkers × daily, 2006-03-15 … 2026-10-01 |

Everything is EUR millions, `iso3='DEU'`, `source_id='DEU_FINANZAGENTUR'`,
`quality_grade='A'` except the derived redemptions (grade B, §5 below).

---

## 1. The files and their sheet layouts

Every Finanzagentur workbook carries a generation timestamp in row 1, the
department name `Abteilung F-HH` in row 3, and a title block in rows 8–12. All
of them are read with `openpyxl` (`data_only=True`); only `rpgUmlaufvolumen`
needs the non-read-only mode, because its row hierarchy lives in the cell
indentation rather than in the label text.

### 1.1 `einzelaufstellung_seit_1995` — the register backbone
`20260909T231355Z_9ec2c0aa4d07.xlsx`, sha `9ec2c0aa…`, one sheet
**`Wertpapierliste`**, `A1:AJ1599`.

> *Ausstehende Bundeswertpapiere und Kreditmarktmittel* —
> *Nominalwerte in Euro, sortiert nach Wertpapierart und Fälligkeit*

Header row 13; data rows 14–1597; row 1598 is the sheet's own `Summe`.

| col | header | content |
|---|---|---|
| A | `WERTPAPIERART` | security type — **present only on the first row of each block**, forward-filled by the reader |
| B | `ISIN ` (trailing space) | the ISIN; `Zwischensumme` on a block-closing row; `SSD fällig {year}` in the Schuldscheindarlehen block |
| C | `KUPON` | coupon as a German decimal string (`6,500`), blank for pre-1999 paper and bills, `3ME25` for one floater |
| D | `LAUFZEIT AB` | first issue date, `DD.MM.YYYY` |
| E | `FÄLLIGKEIT` | maturity, `DD.MM.YYYY`; blank for the Tagesanleihe |
| F…AJ | `31.12.1995` … `31.12.2025` | nominal outstanding in **whole euro** at each 31 December (31 columns) |

24 `WERTPAPIERART` blocks, 1,560 codes (1,518 ISINs + 42 `SSD fällig …`).
Values are already in euro for the whole history: the office converted the
1995–1998 DEM figures at the irrevocable **1.95583 DEM/EUR** (a 1995 Bobl of
DEM 10 bn shows as `5,112,918,811.96`). **No row in any file is denominated in
DEM**, so `currency='EUR'` throughout except the two `Fremdwährungsanleihen`.

### 1.2 `umlaufende_monatsultimo` — the current month-end list
`…fc4304a65b95.xlsx`, sha `fc4304a6…`, same sheet name and identical column
grammar, `A1:I322`. Four as-of columns: `31.12.2024`, `31.12.2025`,
`30.06.2026`, `31.08.2026`. 287 codes in 24 blocks, of which **148 are strip
blocks** (`30-/15-/10-/7-jährige Kapitalstrips`, `Zinsstrips`) whose nominal
cells are all blank, and one malformed code (`W`, inside a strip block).

**This snapshot carries no Eigenbestand column.** The per-ISIN own-book holding
that the brief expected here does not exist in any Finanzagentur file — see §6.

### 1.3 `emissionshistorie` / `emissionsergebnisse_aktuell` — the auction history
`…82fa5ce6a048.xlsx` (sha `82fa5ce6…`, *Auktionsergebnisse seit 1999*,
`A1:U2342`, 2,320 operations 1999-01-06 … 2026-09-09) and `…10609f8504f5.xlsx`
(sha `10609f85…`, current year, `A1:S167`, 144 operations, all already present
in the history — the reader keys on ISIN + Termin and adds only what is new).

Sheet **`Seite1`**; the header is spread over rows 8–11 and is flattened by
position into `AUKTION_COLUMNS`:

| col | flattened name | header text |
|---|---|---|
| A | `nr` | Nr. |
| B | `termin` | Termin (the bidding day) |
| C | `isin` | ISIN |
| D | `anleihe` | Anleihe¹ — `Bund` 736, `Bubill` 781, `Schatz` 295, `Bobl` 268, `ILB` 172, `Green` 66, `USD-Bond` 2 |
| E | `kupon_frac` | Kupon, **as a fraction** (`0.0375` = 3.75 %) |
| F | `laufzeit` | Laufzeit (maturity date) |
| G | `laufzeitsegment` | Laufzeitsegment (`10 J`, `6 M`) |
| H | `emissionsvolumen_mn` | Emissionsvolumen (Mio. €) |
| I | `typ` | Typ² — `N` Neuemission (662), `A` Aufstockung (1,658) |
| J | `verfahren` | Emissionsverfahren⁶ — `Auk` 1,569, `M-A` 575, `EB` 149, `Syn` 27 |
| K | `bietungen_mn` | Bietungen (Mio. €) |
| L | `kursgebote_mn` | Kursgebote (Mio. €) |
| M | `gebote_ohne_kurs_mn` | Gebote ohne Kurs (Mio. €) |
| N | `zuteilung_mn` | Zuteilungsvolumen (Mio. €) |
| O | `niedrigster_kurs` | Niedrigster akzeptierter Kurs |
| P | `durchschnittskurs` | Gewogener Durchschnittskurs³ |
| Q | `durchschnittsrendite` | Durchschnittsrendite (%)⁴ |
| R | `marktpflegequote_mn` | Marktpflegequote (Mio. €) |
| S | `bid_to_cover` | Bid-to-Cover-Ratio⁵ |
| T | `mpq_anteil` | Anteil MPQ (history only) |
| U | `bid_offer` | Bid / Offer (history only) |

The footnote block below the data spells the codes out (`Auk = Auktion, Syn =
Syndikat, M-A = Multi-ISIN-Auktion`); `EB` is a direct placement into the own
book, where `Zuteilungsvolumen` is blank and `Marktpflegequote` equals the whole
Emissionsvolumen (149 rows).

**Emissionsvolumen = Zuteilung + Marktpflegequote** holds exactly on every row
from 2004 on; it is off by 30–130 mn on **38 rows of 1999–2003** (e.g.
1999-01-13 DE0001114296: 5,000 announced, 4,869 allotted, MPQ 0). Those rows
carry the wedge in `notes`; the register uses the published Emissionsvolumen.

### 1.4 `index_ratios_2005` / `_2015` / `_2025` — Index-Verhältniszahlen
sha `83b2c0cd…`, `79fa4bdc…`, `027687dd…`. One sheet **`Deutsch`** each:

> *Archiv Täglicher Referenzindex und Index-Verhältniszahlen für
> Inflationsindexierte Anleihen und Obligationen des Bundes — lineare
> Interpolation des HVPI der Europäischen Währungsunion (ohne Tabak)*

| row | content |
|---|---|
| 10 | header: B `Datum`, C `Täglicher Referenzindex`, D… `Index-Verhältniszahl {ISIN}` |
| 11 | `Fälligkeit: DD.MM.YYYY` |
| 12 | `Zinsen ab: DD.MM.YYYY` |
| 13 | `Kupon: 0,10%` |
| 14 | `1. Kupon: DD.MM.YYYY` |
| 15 | `Basisindex: 116,035` |
| 16–17 | navigation links |
| 18… | one row per **calendar day** (weekends included) |

| file | linkers | dates | rows |
|---|---|---|---|
| `index_ratios_2005` | 8 | 2006-03-01 … **2016-03-01** | 3,671 |
| `index_ratios_2015` | 9 | **2016-03-01** … **2026-03-01** | 3,670 |
| `index_ratios_2025` | 4 | **2026-03-01** … 2026-09-30 | 232 |

### 1.5 `schuldenbericht` — Umlaufvolumen and Eigenbestand
`…c9127325527a.xlsx`, sha `c9127325…`, nine sheets. Eight repeat the BMF
Datenportal series (read from the ministry's own file by `readers/bmf.py`). The
ninth, **`rpgUmlaufvolumen`** (`A1:NP51`), is unique to this file: row 14
`Datum` then one column per month-end from 31.01.1995, and an indented row tree
with two top-level blocks — `Umlaufvolumen` and `Eigenbestand` (published
**negative**) — each broken down by *instrument group*, never per ISIN.

---

## 2. Column mappings and the parsing regexes

### 2.1 Regexes (all in `register_deu.py` / `readers/finanzagentur.py`)

| name | pattern | use |
|---|---|---|
| `DATE_RE` | `^(\d{2})\.(\d{2})\.(\d{4})$` | every `DD.MM.YYYY` cell (`LAUFZEIT AB`, `FÄLLIGKEIT`, the ratio-file term rows) |
| `COUPON_RE` | `^-?\d{1,3}(?:,\d+)?$` | `KUPON` as a German decimal string → `float(text.replace(",", "."))` |
| `FRN_TERMS_RE` | `^(?P<tenor>\d+)(?P<unit>[MJ])(?P<ref>[A-Z]+)(?P<spread>\d+)$` | the one floating `KUPON`, `3ME25` → 3-month EURIBOR + 25 bp |
| `TENOR_RE` | `^(\d+)(?:-|/)?.*?j(ä\|ae)hrige` | the tenor in a `WERTPAPIERART` label |
| `SEGMENT_RE` | `^(\d+)\s*([JM])$` | auction `Laufzeitsegment` (`10 J`, `6 M`) |
| `ISIN_RE` | `^[A-Z]{2}[A-Z0-9]{9}\d$` | separates ISINs from `SSD fällig 1996` and the stray `W` |
| `RATIO_COL_RE` | `Index-Verh(ä\|ae)ltniszahl\s+([A-Z]{2}[A-Z0-9]{9}\d)` | the per-ISIN ratio columns of the ratio files |
| `TERM_VALUE_RE` | `:\s*(.+)$` | strips the `Basisindex: ` / `Kupon: ` label off the term rows |

There is **no coupon or maturity to parse out of a security's name**: the office
publishes no per-security name at all, only the block label plus the `KUPON` and
`FÄLLIGKEIT` columns. `debt_securities.name` is therefore *composed* — block
label + coupon + maturity, e.g. `10-jährige Bundesanleihen 0.500% 15.02.2025`.

### 2.2 `WERTPAPIERART` → DD2 class (`register_deu.WERTPAPIERART`)

| block label | class | `sub_type` | notes |
|---|---|---|---|
| 30-/10-jährige inflationsindexierte Anleihen des Bundes | `inflation_linked` | `bund_ei` | |
| Inflationsindexierte Obligationen des Bundes | `inflation_linked` | `bobl_ei` | |
| 30-/20-/15-/10-/7-jährige Grüne Bundesanleihen, Grüne Bundesobligationen, Grüne Bundesschatzanweisungen | `fixed_bullet` | `bund_green` | `is_green=True` |
| 30-/20-/15-/10-/7-jährige Bundesanleihen | `fixed_bullet` | `bund` | |
| Bundesobligationen | `fixed_bullet` | `bobl` | |
| Bundesschatzanweisungen | `fixed_bullet` | `schatz` | |
| Unverzinsliche Schatzanweisungen (06M) / (12M) | `bill` | `bubill` | |
| Unverzinsliche Schatzanweisung (Likobank, 2J.) | `other` | `uschatz_likobank_2j` | discount paper, but 2 y at issue, so not a DD2 `bill` |
| Variabel verzinsliche Anleihe | `floating` | `bund_frn` | |
| Fremdwährungsanleihe | `fixed_bullet` | `bund_usd` | `currency='USD'` |
| Bund-Länder-Anleihe (Gesamtemission) | `fixed_bullet` | `bund_laender_gesamtemission` | `issuer_unit='joint:bund_and_laender'` |
| Bundesschatzbriefe Typ A / Typ B | `other` | `bundesschatzbrief_a` / `_b` | non-marketable retail |
| Finanzierungsschätze (1J) / (2J) | `other` | `finanzierungsschatz_1j` / `_2j` | non-marketable retail |
| Tagesanleihe des Bundes | `other` | `tagesanleihe` | no maturity |
| Kapitalstrips, Zinsstrips | — | — | **dropped**: DD1, a strip is not a separate obligation |
| Schuldscheindarlehen des Bundes | — | — | **dropped**: loans, no ISIN |

`sub_type` values follow `config/debt.yaml → sub_types` wherever one fits
(`bund`, `bobl`, `schatz`, `bubill`, `bund_ei`, `bobl_ei`, `bund_green`,
`bund_usd`, `bund_frn`); the six that do not (`uschatz_likobank_2j`,
`bund_laender_gesamtemission`, and the four retail types) name the block. An
unmapped label raises `KeyError` rather than being silently dropped — the same
contract as `aggregates.DEU_LEAVES`.

**Deviation from the brief, deliberate.** The brief's illustrative list puts
"USD bonds" under `other`; `config/debt.yaml` maps `bund_usd: fixed_bullet` and
DD2 defines `fixed_bullet` as fixed coupon + single redemption + no option,
which both `Fremdwährungsanleihen` are. The config wins; the currency and the
office's own euro conversion are recorded on the security.

136 ISINs appear only in the auction history (118 in no listing at all) —
overwhelmingly Bubills issued and redeemed inside one calendar year. They are
classified from the auction `Anleihe` label (`register_deu.ANLEIHE`) and carry
`notes = "terms from the auction history only …"`.

### 2.3 Field-by-field

| `debt_securities` field | source |
|---|---|
| `security_id`, `isin` | column B (ISIN only) |
| `name` | composed, §2.1 |
| `instrument_class`, `sub_type`, `is_green`, `currency`, `issuer_unit` | §2.2 |
| `coupon_pct` | `KUPON`, German comma; fallback `kupon_frac × 100` from the auction history |
| `coupon_frequency` | **1** (German federal bonds pay one annual coupon), 4 for the FRN |
| `day_count` | `ACT/ACT`; `ACT/360` for `bill` |
| `first_issue_date`, `maturity_date` | `LAUFZEIT AB`, `FÄLLIGKEIT` (auction-only ISINs: first `Termin`, `Laufzeit`) |
| `dividend_dates` | derived from the maturity day/month, `'15 Feb'` — the format `interest.parse_dividend_dates` reads |
| `index_reference` / `index_lag_months` | `EA_HICP_XT` / `3` for every linker |
| `base_index` | `Basisindex:` of the **earliest** ratio file listing the ISIN, so it sits on the same HICP base as the earliest `reference_index` stored with its ratios; the other bases are in `notes` |
| `floating_reference`, `spread_bp` | `3ME25` → `EA_MM_3M`, 25 bp |
| `first_call_date` | always null — no callable federal paper in the perimeter |

| `debt_positions` field | source |
|---|---|
| `as_of` | the annual file's 31 columns (`office_annual`) + the monthly file's latest column, 31.08.2026 (`office_snapshot`) |
| `nominal_lcu_mn` | the cell / 1e6 — **Umlauf, gross of the own book** |
| `nominal_uplifted_lcu_mn` | linkers only: nominal × the office index ratio on that exact date |
| `official_holdings_lcu_mn`, `market_hands_lcu_mn` | **null** — see §6 |

| `debt_flows` field | source |
|---|---|
| `flow_type` | `syndication` where `Emissionsverfahren = Syn`, else `auction`; a `retention` twin wherever `Marktpflegequote ≠ 0`; `redemption` derived (§5) |
| `settlement_date`, `operation_date` | both the `Termin` — see §6 |
| `nominal_lcu_mn` | `Emissionsvolumen` (allotted + retained) |
| `cash_lcu_mn` | `Zuteilungsvolumen × Gewogener Durchschnittskurs / 100` where the price is published |
| `price_pct`, `yield_pct` | `Gewogener Durchschnittskurs`, `Durchschnittsrendite` |
| `method` | e.g. `M-A (Multi-ISIN-Auktion); Typ A` |
| `seq` | `cumcount` within (security, settlement_date, flow_type) |

---

## 3. Reconciliation to the aggregate layer

`register_deu.reconciliation(run_id)` returns `stock`, `by_class` and
`issuance`. `stock` compares Σ 31 Dec nominal with the ministry's
`stock_gross_umlauf` (`data/canonical/debt_class_aggregates.csv`, DEU, `mixed /
umlaufvolumen_total`), and Σ nominal net of the office's aggregate Eigenbestand
with Σ `stock_year_end` over the in-register BMF leaves (the Kreditbestand, net
of the own book).

| year | Σ nominal | Umlaufvolumen | ratio | Eigenbestand | Σ market hands | Kreditbestand | ratio | n sec |
|---|---|---|---|---|---|---|---|---|
| 1995 | 370,584 | 505,662 | 0.7329 | 11,530 | 359,054 | 494,113 | 0.7267 | 219 |
| 1996 | 410,450 | 536,903 | 0.7645 | 11,123 | 399,327 | 525,607 | 0.7597 | 219 |
| 1997 | 450,818 | 574,329 | 0.7849 | 12,703 | 438,115 | 561,445 | 0.7803 | 212 |
| 1998 | 500,586 | 608,672 | 0.8224 | 17,780 | 482,806 | 590,706 | 0.8173 | 209 |
| 1999 | 555,589 | 649,968 | 0.8548 | 15,912 | 539,677 | 633,905 | 0.8514 | 198 |
| 2000 | 586,988 | 673,411 | 0.8717 | 16,469 | 570,519 | 656,695 | 0.8688 | 190 |
| 2001 | 627,218 | 702,593 | 0.8927 | 13,907 | 613,310 | 688,288 | 0.8911 | 183 |
| 2002 | 694,703 | 741,977 | 0.9363 | 17,879 | 676,824 | 723,637 | 0.9353 | 182 |
| 2003 | 763,852 | 777,992 | 0.9818 | 13,377 | 750,475 | 764,246 | 0.9820 | 179 |
| 2004 | 829,852 | 830,648 | 0.9990 | 21,090 | 808,763 | 809,202 | 0.9995 | 177 |
| 2005 | 879,181 | 879,798 | 0.9993 | 27,517 | 851,664 | 851,889 | 0.9997 | 182 |
| 2006 | 926,287 | 926,668 | 0.9996 | 42,657 | 883,630 | 883,410 | 1.0002 | 197 |
| 2007 | 941,836 | 942,103 | 0.9997 | 39,880 | 901,956 | 901,482 | 1.0005 | 213 |
| 2008 | 955,943 | 955,965 | 1.0000 | 39,958 | 915,985 | 915,346 | 1.0007 | 230 |
| 2009 | 1,041,530 | 1,041,636 | 0.9999 | 41,869 | 999,661 | 999,086 | 1.0006 | 242 |
| 2010 | 1,091,494 | 1,091,538 | 1.0000 | 44,245 | 1,047,249 | 1,046,881 | 1.0004 | 269 |
| 2011 | 1,104,801 | 1,104,796 | 1.0000 | 46,364 | 1,058,437 | 1,058,031 | 1.0004 | 290 |
| 2012 | 1,125,004 | 1,125,003 | 1.0000 | 41,270 | 1,083,734 | 1,077,575 | 1.0057 | 267 |
| 2013 | 1,144,914 | 1,142,319 | 1.0023 | 46,698 | 1,098,216 | 1,095,596 | 1.0024 | 209 |
| 2014 | 1,148,562 | 1,145,967 | 1.0023 | 49,301 | 1,099,261 | 1,096,659 | 1.0024 | 171 |
| 2015 | 1,138,875 | 1,136,280 | 1.0023 | 48,768 | 1,090,107 | 1,079,898 | 1.0095 | 148 |
| 2016 | 1,134,247 | 1,131,652 | 1.0023 | 52,415 | 1,081,832 | 1,074,825 | 1.0065 | 130 |
| 2017 | 1,133,755 | 1,131,160 | 1.0023 | 58,451 | 1,075,304 | 1,072,745 | 1.0024 | 98 |
| 2018 | 1,121,969 | 1,119,374 | 1.0023 | 61,482 | 1,060,487 | 1,057,934 | 1.0024 | 74 |
| 2019 | 1,133,200 | 1,130,605 | 1.0023 | 63,663 | 1,069,537 | 1,066,988 | 1.0024 | 67 |
| 2020 | 1,443,700 | 1,443,700 | 1.0000 | 182,982 | 1,260,718 | 1,261,309 | 0.9995 | 76 |
| 2021 | 1,589,900 | 1,589,900 | 1.0000 | 162,662 | 1,427,238 | 1,428,234 | 0.9993 | 82 |
| 2022 | 1,707,650 | 1,877,425 | **0.9096** | 202,256 | 1,505,394 | 1,505,331 | 1.0000 | 84 |
| 2023 | 1,841,750 | 1,841,750 | 1.0000 | 206,407 | 1,635,343 | 1,630,972 | 1.0027 | 85 |
| 2024 | **1,882,000** | **1,882,000** | **1.0000** | 201,720 | 1,680,280 | 1,676,949 | 1.0020 | 86 |
| 2025 | 1,970,000 | 1,970,000 | 1.0000 | 196,609 | 1,773,391 | 1,773,391 | 1.0000 | 88 |

Three departures from 1.0000, all identified, none allocated (DD13):

* **1995–2003, ratio 0.73 → 0.98.** The ministry's Umlaufvolumen already
  contains the marketable debt of the federal special funds
  (Erblastentilgungsfonds, Fonds Deutsche Einheit, ERP, Bundeseisenbahnvermögen,
  Entschädigungsfonds, Ausgleichsfonds Steinkohle — all present as `Gliederung
  nach Verwendung` rows of `rpgSchuldenstand`), which the Finanzagentur's
  per-ISIN Einzelaufstellung does not list. The gap closes as those funds were
  absorbed into the federal budget: 135 bn in 1995, 14 bn in 2003, 0.8 bn in
  2004. Treuhand MTNs and Fonds-Deutsche-Einheit securities named in the brief
  therefore have **no per-ISIN source at all**; the pre-2004 years are covered
  only by the aggregate layer.
* **2013–2019, ratio 1.0023, a flat +2,595 mn.** The `Bund-Länder-Anleihe`
  DE000A1X2301: the Finanzagentur lists the *Gesamtemission* of 3,000 mn while
  the ministry counts only the Bund's own 405 mn tranche. The register keeps the
  office's figure and marks the security `issuer_unit='joint:bund_and_laender'`;
  the 2,595 mn Länder share is out of DD1 and a consumer can drop it on that key.
* **2022, ratio 0.9096, −169,775 mn.** Exactly the `wsf_zusatzemission_kredite`
  leaf of the BMF instrument tree (169,775.35 mn): the *Zusatzemissionen des
  Bundes für den WSF nach § 26b StFG* are extra tranches of existing ISINs placed
  directly with the Wirtschaftsstabilisierungsfonds and never enter the Umlauf
  list. Note the Kreditbestand column reconciles at **1.0000** in the same year,
  because the two WSF leaves (`wsf_zusatzemission` −169,775 and
  `…_kredite` +169,775) cancel there.

Market hands vs Kreditbestand reconciles to within **0.6 % from 2004 on**
(worst 1.0095 in 2015, 1.0057 in 2012, everything else ≤ 0.27 %), using the
office's own aggregate Eigenbestand — which is the strongest available check
given that no per-ISIN own-book figure is published.

### 3.2 Issuance

Σ `auction` + `syndication` nominal per settlement year against Σ
`gross_issuance` over the in-register BMF leaves.

| year | n ops | Σ Emissionsvolumen | of which retained | Σ allotted | BMF Bruttokreditaufnahme | volume / official | allotted / official |
|---|---|---|---|---|---|---|---|
| 1999 | 27 | 125,987 | 21,531 | 104,456 | 135,940 | 0.9268 | 0.7684 |
| 2000 | 25 | 130,000 | 28,042 | 101,958 | 134,054 | 0.9698 | 0.7606 |
| 2001 | 18 | 139,000 | 21,104 | 117,896 | 142,380 | 0.9763 | 0.8280 |
| 2002 | 29 | 191,000 | 22,917 | 168,083 | 189,244 | 1.0093 | 0.8882 |
| 2003 | 36 | 220,000 | 30,805 | 189,195 | 225,375 | 0.9762 | 0.8395 |
| 2004 | 34 | 226,000 | 31,443 | 194,557 | 220,166 | 1.0265 | 0.8837 |
| 2005 | 60 | 226,423 | 37,516 | 188,906 | 221,781 | 1.0209 | 0.8518 |
| 2006 | 36 | 234,000 | 45,603 | 188,398 | 222,849 | 1.0500 | 0.8454 |
| 2007 | 36 | 215,000 | 30,632 | 184,368 | 221,470 | 0.9708 | 0.8325 |
| 2008 | 40 | 223,000 | 52,950 | 170,050 | 229,177 | 0.9730 | 0.7420 |
| 2009 | 61 | 336,736 | 71,479 | 265,257 | 337,262 | 0.9984 | 0.7865 |
| 2010 | 73 | 323,000 | 49,868 | 273,132 | 321,686 | 1.0041 | 0.8491 |
| 2011 | 68 | 283,000 | 43,701 | 239,299 | 282,246 | 1.0027 | 0.8478 |
| 2012 | 70 | 264,000 | 49,801 | 214,199 | 263,697 | 1.0012 | 0.8123 |
| 2013 | 72 | 257,000 | 42,813 | 214,187 | 251,947 | 1.0201 | 0.8501 |
| 2014 | 69 | 212,000 | 34,083 | 177,917 | 209,385 | 1.0125 | 0.8497 |
| 2015 | 64 | 186,500 | 33,966 | 152,534 | 179,434 | 1.0394 | 0.8501 |
| 2016 | 72 | 201,000 | 43,287 | 157,713 | 192,967 | 1.0416 | 0.8173 |
| 2017 | 68 | 175,500 | 36,339 | 139,161 | 169,542 | 1.0351 | 0.8208 |
| 2018 | 76 | 179,500 | 34,945 | 144,555 | 176,579 | 1.0165 | 0.8186 |
| 2019 | 80 | 202,200 | 44,666 | 157,534 | 200,150 | 1.0102 | 0.7871 |
| 2020 | 194 | 560,000 | 235,047 | 324,953 | 432,647 | **1.2944** | 0.7511 |
| 2021 | 158 | 495,200 | 94,063 | 401,137 | 511,919 | 0.9673 | 0.7836 |
| 2022 | 182 | 520,750 | 160,795 | 359,955 | 471,762 | 1.1038 | 0.7630 |
| 2023 | 188 | 518,100 | 100,414 | 417,686 | 501,478 | 1.0331 | 0.8329 |
| 2024 | 177 | 439,500 | 74,921 | 364,580 | 417,668 | 1.0523 | 0.8729 |
| 2025 | 163 | 426,000 | 91,483 | 334,517 | 405,806 | 1.0498 | 0.8243 |
| 2026 | 144 | 388,000 | 82,791 | 305,209 | — | — | — |

**The wedge, stated not allocated.** The register measures *nominal at the
operation*; the Datenportal's Bruttokreditaufnahme is a **cash-year** measure of
proceeds, so the two differ by (a) the tranches retained this year and never
sold, which the ministry has not yet borrowed, minus (b) own-book sales of paper
retained in *earlier* years, which the ministry books as borrowing but which the
register has already counted at the original auction, plus (c) agio/disagio,
since the ministry's figure is cash and the register's is nominal.

The median |ratio − 1| is **2.7 %** on the Emissionsvolumen and **17.2 %** on the
allotted-only measure — confirming that the *total issue volume* (allotted +
retained) is the correct nominal counterpart, exactly as §14 DEU says. 2020 is
the extreme case: 235 bn was retained during the pandemic issuance surge against
an Eigenbestand that rose only 119 bn, i.e. roughly half was sold back within the
year and shows up in the ministry's cash figure but not as new register nominal.

The register's own recurrence is exact where it can be checked: for the three
sample Bunds (`DE0001102374`, `DE0001135275`, `DE0001141810`) *and* for the
Bubill with the reversed own-book placement (`DE000BU0E246`), Δposition = Σ flows
to the cent in **every** year 1996–2025 (`test_v30_recurrence_for_sample_bunds`).

---

## 4. Coverage

| class | first / last year with a 31 Dec position | securities | max Σ nominal (mn) |
|---|---|---|---|
| `fixed_bullet` | 1995 – 2025 | 400 | 1,807,750 (2025) |
| `bill` | 1996 – 2025 | 384 | 154,500 (2021) |
| `inflation_linked` | 2006 – 2025 | 9 | 77,150 (2022) |
| `floating` | 1995 – 2003 | 2 | 7,669 (1995) |
| `other` | 1995 – 2018 | 859 | 53,817 (1997) |

| class | `sub_type` | first – last listed | securities listed | in register |
|---|---|---|---|---|
| `bill` | `bubill` | 1996 – 2026 | 263 | 384 |
| `fixed_bullet` | `bund` | 1995 – 2026 | 153 | 153 |
| | `bobl` | 1995 – 2026 | 101 | 101 |
| | `schatz` | 1995 – 2026 | 133 | 133 |
| | `bund_green` | 2020 – 2026 | 10 | 10 |
| | `bund_usd` | 2005 – 2011 | 2 | 2 |
| | `bund_laender_gesamtemission` | 2013 – 2019 | 1 | 1 |
| `floating` | `bund_frn` | 1995 – 2003 | 2 | 2 |
| `inflation_linked` | `bund_ei` | 2006 – 2026 | 7 | 7 |
| | `bobl_ei` | 2007 – 2017 | 2 | 2 |
| `other` | `bundesschatzbrief_a` | 1995 – 2017 | 183 | 183 |
| | `bundesschatzbrief_b` | 1995 – 2018 | 190 | 190 |
| | `finanzierungsschatz_1j` | 1995 – 2012 | 232 | 232 |
| | `finanzierungsschatz_2j` | 1995 – 2013 | 244 | 244 |
| | `uschatz_likobank_2j` | 1995 – 2012 | 9 | 9 |
| | `tagesanleihe` | 2008 – 2018 | 1 | 1 |

(“in register” exceeds “listed” for `bubill` because 121 of them were issued and
redeemed inside a single calendar year and so never reached a 31 December.)

### 4.1 Index ratios

| ISIN | coupon | maturity | ratio dates | rows | `base_index` (2005 / 2015 / 2025 file) |
|---|---|---|---|---|---|
| DE0001030500 | 1.50 % | 2016-04-15 | 2006-03-15 … 2016-04-15 | 3,685 | 100.883 / 86.208 / — |
| DE0001030518 | 2.25 % | 2013-04-15 | 2007-10-26 … 2013-04-15 | 1,999 | 102.529 / 87.615 / — |
| DE0001030526 | 1.75 % | 2020-04-15 | 2009-06-12 … 2020-04-15 | 3,961 | 107.025 / 91.457 / — |
| DE0001030534 | 0.75 % | 2018-04-15 | 2011-04-15 … 2018-04-15 | 2,558 | 110.325 / 94.276 / — |
| DE0001030542 | 0.10 % | 2023-04-15 | 2012-03-23 … 2023-04-15 | 4,041 | 113.236 / 96.764 / — |
| DE0001030559 | 0.50 % | 2030-04-15 | 2014-04-10 … 2026-10-01 | 4,558 | 116.035 / 99.156 / 77.400 |
| DE0001030567 | 0.10 % | 2026-04-15 | 2015-03-12 … 2026-04-15 | 4,053 | 116.343 / 99.419 / 77.605 |
| DE0001030575 | 0.10 % | 2046-04-15 | 2015-04-15 … 2026-10-01 | 4,188 | 115.475 / 98.678 / 77.027 |
| DE0001030583 | 0.10 % | 2033-04-15 | 2021-02-11 … 2026-10-01 | 2,059 | — / 104.475 / 81.552 |

**Rebasing and continuity.** The three files' date ranges are disjoint except
for the rebasing day itself, which both the outgoing and the incoming file
publish. On those two days the **Index-Verhältniszahl is bit-identical** in both
files while the daily reference index rebases:

| seam | linkers | max \|Δ ratio\| | reference index | rebase factor |
|---|---|---|---|---|
| 2016-03-01, `2005 → 2015` | 7 | **0.000 %** | 117.21 → 100.16 | 1.170228 |
| 2026-03-01, `2015 → 2025` | 4 | **0.000 %** | 128.89 → 100.61 | 1.281085 |

`debt_index_ratios` keeps the *newer* file's row on a seam day, so
`reference_index` is always on the base then in force; `base_index` on the
security is the *earliest* base, matching the reference index at the start of
that security's stored series (`base_index × index_ratio = reference_index` at
the first date). `F.index_ratio_seams()` exposes the comparison and
`test_index_ratio_files_are_continuous_across_their_rebasings` asserts it.

---

## 5. Derived rows and their grade

Everything read from a file is grade **A**. The one derived table is
`redemption`: the Finanzagentur publishes no redemption file, so a redemption is
booked at the maturity date for

* the last positive listed nominal before maturity (1,440 securities), or
* Σ issue volumes, for paper that never reached a listed as-of date — almost
  all within-year Bubills (121 securities).

Both are grade **B** with the derivation spelled out in `notes` (DD13: a flow
inferred from a position difference is never grade A). 1,561 redemptions in all —
**every one** of the 1,561 securities matured inside the coverage window.

`retention` flows are grade A — they are the published Marktpflegequote — and
are a *memo leg* of the auction beside them, not a second increment:
`interest.nominal_path` already excludes `retention` from the roll-forward, so
Σ `auction` alone reproduces the position.

One published oddity is carried as-is: **2025-05-13 DE000BU0E246, Emissions-
volumen −500 mn** (`EB`), the reversal of an own-book placement made on
2025-02-14. Both legs are negative; Σ auctions for that ISIN is 13,000 mn, which
is exactly its 31.12.2025 position.

---

## 6. Known gaps

1. **No per-ISIN Eigenbestand exists.** `official_holdings_lcu_mn` and
   `market_hands_lcu_mn` are **null on every row**. The monthly file has no
   Eigenbestand column, and the only own-book figures the Finanzagentur
   publishes — `schuldenbericht → rpgUmlaufvolumen`, block `Eigenbestand` — are
   by *instrument group* and monthly. `register_deu.eigenbestand_year_end()`
   exposes the year-end aggregate, and the reconciliation uses it; allocating it
   pro rata across ISINs would be exactly the kind of construction DD13
   prohibits. Same conclusion for DD11: the `FINANZAGENTUR_OWN` overlay in
   `debt_official_holdings` can only be `security_id='AGG'`,
   `holding_type='aggregate'`.
2. **No Valuta.** The auction sheets publish the bidding day (`Termin`) only, so
   `settlement_date = operation_date = Termin`. German auctions settle T+2, but
   inferring it would move flows across year-ends without an official source.
   Every flow's `notes` says so. It costs nothing in the checks above (no sample
   security has a late-December operation) but it will bias a January/December
   cash-year split for the bill programme.
3. **No flows before 1999.** The auction history starts 1999-01-06; the register
   carries positions from 31.12.1995 but no issuance for 1995–1998 (only
   redemptions, derived). 1996–1998 gross issuance is available at class level
   only (BMF Datenportal, grade B).
4. **90 pre-1999 coupons are missing** — 41 `bund`, 28 `bobl`, 21 `schatz`, all
   with a first issue date 1986–1998, i.e. before the auction history that would
   otherwise fill them. `coupon_pct` is null and their accrued/cash coupon is
   `not_computable` until a PDF-era source is admitted (Q-D7). Bills, the retail
   paper and the Tagesanleihe have no coupon by construction.
5. **Securities without an ISIN are out.** The 42 `SSD fällig {year}` rows
   (Schuldscheindarlehen, 3,895 mn at 31.12.2025) are loans, not securities, and
   are a step-A bridge item. The stray code `W` in the monthly file's
   Kapitalstrips block is dropped with the strips.
6. **DEM.** No file reports DEM. The office publishes the whole 1995–1998
   history in euro at 1.95583; that is recorded in the `notes` of every security
   first issued before 1999 and no conversion is performed here.
7. **Foreign currency.** The two `Fremdwährungsanleihen` carry `currency='USD'`
   with `nominal_lcu_mn` at the office's own euro value (USD 5 bn shows as
   3,968.25 mn EUR, i.e. 1.26 USD/EUR). No rate is published in the file, so
   `fx_rate` and `nominal_issue_ccy_mn` stay null and the conversion is noted on
   the security (§7.9 remains open for them).
8. **The FRN has no fixing.** `DE0001134948` names `3ME25`; `DE0001134781` names
   nothing at all. Neither has a reachable official fixing history, so both are
   DD10 `not_computable`, 5,113 mn at 31.12.1999.
9. **Retail paper is inside the register.** Bundesschatzbriefe,
   Finanzierungsschätze and the Tagesanleihe are `instrument_class='other'`
   here, against DD1, because that is what makes Σ positions reproduce the
   office's own `Summe` row and the ministry's Umlaufvolumen exactly. They are
   listed in `register_deu.NON_MARKETABLE_SUB_TYPES` and every such security
   says so in `notes`; a strict-DD1 consumer filters on `sub_type`. They peak at
   53,817 mn (1997) and are gone by 2019 apart from the Tagesanleihe residual.
10. **Strips are excluded** (DD1) — 148 strip codes in the monthly file, all
    with blank nominals in this snapshot.
