# Cyclically adjusted equivalents of the 66 line series — availability check

Status date: 2026-09-10. Question put by the committee: **is the data this
repo stitches — GG expenditure by COFOG function and revenue by ESA type —
available in cyclically adjusted form from any official source, for GBR, FRA
and DEU?**

Machine-readable evidence: `reports/cyclical_adjustment_availability.csv`
(56 rows, one per source × series × country, with measured spans). Every span
in this report was pulled live on 2026-09-10 and measured programmatically,
not read off documentation — same standard as `source_verification.md`.

---

## Answer

**No, for expenditure. Partially, for revenue. Neither at the granularity
this repo publishes.**

| What we publish | Official cyclically adjusted equivalent | Verdict |
|---|---|---|
| 12 COFOG expenditure lines (`GF01`–`GF10`, `GF01_7`, `GF01_X`) | none, from any source, for any of the three countries | **not available** |
| 10 ESA revenue lines (`R01`–`R10`) | OECD Economic Outlook covers 4 of them (`R01`+`R02` jointly, `R03`, `R04`, `R06`) | **partially available** |
| `TE`, `TR` | AMECO `UUTGAP` / `URTGAP`; OECD `YPGQA` / `YRGQA` (current only) | **available as aggregates** |
| `NLB`, `PB` | AMECO `UBLGAP`/`UBLGBP`, IMF WEO `GGSB_NPGDP`, OECD `NLGQA`, OBR CANB | **available** |

The COFOG gap is not an accident of publication. It is methodological, and
that matters more than the absence itself — see §3.

---

## 1. The functional (COFOG) side: nothing exists

Checked and found empty:

- **Eurostat** — the anchor for FRA/DEU. Enumerated the full dataflow
  catalogue (`dataflow/ESTAT/all/latest`): **8,156 dataflows, 0** whose title
  mentions cyclical adjustment or a structural balance. `gov_10a_exp` has no
  cyclically adjusted counterpart, and no Eurostat dataset carries one for any
  aggregate either.
- **OECD** — `DSD_EO` `CL_MEASURE` has 338 measures. 17 mention adjustment;
  every cyclically adjusted expenditure measure is an aggregate
  (`YPGA`/`YPGQA` current disbursements, `YPGXA`/`YPGXQA` the same excluding
  gross interest). Nothing by function. OECD Table 11 (`DSD_NASEC10@DF_TABLE11`),
  the COFOG flow this repo already ingests, has no adjusted variant.
- **AMECO** — chapter 17 is the cyclical-adjustment chapter: 18 variables,
  all aggregates (listed in §2). Chapter 16, the GG revenue/expenditure detail
  chapter, has 67 variables and **no** cyclically adjusted member.
- **IMF WEO** — `CL_WEO_INDICATOR`, 145 codes: exactly three touch the cycle
  (`GGSB`, `GGSB_NPGDP`, `NGAP_NPGDP`). A structural *balance* only.
- **National.** UK: the March 2026 EFO (retrieved via the gov.uk mirror, see
  §5) publishes four cyclically adjusted measures — net borrowing, current
  budget deficit, primary deficit, and GGNB — **all balances, no receipts or
  spending lines, nothing by function**. DEU: the cyclical adjustment that
  carries legal force is the debt-brake `Konjunkturkomponente`, a single
  figure applied to the budget balance; Destatis publishes no adjusted series.
  FRA: the structural balance in the *programme de stabilité*, scrutinised by
  the HCFP, is again a balance; INSEE publishes none.

A caution worth recording, because the two are easy to conflate: Eurostat and
the NSIs *do* publish **seasonally and calendar adjusted** quarterly
government data. That is a within-year timing adjustment. It is not cyclical
adjustment and must not be substituted for it.

## 2. The aggregate side: available, with a UK hole

AMECO chapter 17, Spring 2026 vintage (published 2026-06-03), measured spans:

| Series | Concept | GBR | FRA | DEU |
|---|---|---|---|---|
| `URTGAP` | CA total revenue | **2026–2027** | 1978–2027 | 1991–2027 |
| `UUTGAP` | CA total expenditure | **2026–2027** | 1978–2027 | 1991–2027 |
| `UUTGBP` | CA primary expenditure | **2026–2027** | 1978–2027 | 1991–2027 |
| `UBLGAP` | CA net lending/borrowing | 1987–2027 | 1965–2027 | 1991–2027 |
| `UBLGBP` | CA primary balance | 1987–2027 | 1978–2027 | 1991–2027 |
| `UBLGAPS` | Structural balance | **absent** | 2010–2027 | 2010–2027 |
| `UTCGCP` | Cyclical component of revenue | 1971–2027 | 1965–2027 | 1991–2027 |
| `UUCGCP` | Cyclical component of expenditure | 1971–2027 | 1965–2027 | 1991–2027 |

Two things to note. First, the **GBR two-observation hole in `URTGAP`/`UUTGAP`
is the same defect OQ-4 already records for unadjusted `URTG`/`UUTG`** — post-Brexit,
AMECO carries UK revenue and expenditure levels only for the forecast years.
The conclusion of OQ-4 carries over unchanged: *AMECO is usable for GBR
balance series, but not as a UK revenue or expenditure source*. Second,
`UBLGAPS` (the EDP structural balance) does not exist for the UK at all,
which is expected — it is an SGP construct.

IMF WEO 2026-04 `GGSB_NPGDP` is the longest single adjusted balance and the
easiest to add, since the pipeline already ingests this dataflow: GBR
1981–2031, FRA 1980–2031, DEU 1991–2031.

## 3. Why the COFOG gap is methodological, not editorial

Under the EU method (Mourre, Poissonnier & Lausegger, DG ECFIN Discussion
Paper 098, which is what AMECO's chapter 17 implements), the cyclical
component of the budget balance is built from **four revenue categories plus
exactly one expenditure category**: unemployment-related expenditure. Every
other spending item is treated as acyclical by construction. The OECD method
is the same in shape.

So AMECO's `UUCGCP` — "cyclical component of expenditure of general
government" — is, in substance, a cyclical adjustment of unemployment
benefits and nothing else. Mapped onto our tree that sits inside `GF10`
(social protection), and it is not published separately.

The consequence for this repo is worth stating plainly: **a cyclically
adjusted `GF02` or `GF07` is not an unpublished series, it is an undefined
one.** No official body has a method that would produce it. Anyone asking for
one is asking us to invent the concept, which is exactly what D13/D16 and the
"decompose, never force" principle exist to prevent. If the committee wants
functional cyclical adjustment, that is a research project with its own
elasticities, not a harvest.

## 4. The one genuinely useful finding: OECD adjusted revenue components

The OECD Economic Outlook is the only source that publishes cyclically
adjusted fiscal data **below the aggregate**, and it maps onto our revenue
tree better than anything else found. Measured spans, retrieved live
2026-09-10:

| OECD series | Concept | Our line(s) | GBR | FRA | DEU |
|---|---|---|---|---|---|
| `TINDA` | CA taxes on production and imports (D.2) | `R01`+`R02` **jointly** | 1971–2027 | 1985–2027 | 1991–2027 |
| `TYHA` | CA direct taxes on households | `R03` | 1985–2027 | 1985–2027 | 1991–2027 |
| `TYBA` | CA direct taxes on business | `R04` | 1971–2027 | 1985–2027 | 1991–2027 |
| `SSRGA` | CA social security contributions received | `R06` | 1971–2027 | 1985–2027 | 1991–2027 |
| `YRGQA` | CA current receipts, GG | ≈ `TR` | 1985–2027 | 1985–2027 | 1991–2027 |
| `YPGQA` | CA current disbursements, GG | ≈ `TE` | 1985–2027 | 1985–2027 | 1991–2027 |

Four of our ten revenue lines therefore have an official cyclically adjusted
analogue over spans comparable to our own. `R05`, `R07`, `R08`, `R09` and
`R10` have none anywhere.

Concept wedges that would have to be measured before any of this were used —
none is fatal, all are the same class of problem §7.11 and V1 already handle:

1. **`TINDA` does not split VAT.** Our `R01`/`R02` separation (D.211 vs the
   rest of D.2) has no adjusted counterpart; only the sum does.
2. **`SSRGA` is contributions *received*; our `R06` is D.61 net social
   contributions**, which includes the imputed component. A measured wedge,
   and `R06`'s imputed leg is already flagged D7-partial.
3. **`YPGQA` is *current* disbursements** — it excludes capital expenditure,
   so it is **not** an adjusted `TE`. Treating it as one would silently drop
   gross capital formation. AMECO's `UUTGAP` is the true total-expenditure
   concept, but it is the series with the GBR hole.
4. **The OECD adjusts on its own output gap**, which is not AMECO's and not
   the OBR's. Adjusted levels from different providers are not additive and
   must never be mixed within one identity.

## 5. Access note — OBR, and a route around it

`obr.uk` remains Cloudflare-challenge blocked from this environment (HTTP 403
on both the working-paper page and the databank download), exactly as OQ-6
records. **However, the March 2026 EFO is mirrored on `assets.publishing.service.gov.uk`,
which was allowlisted under D-S7-002**, and it fetched cleanly (1.1 MB, HTTP
200). That is how the UK finding in §1 was verified against the primary
document rather than secondary commentary.

This is a reusable route: **the gov.uk asset mirror can stand in for
obr.uk for EFO documents**, which softens OQ-6's "each new EFO needs the
manual route" for the PDF at least. It does not solve the databank or the
supplementary tables, which are obr.uk-only.

## 6. Recommendation

Do not extend the tree with cyclically adjusted lines. The concept does not
exist at COFOG level, and building it would violate D13/D16.

If the committee wants cyclical context, the defensible options, in order of
cost:

1. **Cheapest, and additive to the existing reconciliation module.** Add IMF
   WEO `GGSB_NPGDP` and `NGAP_NPGDP` to the §8 reconciliation only. The
   pipeline already pulls this dataflow and vintage; it is a `sources.yaml`
   subject-list change, no new source. This gives the WEO balance path a
   structural counterpart at zero conceptual risk, since §8 explains
   differences rather than forcing them.
2. **Moderate.** Register OECD EO as a *reconciliation* source for the four
   revenue lines above, carrying the wedges in §4 as measured `concept_note`
   fields. Useful; genuinely new information; does not touch the anchors.
3. **Not recommended.** Constructing cyclically adjusted COFOG lines from
   published elasticities. That is original research presented as official
   data, and the repo's governing principles rule it out.

Tabled for the committee as **OQ-8**.

---

## Sources verified

| Source | Endpoint hit 2026-09-10 | Result |
|---|---|---|
| Eurostat catalogue | `ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/dataflow/ESTAT/all/latest` | 8,156 flows, 0 cyclical/structural |
| EC AMECO ch.16, ch.17 | `ec.europa.eu/economy_finance/db_indicators/ameco/ameco{16,17}.zip` | 67 + 18 variables, spans measured |
| OECD Economic Outlook | `sdmx.oecd.org/public/rest` — `DSD_EO` + `DSD_EO@DF_EO` data | 338 measures; 1,153 obs pulled for GBR/FRA/DEU |
| IMF WEO | `api.imf.org/external/sdmx/3.0` — `CL_WEO_INDICATOR`, `IMF.RES:WEO(9.0.0)` | 145 codes; `GGSB_NPGDP` spans measured |
| OBR EFO March 2026 | `assets.publishing.service.gov.uk/media/69a6d7b62e1f4fbda4252208/...pdf` | 131 pp; 15 "cyclically adjusted" hits, all balances |
| obr.uk direct | `obr.uk/download/public-finances-databank/` | **HTTP 403** (OQ-6, unchanged) |
| EU method | DG ECFIN Discussion Paper 098 (Mourre et al.), `economy-finance.ec.europa.eu/system/files/2019-05/dp098_en.pdf` | unemployment expenditure is the only cyclical spending item |
