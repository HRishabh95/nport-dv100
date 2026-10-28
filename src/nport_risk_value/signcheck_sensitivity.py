"""SIGNCHECK_PROTOCOL.md sensitivity: inferred records of flagged families set UNRESOLVED; recompute pair flips
and the outcome study's convention cost. Usage: python src/nport_risk_value/signcheck_sensitivity.py
Writes audit/signcheck_sensitivity.json.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import audit

ROOT = Path(__file__).resolve().parents[2]
AU = ROOT / "data/interim/nport_risk_value/audit"
O = ROOT / "data/interim/nport_risk_value/outcome"


def main():
    fq = pd.read_parquet(AU / "fund_quarters.parquet")
    flagged = {f["FAMILY"] for f in json.loads((AU / "signcheck.json").read_text())["flagged_families"]}
    fq["FAMILY"] = np.where(fq.CRD.fillna("") != "", "CRD" + fq.CRD.fillna(""), "CIK" + fq.CIK.astype(str))
    bad = fq.FAMILY.isin(flagged) & fq.CONV_RULE.isin(["registrant", "adviser"]) & (fq.STATUS_D1 != "UNRESOLVED")
    out = {"records_reclassified": int(bad.sum())}
    for lab, G in [("D1", fq), ("D1_minus_flagged", fq.assign(STATUS_D1=np.where(bad, "UNRESOLVED", fq.STATUS_D1)))]:
        out[lab] = audit.pairs_flip(G.assign(STATUS=G.STATUS_D1, SIGN=G.SIGN_D1))
    # records inferred through the N-CEN placeholder adviser ID "N/A" (pools unrelated advisers)
    na = (fq.CRD == "N/A") & (fq.CONV_RULE == "adviser")
    out["na_adviser_records"] = {"D1": int((na & (fq.STATUS_D1 != "UNRESOLVED")).sum()),
                                 "frozen": int((na & (fq.STATUS != "UNRESOLVED")).sum())}
    out["D1_minus_na_adviser"] = audit.pairs_flip(
        fq.assign(STATUS=np.where(na, "UNRESOLVED", fq.STATUS_D1), SIGN=fq.SIGN_D1))
    out["frozen"] = audit.pairs_flip(fq)
    out["frozen_minus_na_adviser"] = audit.pairs_flip(fq.assign(STATUS=np.where(na, "UNRESOLVED", fq.STATUS)))
    bad_acc = set(fq.ACCESSION_NUMBER[bad])
    rec = pd.read_parquet(O / "records.parquet")
    R = json.loads((O / "result_conf.json").read_text())
    excl = set(R["excluded_funds"]["check_keys"]) | set(pd.read_csv(AU / "s6_sample.csv", dtype=str).FUND_KEY)
    d = pd.read_parquet(O / "pred_conf_primary_FX_ecb.parquet")
    fm = pd.read_parquet(O / "fundmonths_primary.parquet")[["FUND_KEY", "M", "REC"]]
    d = d.merge(fm, on=["FUND_KEY", "M"], suffixes=("", "_r"))
    d["ACC"] = rec.ACCESSION_NUMBER.values[d.REC]
    m = d[~d.QUARTER.isin(["2026q2", "2026q3"]) & ~d.FUND_KEY.isin(excl)]
    out["outcome_evaluated_fund_months_dropped"] = int(m.ACC.isin(bad_acc).sum())
    print(json.dumps(out, indent=1))
    (AU / "signcheck_sensitivity.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
