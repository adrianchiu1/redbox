# Files to hand-download (bot-challenged hosts: DMO, AFT)

Save each file as `data/incoming/{SOURCE_ID}/{part}.{ext}` exactly as named in the
third column (keep the extension the site gives: .xml, .xls, .xlsx, .pdf), then run
`ggfiscal debt ingest-incoming`. Open the URL in a normal browser; the first visit
solves the site's challenge, after which the export links download directly.
If a DMO URL answers "Report X is not available in this presentation type", the
`exportFormatValue` parameter is missing — use the form below, or the page's own
export button (Data → Gilt market → the report → Excel/XML icon).

## UK Debt Management Office — dmo.gov.uk

| # | URL | save as |
|---|---|---|
| 1 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xml&parameters=&COBDate= | `UK_DMO_GILTS/D1A_xml.xml` |
| 2 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D1A.xls` |
| 3 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1C&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D1C.xls` |
| 4 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1D&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D1D.xls` |
| 5 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.1E&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D2.1E.xls` |
| 6 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.1A&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D2.1A.xls` |
| 7 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.1PROF7&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D2.1PROF7.xls` |
| 8 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.1PROF9&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D2.1PROF9.xls` |
| 9 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D10A&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D10A.xls` |
| 10 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D4L&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D4L.xls` |
| 11 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D8B&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D8B.xls` |
| 12 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D5I&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D5I.xls` |
| 13 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D10C&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D10C.xls` |
| 14 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D9C&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_GILTS/D9C.xls` |
| 15 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.2A&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_BILLS/D2.2A.xls` |
| 16 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.2D&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_BILLS/D2.2D.xls` |
| 17 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.2E&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_BILLS/D2.2E.xls` |
| 18 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D2.2G&exportFormatValue=xls&parameters=&COBDate= | `UK_DMO_BILLS/D2.2G.xls` |
| 19 | https://www.dmo.gov.uk/data/gilt-market/gross-and-net-issuance-data/ | `UK_DMO_GILTS/gross_net_issuance_annual.xls (the 'annual gross and net issuance' export) and UK_DMO_GILTS/cash_sales_by_type_and_maturity.xls (the 'cash sales of gilts by type and maturity' export)` |

Year-end positions (one per 31 December; the site returns the previous working day when the date is not one — that is fine):

| # | URL | save as |
|---|---|---|
| 20 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F1998 | `UK_DMO_GILTS/D1A_cob_19981231.xls` |
| 21 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F1999 | `UK_DMO_GILTS/D1A_cob_19991231.xls` |
| 22 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2000 | `UK_DMO_GILTS/D1A_cob_20001231.xls` |
| 23 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2001 | `UK_DMO_GILTS/D1A_cob_20011231.xls` |
| 24 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2002 | `UK_DMO_GILTS/D1A_cob_20021231.xls` |
| 25 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2003 | `UK_DMO_GILTS/D1A_cob_20031231.xls` |
| 26 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2004 | `UK_DMO_GILTS/D1A_cob_20041231.xls` |
| 27 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2005 | `UK_DMO_GILTS/D1A_cob_20051231.xls` |
| 28 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2006 | `UK_DMO_GILTS/D1A_cob_20061231.xls` |
| 29 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2007 | `UK_DMO_GILTS/D1A_cob_20071231.xls` |
| 30 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2008 | `UK_DMO_GILTS/D1A_cob_20081231.xls` |
| 31 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2009 | `UK_DMO_GILTS/D1A_cob_20091231.xls` |
| 32 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2010 | `UK_DMO_GILTS/D1A_cob_20101231.xls` |
| 33 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2011 | `UK_DMO_GILTS/D1A_cob_20111231.xls` |
| 34 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2012 | `UK_DMO_GILTS/D1A_cob_20121231.xls` |
| 35 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2013 | `UK_DMO_GILTS/D1A_cob_20131231.xls` |
| 36 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2014 | `UK_DMO_GILTS/D1A_cob_20141231.xls` |
| 37 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2015 | `UK_DMO_GILTS/D1A_cob_20151231.xls` |
| 38 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2016 | `UK_DMO_GILTS/D1A_cob_20161231.xls` |
| 39 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2017 | `UK_DMO_GILTS/D1A_cob_20171231.xls` |
| 40 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2018 | `UK_DMO_GILTS/D1A_cob_20181231.xls` |
| 41 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2019 | `UK_DMO_GILTS/D1A_cob_20191231.xls` |
| 42 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2020 | `UK_DMO_GILTS/D1A_cob_20201231.xls` |
| 43 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2021 | `UK_DMO_GILTS/D1A_cob_20211231.xls` |
| 44 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2022 | `UK_DMO_GILTS/D1A_cob_20221231.xls` |
| 45 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2023 | `UK_DMO_GILTS/D1A_cob_20231231.xls` |
| 46 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2024 | `UK_DMO_GILTS/D1A_cob_20241231.xls` |
| 47 | https://www.dmo.gov.uk/umbraco/surface/DataExport/GetDataExport?reportCode=D1A&exportFormatValue=xls&parameters=&COBDate=31%2F12%2F2025 | `UK_DMO_GILTS/D1A_cob_20251231.xls` |

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
