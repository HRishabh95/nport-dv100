"""Fund-complex DV100 sign-convention lookup (registrant x data-set quarter), from the frozen audit outputs.

Rule (AUDIT_PROTOCOL.md S3): a registrant-quarter's convention is the majority class of its plain long-only
bond funds when >= 2 such funds exist and >= 90% agree; otherwise UNRESOLVED at registrant level.
Usage: python reports/nport_dv100/lookup.py -> reports/nport_dv100/data/fund_complex_dv100_conventions.csv
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
AU = ROOT / "data/interim/nport_risk_value/audit"
OUT = Path(__file__).resolve().parent / "data"
OUT.mkdir(exist_ok=True)


def main():
    fq = pd.read_parquet(AU / "fund_quarters.parquet")
    build(fq, "CIK", "REGISTRANT_NAME", "REGISTRANT", "fund_complex_dv100_conventions.csv")
    # adviser CRD must be a real number: N-CEN carries a literal "N/A" placeholder for some advisers
    fq = fq[fq.CRD.fillna("").str.fullmatch(r"\d+")]
    build(fq, "CRD", "ADVISER", "ADVISER", "adviser_dv100_conventions.csv")


def build(fq, key, namecol, label, fname):
    notes = pd.read_parquet(AU / "notes.parquet")
    conv_note = set(notes.ACCESSION_NUMBER[notes.TAG == "CONVENTION"])
    flagged = {f["NAME"] for f in json.loads((AU / "signcheck.json").read_text())["flagged_families"]}
    fq["EVID"] = fq.PLAIN & ~fq.MAGFLAG & fq.PCLASS.isin(["R", "F"])
    fq["NOTE"] = fq.ACCESSION_NUMBER.isin(conv_note)
    name = fq.sort_values("QUARTER").groupby(key)[namecol].last()
    rows = []
    for (cik, q), g in fq.groupby([key, "QUARTER"]):
        e = g[g.EVID]
        nr, nf = int((e.PCLASS == "R").sum()), int((e.PCLASS == "F").sum())
        n = nr + nf
        top = "R" if nr >= nf else "F"
        agree = max(nr, nf) / n if n else np.nan
        conv = top if (n >= 2 and agree >= 0.90) else "UNRESOLVED"
        lim = []
        if n < 2:
            lim.append("fewer than 2 plain bond funds")
        elif agree < 0.90:
            lim.append("plain funds disagree (<90%)")
        if g.REGISTRANT_NAME.isin(flagged).any():
            lim.append("multi-adviser or flagged trust: inferred funds disagreed with holdings in sign check")
        basis = "none"
        if conv != "UNRESOLVED":
            basis = "plain-fund majority" + (" + explanatory note" if g.NOTE.any() else "")
        rows.append({f"{label}_ID": cik, f"{label}_NAME": name[cik], "QUARTER": q, "CONVENTION": conv,
                     "N_PLAIN_R": nr, "N_PLAIN_F": nf, "AGREEMENT": round(agree, 3) if n else None,
                     "BASIS": basis, "N_FUNDS_WITH_DV100": int(len(g)),
                     "N_FUNDS_RESOLVED_IN_AUDIT": int((g.STATUS_D1 != "UNRESOLVED").sum()),
                     "LIMITATIONS": "; ".join(lim)})
    t = pd.DataFrame(rows).sort_values([f"{label}_NAME", "QUARTER"])
    prev = t.groupby(f"{label}_ID").CONVENTION.shift()
    res = t.CONVENTION.isin(["R", "F"])
    prev_res = prev.where(prev.isin(["R", "F"])).groupby(t[f"{label}_ID"]).ffill()
    t["CHANGED_FROM_PREVIOUS_RESOLVED"] = res & prev_res.notna() & (t.CONVENTION != prev_res)
    t.to_csv(OUT / fname, index=False)
    s = {"table": fname, "rows": len(t), "groups": int(t[f"{label}_ID"].nunique()),
         "convention_counts": t.CONVENTION.value_counts().to_dict(),
         "fund_quarters_in_resolved_registrant_quarters": int(t[res].N_FUNDS_WITH_DV100.sum()),
         "fund_quarters_total": int(t.N_FUNDS_WITH_DV100.sum()),
         "groups_with_a_change": int(t[t.CHANGED_FROM_PREVIOUS_RESOLVED][f"{label}_ID"].nunique()),
         "with_explanatory_note": int(t.BASIS.str.contains("note").sum())}
    print(json.dumps(s, indent=1))
    return t


if __name__ == "__main__":
    main()
