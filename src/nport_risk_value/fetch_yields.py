"""Month-end government yields by currency and Item B.3 bucket (OUTCOME_PROTOCOL.md, "Rate changes").

Downloads official files into data/raw/yields/ (robots.txt checked 2026-10-27) and writes
data/interim/nport_risk_value/yields_monthly.parquet: CUR, BUCKET, MONTH (period), Y (percent),
SOURCE, DATE (last observation used in the month).

Usage: python src/nport_risk_value/fetch_yields.py
"""
import io
import os
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/yields"
OUT = ROOT / "data/interim/nport_risk_value/yields_monthly.parquet"
UA = os.environ["SEC_USER_AGENT"]  # e.g. "Your Name your@email" (SEC fair-access policy)
START = 2016


def get(url, name):
    p = RAW / name
    if not p.exists() or p.stat().st_size == 0:
        subprocess.run(["curl", "-s", "-f", "-A", UA, "-o", str(p), url], check=True)
    return p


def usd():
    frames = []
    for y in range(START, 2027):
        url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
               f"daily-treasury-rates.csv/{y}/all?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv")
        d = pd.read_csv(get(url, f"ust_{y}.csv"))
        frames.append(d)
    d = pd.concat(frames)
    d["DATE"] = pd.to_datetime(d["Date"])
    m = {"3MON": "3 Mo", "1YR": "1 Yr", "5YR": "5 Yr", "10YR": "10 Yr", "30YR": "30 Yr"}
    return long(d, m, "USD", "US Treasury par yield curve")


def eur():
    cols = {}
    for b, t in {"3MON": "3M", "1YR": "1Y", "5YR": "5Y", "10YR": "10Y", "30YR": "30Y"}.items():
        url = (f"https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_{t}"
               f"?format=csvdata&startPeriod={START}-01-01")
        d = pd.read_csv(get(url, f"ecb_aaa_spot_{t}.csv"))
        cols[b] = d.set_index(pd.to_datetime(d.TIME_PERIOD)).OBS_VALUE
    d = pd.DataFrame(cols).rename_axis("DATE").reset_index()
    return long(d, {b: b for b in cols}, "EUR", "ECB euro area AAA spot curve")


def gbp():
    files = sorted((RAW / "boe").glob("GLC Nominal daily data_20[12]*.xlsx")) + \
        sorted((RAW / "boe_latest").glob("GLC Nominal daily data current month.xlsx"))
    frames = []
    for f in files:
        x = pd.read_excel(f, "4. spot curve", header=None)
        mats = x.iloc[3, 1:].tolist()
        body = x.iloc[5:].copy()
        body.columns = ["DATE"] + mats
        body = body[pd.to_datetime(body.DATE, errors="coerce").notna()]
        body["DATE"] = pd.to_datetime(body.DATE)
        frames.append(body)
    d = pd.concat(frames).drop_duplicates("DATE", keep="last")
    d = d[d.DATE.dt.year >= START]
    m = {"3MON": 0.5, "1YR": 1, "5YR": 5, "10YR": 10, "30YR": 30}
    return long(d, m, "GBP", "Bank of England nominal spot curve")


def jpy():
    a = pd.read_csv(get("https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv",
                        "mof_jgbcme_all.csv"), skiprows=1, encoding="latin-1")
    c = pd.read_csv(get("https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv",
                        "mof_jgbcme.csv"), skiprows=1, encoding="latin-1")
    d = pd.concat([a, c])
    d["DATE"] = pd.to_datetime(d.Date, format="%Y/%m/%d", errors="coerce")
    d = d[d.DATE.notna() & (d.DATE.dt.year >= START)]
    m = {"3MON": "1Y", "1YR": "1Y", "5YR": "5Y", "10YR": "10Y", "30YR": "30Y"}
    return long(d, m, "JPY", "Japan MoF JGB yields")


def cad():
    m = {"3MON": "TB.CDN.90D.MID", "1YR": "TB.CDN.1Y.MID", "5YR": "BD.CDN.5YR.DQ.YLD",
         "10YR": "BD.CDN.10YR.DQ.YLD", "30YR": "BD.CDN.LONG.DQ.YLD"}
    sers = ",".join(m.values())
    p = get(f"https://www.bankofcanada.ca/valet/observations/{sers}/csv?start_date={START}-01-01", "boc_valet.csv")
    txt = p.read_text()
    body = txt[txt.index('"OBSERVATIONS"'):].split("\n", 1)[1]
    d = pd.read_csv(io.StringIO(body))
    d["DATE"] = pd.to_datetime(d["date"])
    return long(d, m, "CAD", "Bank of Canada Valet")


def aud():
    def rba(name, url):
        lines = get(url, name).read_text(encoding="utf-8-sig").splitlines()
        i = next(k for k, l in enumerate(lines) if l.startswith("Series ID"))
        d = pd.read_csv(io.StringIO("\n".join(lines[i:])))
        d = d.rename(columns={"Series ID": "DATE"})
        d["DATE"] = pd.to_datetime(d.DATE, format="%d-%b-%Y", errors="coerce")
        return d[d.DATE.notna()]
    f2 = rba("rba_f2.csv", "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv")
    f1 = rba("rba_f1.csv", "https://www.rba.gov.au/statistics/tables/csv/f1-data.csv")
    d = f2.merge(f1[["DATE", "FIRMMBAB90D"]], on="DATE", how="outer")
    d = d[d.DATE.dt.year >= START]
    m = {"3MON": "FIRMMBAB90D", "1YR": "FCMYGBAG2D", "5YR": "FCMYGBAG5D", "10YR": "FCMYGBAG10D",
         "30YR": "FCMYGBAG10D"}
    return long(d, m, "AUD", "RBA F1/F2")


def long(d, m, cur, src):
    rows = []
    for b, col in m.items():
        s = pd.to_numeric(d[col], errors="coerce")
        x = pd.DataFrame({"DATE": d.DATE.values, "Y": s.values}).dropna().sort_values("DATE")
        x["MONTH"] = x.DATE.dt.to_period("M")
        x = x.groupby("MONTH").last().reset_index()
        x["CUR"], x["BUCKET"], x["SOURCE"] = cur, b, f"{src} [{col}]"
        rows.append(x)
    return pd.concat(rows)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    out = pd.concat([fn() for fn in (usd, eur, gbp, jpy, cad, aud)])
    out["MONTH"] = out.MONTH.astype(str)
    out.to_parquet(OUT)
    print(out.groupby(["CUR", "BUCKET"]).agg(first=("MONTH", "min"), last=("MONTH", "max"), n=("Y", "size"),
                                             src=("SOURCE", "first")).to_string())


if __name__ == "__main__":
    main()
