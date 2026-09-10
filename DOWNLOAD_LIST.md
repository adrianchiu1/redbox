# Files to hand-download (bot-challenged hosts: DMO, AFT)

Save each file as `data/incoming/{SOURCE_ID}/{part}.{ext}` exactly as named in the
third column (keep the extension the site gives: .xml, .xls, .xlsx, .pdf), then run
`ggfiscal debt ingest-incoming`. Open the URL in a normal browser; the first visit
solves the site's challenge, after which the export links download directly.
If a DMO URL answers "Report X is not available in this presentation type", the
`exportFormatValue` parameter is missing — use the form below, or the page's own
export button (Data → Gilt market → the report → Excel/XML icon).

## UK Debt Management Office — dmo.gov.uk

Status 2026-09-10: the export endpoint below is reachable from the build box
through the package's browser session (`ggfiscal debt fetch --family
debt_offices`), so these rows are a fallback, not a chore. Each report exports in
exactly one presentation type (`exportFormatValue`); any other value, and the
plain `ExportReport?reportCode=` form, return a 35-byte stub "Unable to fulfil the
report request" (a download of that size is a failure). D10A's "xls" is an HTML
table; keep the .xls name, the reader sniffs it.

| # | URL | save as |
|---|---|---|
| 1 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xml&parameters=&COBDate= | `UK_DMO_GILTS/D1A.xml` |
| 2 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1C&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D1C.xls` |
| 3 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.1E&exportFormatValue=xml&parameters=&COBDate= | `UK_DMO_GILTS/D2.1E.xml` |
| 4 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.1A&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D2.1A.xls` |
| 5 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.1PROF7&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D2.1PROF7.xls` |
| 6 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.1PROF9&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D2.1PROF9.xls` |
| 7 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D10A&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D10A.xls` |
| 8 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D4L&exportFormatValue=xml&parameters=&COBDate= | `UK_DMO_GILTS/D4L.xml` |
| 9 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D8B&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D8B.xls` |
| 10 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D10C&exportFormatValue=xml&parameters=&COBDate= | `UK_DMO_GILTS/D10C.xml` |
| 11 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.2D&exportFormatValue=xml&parameters=&COBDate= | `UK_DMO_BILLS/D2.2D.xml` |
| 12 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.2E&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_BILLS/D2.2E.xls` |
| 13 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.2G&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_BILLS/D2.2G.xls` |

Not exportable by URL in any format tried (xls, xlsx, xml, pdf, csv): **D1D, D5I,
D9C, D2.2A**. If the page for one of them shows an Excel/XML icon, right-click it,
copy the link and send it; the pieces they carry (cash-flow schedules, bill stock)
are otherwise derived from D2.1E/D1C and D2.2D.

Year-end position snapshots (`COBDate=DD%2FMM%2FYYYY`): the xml export ignores
the date (it always returns the latest close of business) and the xls export
returns the stub, so the 1998–2025 panel is NOT obtainable from this endpoint as
written. On the Gilts in Issue page, pick a past close-of-business date, then
right-click the Excel/XML icon and send the link: the date must travel in the
`parameters=` slot in a form only the page reveals. Until then the positions panel
is rebuilt from the flows (D2.1E issuance, D1C redemptions, D2.1PROF7 switches and
buybacks), the way the German register is.

## Agence France Trésor — aft.gouv.fr

These pages carry versioned Excel links; download the file the page offers and save under the name given.

| # | page | file to take | save as |
|---|---|---|---|
| 48 | https://www.aft.gouv.fr/fr/encours-detaille-oat | the Excel export of the OAT table (fixed-rate OAT lines) | `FRA_AFT_ENCOURS/oat_xlsx.xlsx` |
| 49 | https://www.aft.gouv.fr/fr/encours-detaille-btf | the Excel export of the BTF table | `FRA_AFT_ENCOURS/btf_xlsx.xlsx` |
| 50 | https://www.aft.gouv.fr/en/encours-detaille-oatei | the Excel export of the indexed lines (OATi and OAT€i) | `FRA_AFT_ENCOURS/oatei_xlsx.xlsx` |
| 51 | https://www.aft.gouv.fr/fr/dernieres-adjudications | the OAT auction history workbook (hist_oat…xlsx) | `FRA_AFT_ADJUDICATIONS/hist_oat.xlsx` |
| 52 | https://www.aft.gouv.fr/fr/dernieres-adjudications | the BTF auction history workbook (…hist_btf.xlsx) | `FRA_AFT_ADJUDICATIONS/hist_btf.xlsx` |
| 53 | https://www.aft.gouv.fr/fr/dernieres-adjudications-archives | the pre-June-2018 OAT/BTAN auction archive file(s) | `FRA_AFT_ADJUDICATIONS/archives_oat.xlsx` |
| 54 | https://www.aft.gouv.fr/fr/dernieres-adjudications-archives | the pre-June-2018 BTF auction archive file | `FRA_AFT_ADJUDICATIONS/archives_btf.xlsx` |
| 55 | https://www.aft.gouv.fr/fr/oati-principaux-chiffres | current OATi coefficients (XLS, ~940 KB) | `FRA_AFT_INDEXATION/oati_current.xls` |
| 56 | https://www.aft.gouv.fr/fr/oati-principaux-chiffres | historical base-1998 OATi coefficients (XLS, 1998-07-25 to 2016-03-01) | `FRA_AFT_INDEXATION/oati_hist_1998.xls` |
| 57 | https://www.aft.gouv.fr/en/oateuroi-key-figures | current OAT€i coefficients (XLSX, ~730 KB) | `FRA_AFT_INDEXATION/oatei_current.xlsx` |
| 58 | https://www.aft.gouv.fr/en/oateuroi-key-figures | historical base-2005 OAT€i coefficients (XLS, 2001-07-25 to 2016-03-01) | `FRA_AFT_INDEXATION/oatei_hist_2005.xls` |
| 59 | https://www.aft.gouv.fr/fr/rapports-activite | Rapport d'activité 2024 (PDF) | `FRA_AFT_FINANCEMENT/rapport_2024.pdf` |
| 60 | https://www.aft.gouv.fr/fr/rapports-activite | Rapport d'activité 2023 (PDF) | `FRA_AFT_FINANCEMENT/rapport_2023.pdf` |

Optional, larger: the Bulletin mensuel PDF archive at https://www.aft.gouv.fr/fr/bulletins-mensuels (the only month-by-month line register before the AFT Excel era). Not needed for the first pass; if you want it, save the PDFs as `FRA_AFT_BULLETINS/{YYYY-MM}.pdf` and say so.

Already harvested automatically (no action): everything from the Finanzagentur, BMF, ONS, HM Treasury, Bank of England, Eurostat, INSEE, OECD, ECB.
