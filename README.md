# Same Exposure, Opposite Signs

Code for the working paper *Same Exposure, Opposite Signs: Interest-Rate Risk Reporting Conventions in SEC
Form N-PORT* (Rishabh Gyanendra Upadhyay, Inception42).

Form N-PORT Item B.3 asks funds for DV100, "the change in value of the portfolio resulting from a 100 basis
point change in interest rates", without saying whether rates rise or fall. About half of plain bond
fund-quarters report it as positive and half as negative, and the choice is made by the fund complex. This
repository contains the code to:
- classify every filer's convention;
- validate the classification;
- build fund-complex convention lookup tables;
- run the pre-registered return study;
- regenerate every figure and table in the paper.

**No data is included.** All inputs are public and are downloaded from the sources below.

## Requirements

- Python 3.9+ with the packages in `requirements.txt`.
- [Tectonic](https://tectonic-typesetting.github.io/), to build the paper:
  `conda create -n tectonic -c conda-forge tectonic`.
- `export SEC_USER_AGENT="Your Name your@email"`. The SEC's fair-access policy requires a descriptive
  User-Agent for scripted requests to sec.gov.

## Inputs (place under `data/raw/`)

| Input | Source | Location |
|---|---|---|
| Form N-PORT data sets, 2019q4-2026q3 | `https://www.sec.gov/files/dera/data/form-n-port-data-sets/{q}_nport.zip` | `data/raw/nport/{q}_nport.zip` |
| Form N-CEN data sets, same quarters | SEC Form N-CEN data sets page | `data/raw/ncen/{q}_ncen.zip` |
| ECB end-of-month reference rates | `https://data-api.ecb.europa.eu/service/data/EXR/M..EUR.SP00.E?format=csvdata&startPeriod=2019-06` | `data/raw/fx/ecb_exr_monthly_eop.csv` |
| Government yield curves (US, EUR, JPY, CAD, AUD) | downloaded by `fetch_yields.py` | `data/raw/yields/` |
| Bank of England nominal spot curve | BoE yield-curve archive (`GLC Nominal daily data_*.xlsx`) | `data/raw/yields/boe/`, `data/raw/yields/boe_latest/` |
| Daily closes for ACWI, HYG, IEI (factor returns; return study only) | any daily price source | `data/interim/daily_bars.parquet` with columns `symbol, ts, close` |

## Pipeline

```sh
Q="2019q4 2020q1 ... 2026q3"                      # the 28 data-set quarters

# 1. Extract filings (no returns are read)
python src/nport_risk_value/extract.py $Q
python src/nport_risk_value/extract_ncen.py $Q

# 2. Sign-convention audit (AUDIT_PROTOCOL.md), deviation D1, original-XML check
python src/nport_risk_value/audit.py
python src/nport_risk_value/audit_d1.py
python src/nport_risk_value/audit_s6.py            # fetches 19 filings from EDGAR
python src/nport_risk_value/signcheck.py           # SIGNCHECK_PROTOCOL.md

# 3. Fund-complex and adviser lookup tables
python reports/nport_dv100/lookup.py

# 4. Pre-registered return study (OUTCOME_PROTOCOL.md + amendments)
python src/nport_risk_value/fetch_yields.py
python src/nport_risk_value/fx_coverage.py
python src/nport_risk_value/extract_outcome.py fwd $Q
python src/nport_risk_value/exposures.py $Q
python src/nport_risk_value/outcome.py prep
python src/nport_risk_value/extract_outcome.py returns $Q   # first step that reads returns
python src/nport_risk_value/outcome.py run dev
python src/nport_risk_value/outcome.py run conf
python src/nport_risk_value/signcheck_sensitivity.py

# 5. Paper figures, tables and PDF
reports/nport_dv100/paper/build.sh

# 6. Separate re-implementation of the census
python reports/nport_dv100/replication/build.py
python reports/nport_dv100/replication/analyze.py
```

## Pre-registration record

The protocols were frozen before the analyses they govern, and their SHA-256 hashes are quoted in the
paper:

| Document | SHA-256 prefix |
|---|---|
| `AUDIT_PROTOCOL.md` | 7c51d52c |
| `OUTCOME_PROTOCOL.md` | fe1c473e |
| `OUTCOME_AMENDMENT_1.md` | e6a248e8 |
| `OUTCOME_AMENDMENT_2.md` | 8ae3f579 |
| `SIGNCHECK_PROTOCOL.md` | 29cbe65b |

The results are in `AUDIT.md` and `OUTCOME.md`. Deviations and corrections are logged in
`reports/nport_dv100/NUMBERS_AUDIT.md`. `PROTOCOL.md`, `CHECK.md` and `gates.py` record the earlier
screening stage.

## Lookup tables

`reports/nport_dv100/lookup.py` writes `reports/nport_dv100/data/fund_complex_dv100_conventions.csv` and
`adviser_dv100_conventions.csv`. The column definitions and usage cautions are in
`reports/nport_dv100/data/README.md`. In short:
- **R**: the value change for a rise in rates.
- **F**: a positive number for a long bond fund, either the change for a fall or an unsigned magnitude.
  F is a reporting convention, not an instruction to flip every number.
