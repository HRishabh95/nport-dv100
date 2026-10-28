# N-PORT risk-metric outcome study: frozen protocol

**Question.** For funds whose rate risk is spread across currencies, does correctly interpreted
per-currency DV100 change the assessment of rate risk, measured against later returns, beyond
(A) a competent holdings-and-returns baseline and (B) the information the February 2026 proposal
would keep?

Frozen 2026-10-27, after the source audit (`AUDIT.md`) and before any fund return
(MONTHLY_TOTAL_RETURN, MONTHLY_RETURN_CAT_INSTRUMENT) has been read in this study. Market data
already read: month-end government yields (`fetch_yields.py`) and factor ETF price ranges. Changes
after this point are deviations, reported in `OUTCOME.md`.

## 1. Two problems kept apart

1. **Convention problem** (measured in `AUDIT.md`, without returns): signs and units differ across
   filers. Secondary analysis 7.2 reports how much raw, uncleaned data would mislead.
2. **Information-loss problem** (this study): after identical cleaning, does currency detail add
   anything? Both B and C come from the same harmonised records. B is the aggregate of C's cleaned
   legs, which is what a USD-mandated, correctly signed proposal filing would contain. No cleaning
   step uses returns.

## 2. Records and cleaning

- Unit: one public N-PORT report per fund (series) per data-set quarter (`extract.py`), 2019q4-2026q3.
- Harmonised per-currency, per-bucket DV100: reported x SIGN_D1 (`audit/fund_quarters.parquet`:
  +1 for R, -1 for F). Legs flagged LOCAL_UNITS are divided by the exchange rate. Target meaning:
  USD value change for a +100 bp parallel rise in that currency and bucket.
- A record is usable only if STATUS_D1 is not UNRESOLVED. Unresolved records are excluded from A, B
  and C alike, so all three are evaluated on the same fund-months.
- Share classes: N-PORT is filed per series, which is one portfolio. The fund-month return is the
  median of the class returns reported for that month.
- Duplicate fund-months (amendments, or the same month reported in two filings): keep the latest
  FILING_DATE.

## 3. Information availability

- A record becomes available at FILING_DATE. Under the current rules the third-month report "will be
  made public upon filing (i.e., no later than 60 days after fiscal quarter end)" (IC-35962, Table 1).
- **Primary (implementable):** for month m, use the most recent usable record with FILING_DATE
  strictly before the first day of m and REPORT_DATE no more than 9 months before the end of m.
  Holdings for approach A come from that same record, never from a later one.
- Sensitivity 7.3: available at max(FILING_DATE, REPORT_DATE + 60 days).
- Secondary 7.4 (decomposition, not implementable): apply the record to the month after its
  REPORT_DATE.

## 4. Rate changes and exposure

- Delta y_{c,b,m} = 100 x (month-end yield in m minus month-end yield in m-1), in bp, from
  `data/interim/nport_risk_value/yields_monthly.parquet` (series named there):
  - USD: Treasury par curve.
  - EUR: ECB AAA spot curve.
  - GBP: BoE nominal spot curve (0.5y stands in for 3 months).
  - JPY: MoF JGB yields (1y stands in for 3 months).
  - CAD: Bank of Canada Valet.
  - AUD: RBA (2y stands in for 1y; 10y for 30y).
  - Missing month-ends are carried from the previous month-end, at most one month.
- Rate P&L, % of NAV: P = 100 x sum_{c,b} E_{c,b} x Delta y_{c,b,m} / 100 / NAV, where E is an
  exposure vector in USD per 100 bp. This is linear in yields and has no convexity term (a stated
  approximation). Buckets are treated as key-rate exposures, as the form's linear-interpolation
  instruction implies.
- **Unmapped currencies** (no yield series): their exposure is priced at the fund's mix change
  Delta y^mix_{f,b,m}. That is the average of mapped currencies' Delta y_{c,b,m}, weighted by
  |A_{c,b}| from the same record. If A has no mapped exposure in bucket b, USD is used. The mix
  depends only on holdings, so it is identical for B and C.

## 5. The three information sets (per record)

- **A, holdings baseline.**
  - E^A_{c,b} is the holdings estimate of `gates.py` (v2 futures table), allocated to buckets by
    each position's maturity, with linear interpolation between 0.25, 1, 5, 10 and 30 years. Below
    0.25 years goes to 3 months; above 30 years goes to 30 years.
  - Futures use these maturity equivalents: duration 0.25 -> 0.25y; 1.9 -> 2; 2.8 -> 3; 4.2 or
    4.3 -> 5; 6.5 to 9 -> 10; 11.5 -> 20; 17 or 20 -> 30.
  - Swaps use their termination date.
- **B, proposal-equivalent.**
  - The aggregate per bucket is B_b = sum_c E^C_{c,b}. The holdings profile is kept, and the part of
    the reported aggregate that holdings do not explain is put on the mix:
    E^B_{c,b} = E^A_{c,b} for mapped c, plus (B_b - sum_c E^A_{c,b}) priced at Delta y^mix_{f,b}.
  - This operationalises the SEC's stated method, which uses "the currency denomination of each
    portfolio holding ... in conjunction with the aggregate DV100".
  - Sensitivity 7.6: B priced on the mix only, with no holdings profile.
- **C, full.** E^C_{c,b} = harmonised reported DV100 per currency and bucket. Unmapped legs are
  priced at the mix.
- DV01 is not used by any approach. Removing DV01 is not tested.

## 6. Primary test

**Common return model.** Run separately for each approach k in {A, B, C}, with the same regressors.
- For fund f and month m, take the residual return y^k_{f,s} = r_{f,s} - P^k_{f,s}, for s in the
  36 months before m (at least 24 months with a usable record).
- Regress it by OLS on:
  - the ACWI price return;
  - the credit return: HYG minus 0.8 x IEI price return;
  - the fund's FX return: sum_c w_{f,c} x FX return of c against USD, where w_{f,c} is non-USD
    holdings value plus net FX forward/swap amounts in c, over NAV, from the same record as P. FX
    month-end rates are the median EXCHANGE_RATE in N-PORT holdings with that REPORT_DATE
    (>= 20 rows). Otherwise the return is 0.
  - Delta y USD 10y;
  - the equal-weighted Delta y 10y of EUR, GBP, JPY, CAD and AUD.
- Factor returns come from `data/interim/daily_bars.parquet`, last close of each month.
- So all three approaches get the same competent returns-based model, including returns-based rate
  betas. They differ only in which exposure is taken at face value.
- **Forecast:** r_hat^k_{f,m} = P^k_{f,m} + a^k + b^k' X_m. **Error:** e^k_{f,m} = r_{f,m} - r_hat^k_{f,m}.
- **Evaluation sample:** fund-months where all of the following hold:
  - all three approaches have a forecast, and all are based on the same record;
  - |r| <= 25%;
  - the record is PRIMARY: O_c >= 0.20 and non-USD share >= 0.10, both on harmonised legs.

**Primary statistic: the encompassing slope.**
  theta = sum (e^B x D) / sum D^2,  where D = P^C - P^B
over confirmation-sample PRIMARY fund-months, giving each fund-month equal weight.
- theta = 1: the currency detail C adds over B is fully borne out by returns.
- theta = 0: it is unrelated to returns.
- theta < 0: it points the wrong way.

**Uncertainty.** Two bootstraps, 2,000 draws each: (i) resample calendar months, so all fund-months
of a month move together (common shocks); (ii) resample fund families. The decision uses the more
conservative interval: the lower of the two 2.5% bounds and the higher of the two 97.5% bounds.

**Market periods:** 2022, 2023, 2024, and 2025-01 to 2026-07. theta is reported for each.

**Decision.**
- **CURRENCY DETAIL CHANGES RISK ASSESSMENT** if all of the following hold:
  - theta >= 0.5;
  - the conservative lower bound is above 0;
  - theta > 0 in at least 3 of the 4 periods;
  - the pooled RMS of D is at least 10 bp of NAV per month.
- **DOES NOT** if the conservative upper bound is below 0.5, or if RMS(D) is below 5 bp a month.
- **INCONCLUSIVE** otherwise.

Also reported with the decision: MSE of A, B and C; 1 - MSE_C/MSE_B and 1 - MSE_B/MSE_A, with the
same bootstraps; theta_AB = sum(e^A x (P^B - P^A)) / sum (P^B - P^A)^2, which asks whether the
retained aggregate adds to holdings.

## 7. Secondary analyses (reported in full, no gate)

1. **Broad population:** usable records with non-USD debt holdings >= 10% of debt value. This
   population is defined from holdings alone, so a B user could form it.
2. **Raw data:**
   - B_raw and C_raw are built from unharmonised signs and units.
   - Report MSE and theta for A, B_raw, C_raw, B and C.
   - This measures what the convention problem costs a face-value user. It is not used to set any
     sign.
3. **Availability at max(FILING_DATE, REPORT_DATE + 60 days).**
4. **Decomposition timing** (not implementable).
5. **Weighting and coverage:** family-equal weights; also excluding PARTIAL_COVERAGE records and
   records with converted legs.
6. **B priced on the mix only.**
7. **Placebo:** C with Delta y currency labels permuted across mapped currencies within each month,
   using fixed seed 20261027. Expected theta near 0.
8. **Pair illustration** (frozen rule, descriptive):
   - For each confirmation quarter, form all pairs of PRIMARY funds from different families.
   - Compute the predicted correlation of rate P&L under B and under C, using the covariance of
     mapped Delta y over the previous 60 months.
   - Classify each pair: offsetting below -0.3, similar above +0.3, else neutral.
   - Report the share of pairs whose class differs between B and C. For those pairs, report whether
     the realised correlation of e^A over the next 12 months has the sign of C's or of B's
     prediction.
   - Chart: raw -> harmonised -> proposal-equivalent for the 3 pairs with the largest
     |corr_C - corr_B|.
9. **Same test on the 2026q2-2026q3 records** (inspected earlier): reported separately, never pooled
   with confirmation.

## 8. Samples

- **Family:** primary investment adviser CRD from N-CEN (latest at or before the record's quarter);
  fallback "CIK" + registrant CIK.
- **Development sample:** families whose sha256(family key) begins with 0-4 (5/16). It is used to
  debug code and check data integrity. Results are reported but carry no claim.
- **Confirmation sample:** all other families, excluding:
  - every record from data sets 2026q2 and 2026q3 (inspected in `CHECK.md`);
  - all records of every fund in the S6 sample (`audit/s6_sample.csv`);
  - all records of the funds named in `CHECK.md`: Eaton Vance Global Macro Absolute Return
    Advantage Portfolio, BlackRock Tactical Opportunities Fund, Campbell Systematic Macro Fund,
    T. Rowe Price Dynamic Global Bond Fund, Transamerica JPMorgan Asset Allocation - Moderate VP,
    PIMCO Long Duration Credit Bond Portfolio, JPMorgan Strategic Income Opportunities Fund and
    American Funds Inflation Linked Bond Fund. These are matched by exact series name.
- **Order of runs:** development first. Any definition change after development is a deviation.
  Confirmation runs once.

## 9. Limits stated in advance

- DV100 is a linear, parallel-by-bucket approximation, with no convexity and no basis or spread terms.
- Positions are 1-9 months stale under the implementable timing. Fast-trading macro funds will look
  worse for every approach.
- Six currencies have yields. The others are priced at the mix, identically for B and C, so C's
  advantage is understated where unmapped currencies matter.
- Factor ETF returns are price returns without distributions. This affects the intercepts, not
  the slopes.
- A result for this population does not speak to the threshold change (25% -> 50%), the IG/non-IG
  merge or the DV01 removal.
