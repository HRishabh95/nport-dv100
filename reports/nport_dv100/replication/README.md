# Blind replication of the plain-fund sign census

A separate model agent (Claude, run as a subagent on 2026-10-28) wrote `build.py` and `analyze.py`.
It was briefed on the question and the form text, read only `src/nport_risk_value/extract.py` and the
extracted SEC bulk data, and had no access to the audit code or results. It is an independent
re-implementation on **the same SEC bulk data**, not independent data. It covers only the plain-fund
sign census (share positive, registrant unanimity, leave-one-out, top registrants). It does not
cover units, inferred conventions for non-plain funds or the return study.

Run: `python build.py` (writes `data/interim/nport_risk_value/replication/panel.parquet`), then
`python analyze.py` (main: plausibility-screened sample) and `python analyze.py noplaus`. Saved
outputs: `output_plaus.txt`, `output_noplaus.txt`.
