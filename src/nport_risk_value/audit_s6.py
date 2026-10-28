"""AUDIT_PROTOCOL.md step S6: compare original N-PORT XML Item B.3 cells with the bulk data set.

Usage: python src/nport_risk_value/audit_s6.py
Reads audit/s6_sample.csv, caches XML in audit/s6_xml/, writes audit/s6_results.csv and s6_notes.csv.
"""
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "data/interim/nport_risk_value/audit"
EX = ROOT / "data/interim/nport_risk_value/extract"
XML = A / "s6_xml"
XML.mkdir(exist_ok=True)
UA = os.environ["SEC_USER_AGENT"]  # e.g. "Your Name your@email" (SEC fair-access policy)
PER = {"period3Mon": "3MON", "period1Yr": "1YR", "period5Yr": "5YR", "period10Yr": "10YR", "period30Yr": "30YR"}


def fetch(cik, acc):
    p = XML / f"{acc}.xml"
    if not p.exists() or p.stat().st_size == 0:
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/primary_doc.xml"
        subprocess.run(["curl", "-s", "-f", "-A", UA, "-o", str(p), url], check=True)
        time.sleep(0.3)
    return p


def strip(tag):
    return tag.split("}")[-1]


def parse(p):
    root = ET.parse(p).getroot()
    cells, notes = [], []
    for el in root.iter():
        t = strip(el.tag)
        if t == "curMetric":
            cur = next((c.text for c in el if strip(c.tag) == "curCd"), None)
            for c in el:
                k = strip(c.tag)
                if k in ("intrstRtRiskdv01", "intrstRtRiskdv100"):
                    for a, b in PER.items():
                        cells.append({"CUR": (cur or "").strip().upper(), "METRIC": "DV01" if k.endswith("01") else "DV100",
                                      "BUCKET": b, "XML": float(c.attrib.get(a, "nan"))})
        elif t == "explntrNote":
            notes.append({"ITEM": el.attrib.get("noteItem", ""), "NOTE": el.attrib.get("note", "")})
    return pd.DataFrame(cells), pd.DataFrame(notes)


def main():
    S = pd.read_csv(A / "s6_sample.csv", dtype=str)
    rows, nrows = [], []
    irr_cache = {}
    for acc, s in S.groupby("ACCESSION_NUMBER", sort=False):
        r = s.iloc[0]
        cells, notes = parse(fetch(r.CIK, acc))
        q = r.QUARTER
        if q not in irr_cache:
            irr_cache[q] = pd.read_parquet(EX / f"{q}_irr.parquet")
        irr = irr_cache[q]
        irr = irr[irr.ACCESSION_NUMBER == acc].copy()
        irr["CUR"] = irr.CURRENCY_CODE.str.strip().str.upper()
        bulk = []
        for _, x in irr.iterrows():
            for m in ("DV01", "DV100"):
                for b in PER.values():
                    v = x[f"INTRST_RATE_CHANGE_{b}_{m}"]
                    bulk.append({"CUR": x.CUR, "METRIC": m, "BUCKET": b,
                                 "BULK": float(v) if v not in ("", None) else np.nan})
        bulk = pd.DataFrame(bulk).groupby(["CUR", "METRIC", "BUCKET"], as_index=False).BULK.sum(min_count=1)
        m = cells.groupby(["CUR", "METRIC", "BUCKET"], as_index=False).XML.sum(min_count=1).merge(
            bulk, on=["CUR", "METRIC", "BUCKET"], how="outer")
        both = m.XML.fillna(0), m.BULK.fillna(0)
        rel = (both[0] - both[1]).abs() / np.maximum(both[0].abs(), 1e-9)
        m["MATCH"] = (rel < 1e-6) | ((both[0] == 0) & (both[1] == 0))
        dv100 = m[m.METRIC == "DV100"]
        rows.append({"ACCESSION_NUMBER": acc, "STRATA": ",".join(s.STRATUM), "SERIES_NAME": r.SERIES_NAME,
                     "REGISTRANT_NAME": r.REGISTRANT_NAME, "QUARTER": q, "CONV": r.CONV, "CONV_RULE": r.CONV_RULE,
                     "STATUS": r.STATUS, "cells": len(m), "mismatch": int((~m.MATCH).sum()),
                     "currencies_xml": cells.CUR.nunique(), "currencies_bulk": irr.CUR.nunique(),
                     "xml_net_dv100": dv100.XML.sum(), "bulk_net_dv100": dv100.BULK.sum(),
                     "b3_notes": int(notes.ITEM.str.startswith("B.3").sum()) if len(notes) else 0})
        for _, n in notes.iterrows():
            nrows.append({"ACCESSION_NUMBER": acc, "SERIES_NAME": r.SERIES_NAME, **n.to_dict()})
        if (~m.MATCH).any():
            print(acc, "MISMATCH\n", m[~m.MATCH].to_string())
    R = pd.DataFrame(rows)
    R.to_csv(A / "s6_results.csv", index=False)
    pd.DataFrame(nrows).to_csv(A / "s6_notes.csv", index=False)
    pd.set_option("display.width", 250)
    print(R.drop(columns=["REGISTRANT_NAME"]).to_string())


if __name__ == "__main__":
    main()
