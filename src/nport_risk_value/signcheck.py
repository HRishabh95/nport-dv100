"""SIGNCHECK_PROTOCOL.md: check inferred sign conventions against each fund's own holdings, leg by leg.

Usage: python src/nport_risk_value/signcheck.py   -> audit/signcheck.json, audit/signcheck_families.csv
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
AU = ROOT / "data/interim/nport_risk_value/audit"


def agree(L):
    w = L.EST_C.abs()
    a = (np.sign(L.H) == np.sign(L.EST_C)).astype(float)
    return {"legs": int(len(L)), "records": int(L.ACCESSION_NUMBER.nunique()),
            "weighted": float((a * w).sum() / w.sum()) if len(L) else None, "unweighted": float(a.mean()) if len(L) else None}


def main():
    fq = pd.read_parquet(AU / "fund_quarters.parquet").set_index("ACCESSION_NUMBER")
    L = pd.read_parquet(AU / "legs.parquet")
    L = L[L.UNIT != "UNIT_UNRESOLVED"].copy()
    for c in ["NAV", "SIGN_D1", "CONV", "CONV_RULE", "STATUS_D1", "PLAIN", "CRD", "CIK", "REGISTRANT_NAME"]:
        L[c] = L.ACCESSION_NUMBER.map(fq[c])
    L["DV"] = np.where(L.UNIT == "LOCAL_UNITS", L.DV100 / L.X, L.DV100)
    L["H"] = L.DV * L.SIGN_D1
    q = (L.EST_C.abs() >= 0.0025 * L.NAV) & (L.DV.abs() >= 0.0025 * L.NAV) & (L.NAV > 0)
    L = L[q & (L.STATUS_D1 != "UNRESOLVED")]
    L["FAMILY"] = np.where(L.CRD.fillna("") != "", "CRD" + L.CRD.fillna(""), "CIK" + L.CIK.astype(str))
    inf = L[L.CONV_RULE.isin(["registrant", "adviser"])]
    R = {"protocol_sha": (ROOT / "data/interim/nport_risk_value/SIGNCHECK_PROTOCOL_SHA256").read_text().split()[0],
         "overall": agree(inf), "inferred_R": agree(inf[inf.CONV == "R"]), "inferred_F": agree(inf[inf.CONV == "F"]),
         "by_rule": {r: agree(g) for r, g in inf.groupby("CONV_RULE")},
         "benchmark_as_filed_nonplain": agree(L[(L.STATUS_D1 == "COMPARABLE_AS_FILED") & ~L.PLAIN.fillna(False)])}
    o, r_, f_ = R["overall"]["weighted"], R["inferred_R"]["weighted"], R["inferred_F"]["weighted"]
    R["verdict"] = ("CONFIRMED" if o >= 0.80 and r_ >= 0.75 and f_ >= 0.75 else
                    "NOT CONFIRMED" if o < 0.65 or min(r_, f_) < 0.60 else "MIXED")
    fam = []
    for k, g in inf.groupby("FAMILY"):
        a = agree(g)
        fam.append({"FAMILY": k, "NAME": g.REGISTRANT_NAME.mode().iloc[0], "CONV": g.CONV.mode().iloc[0], **a})
    fam = pd.DataFrame(fam).sort_values("legs", ascending=False)
    fam.to_csv(AU / "signcheck_families.csv", index=False)
    flagged = fam[(fam.legs >= 5) & (fam.weighted < 0.5)]
    R["families_with_5plus_legs"] = int((fam.legs >= 5).sum())
    R["flagged_families"] = flagged[["FAMILY", "NAME", "CONV", "legs", "records", "weighted"]].to_dict("records")
    (AU / "signcheck.json").write_text(json.dumps(R, indent=1, default=str))
    print(json.dumps({k: v for k, v in R.items() if k != "flagged_families"}, indent=1))
    print(flagged.to_string())


if __name__ == "__main__":
    main()
