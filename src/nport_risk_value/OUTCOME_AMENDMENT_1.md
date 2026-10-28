# Amendment 1 to the outcome protocol (2026-10-28)

`OUTCOME_PROTOCOL.md` is unchanged and still hashes to `fe1c473e...a2b213e`
(`data/interim/nport_risk_value/OUTCOME_PROTOCOL_SHA256`). This amendment was written on 2026-10-28,
after a methodological review and before any fund return (MONTHLY_TOTAL_RETURN,
MONTHLY_RETURN_CAT_INSTRUMENT) had been read. Its sha256 is in
`data/interim/nport_risk_value/OUTCOME_AMENDMENT_1_SHA256`. Where it conflicts with the protocol, the
amendment applies. Every result in `OUTCOME.md` names the version it uses.

## M1. theta measures incremental calibration, not lower forecast error

Approach k refits its own intercept and factor coefficients on y^k = r - P^k. So the error difference
is not D:
- e^B - e^C = D + (F^C - F^B), where F^k = a^k + b^k' X_m is the fitted factor part and D = P^C - P^B.
- Write Dt = e^B - e^C. Then MSE_B - MSE_C = 2 sum(e^B Dt) - sum(Dt^2), so
  **MSE_C < MSE_B exactly when thetat = sum(e^B Dt) / sum(Dt^2) > 1/2.**
- The frozen theta uses D, not Dt. When D is correlated with the common rate factors, the refit
  absorbs part of D (F^C - F^B is about -b_D' X_m). theta can then be large while Dt, the part that
  actually changes the prediction, is small or unrelated to e^B.
- **Passing theta therefore does not imply MSE_C < MSE_B.** Without refits (Dt = D), theta = 0.5 is the
  break-even point; with refits there is no fixed link in either direction.

What changes:
- The frozen theta rule stays the decision gate, unchanged.
- The verdict is labelled an **incremental-calibration (encompassing) result**: it asks whether the
  part of C's rate P&L that B lacks is borne out in returns.
- Reported alongside, with the same two bootstraps, the conservative interval and the four periods:
  - **forecast-error improvement** dMSE_CB = 1 - MSE_C / MSE_B;
  - thetat;
  - the share of var(D) absorbed by the refit, 1 - var(Dt) / var(D).
- Wording rule:
  - "C reduces prediction error relative to B" may be written only if the conservative lower bound
    of dMSE_CB is above 0.
  - If theta passes and dMSE_CB does not, the claim is limited to: "currency detail carries
    information about returns that the proposal-equivalent set lacks, but the full-weight
    per-currency model does not measurably reduce prediction error."
- The same applies to theta_AB and dMSE_BA.

## M2. The test is conditional on realised shocks

- r_hat^k_{f,m} uses the factor returns and yield changes realised in month m itself (X_m and
  Delta y_m). It is a **conditional prediction**: do exposures disclosed before m explain returns in m,
  given what markets did in m? It is not an ex-ante return forecast and not a tradable signal.
- `OUTCOME.md` uses "conditional prediction" and "prediction error" throughout, not "forecast".
- Stated, not changed: the 36-month estimation window can include fund returns for months whose
  N-PORT report was not yet public at the start of m (up to about five months of lag). This is
  identical for A, B and C. Information availability (protocol section 3) governs the exposure
  records only.

## M3. The FX-return source is replaced

**Audit** (`fx_coverage.py`, outputs in `data/interim/nport_risk_value/fx/`). The rule tested is the
frozen one: the month-end rate is the median N-PORT EXCHANGE_RATE among holdings with that
REPORT_DATE (>= 20 rows); otherwise the return is 0. Results over 2019-10 to 2026-09, for the 72
currencies held by PRIMARY-flagged records:

| | Value |
|---|---|
| Currency-month cells | 6,048 |
| Cells defaulted to zero | 2,817 (46.6%) |
| Weighted by PRIMARY non-USD holdings value | 6.1% defaulted to zero |
| Main currencies (EUR, GBP, JPY, BRL, MXN, CAD, ZAR, AUD, ...) | 82 of 84 months |
| The two missing months | 2026-08 and 2026-09, both after the evaluation window |
| Months with defaults inside the window | thin currencies: ARS 54%, RSD 92%, EGP 14% |

Coverage alone is adequate. **Quality is not.** Against ECB end-of-month reference rates (33
currencies, 2,365 currency-months):
- The median absolute difference in monthly returns is 27 bp, rising to 376 bp at the 99th
  percentile.
- CAD's monthly returns correlate 0.06 with the ECB's. Several month-end medians are 1.00 or 0.75
  against an ECB rate of 1.35, because filers quote the rate in both directions.
- ARS diverges by 18-64% in individual months, because filers use different rates.
- BRL differs by up to 4%.

A factor with spikes of 38-80% in single months is not a usable control.

**Replacement (applies to the primary test and all secondaries):**
- Source: ECB euro foreign exchange reference rates, monthly end-of-period, series
  `EXR.M.{CUR}.EUR.SP00.E`, all currencies (`data/raw/fx/ecb_exr_monthly_eop.csv`, retrieved
  2026-10-28 from data-api.ecb.europa.eu, the API already used for EUR yields).
- Conversion: X_{c,m} = (c per EUR) / (USD per EUR) is units of c per USD, and X_{EUR,m} =
  1 / (USD per EUR). The USD return of holding c in month m is X_{c,m-1} / X_{c,m} - 1.
- Coverage: the ECB publishes 37 currencies. They cover 93.4% of PRIMARY non-USD holdings value. For
  a currency-month the ECB does not publish (for example PEN, COP, RSD, CLP; ARS, EGP and TWD after
  October 2020; RUB after March 2022), the FX return is 0. The exposure share defaulted to 0 is reported.
- Net FX forward and swap amounts (`FWD_FOREIGNCUR_CONTRACT_SWAP`) are converted to USD at the ECB
  rate for the record's REPORT_DATE month. Where the ECB has no rate, the data-set median N-PORT rate
  (`extract/{q}_fx.parquet`, as used by `gates.py`) is used.
- Futures and swap notionals inside approach A keep the `gates.py` conversion.
- **Sensitivity 7.10 (new):** the primary test with the frozen N-PORT FX factor, reported in full.

## M4. Corrected statement on ETF distributions

The protocol's section 9 says omitted distributions affect "the intercepts, not the slopes". That is
true only if distributions are constant. They are not:
- ACWI pays twice a year, so the price return understates the total return in ex-dividend months
  only.
- HYG and IEI pay monthly, in amounts that move with yields (higher in 2023-25 than in 2021).
- The time-varying part is measurement error in the regressors. It attenuates their slopes,
  leaves some return in the residual, and the slow drift is partly absorbed by the rolling
  intercept.

No distribution data are on disk, so the size is not measured here. The usual size of these payouts
relative to monthly price volatility suggests the effect is small. That is an expectation, not a
result. The error is identical in A, B and C, because the regressors are shared. Factor returns stay
price returns; the specification is not changed. `OUTCOME.md` states this corrected limitation.

## M5. Implementation clarifications, fixed before reading returns

Each applies identically to A, B and C, or to the evaluation sample as a whole.

1. **Records.** For month m, the record is chosen from those with FILING_DATE strictly before the
   first day of m and REPORT_DATE within 9 months: take the latest REPORT_DATE, then the latest
   FILING_DATE.
2. **Returns.**
   - MONTHLY_TOTAL_RETURN1, 2 and 3 are the returns of REPORT_DATE month -2, -1 and 0, in percent.
   - The fund-month return is the median across classes within a filing.
   - When several filings of the same FUND_KEY give the same month, the one with the latest
     FILING_DATE is kept.
3. **Estimation window.** The |r| <= 25% filter also applies to estimation months, not only to
   evaluated months, to keep data errors out. An estimation month needs a record that was available
   under the primary timing rule.
4. **Bucket allocation in A.**
   - Floating-rate debt is bucketed at min(T, 0.25 years), its reset horizon, consistent with the
     duration of 0.25 already assigned to it.
   - MBS debt is bucketed at the maturity of a par fixed-rate bond whose duration equals its capped
     duration, so a 30-year MBS with duration 6 is not placed at 30 years.
   - All other positions use final maturity, as frozen.
   - Estimated totals are unchanged; only their split across buckets changes.
5. **Missing yields.** A (currency, bucket, month) cell still missing after the one-month carry is
   priced at the mix for that month, as if the currency were unmapped. It is excluded from the mix
   weights. The case affects the BoE 0.5-year yield, which has 25 missing months.
6. **PRIMARY and the offset measures.** O_c = 1 - |sum_c N_c| / sum_c |N_c| and non-USD share =
   sum_{c != USD} |N_c| / sum_c |N_c|. Here N_c is the harmonised net DV100 of currency c (summed
   over buckets, unit-converted), with the same definitions as `gates.py`.
7. **FX weights.**
   - w_{f,c} = (USD value of holdings with currency c, plus USD value of FX forward/swap amounts
     purchased in c, minus those sold in c) / NAV, for c not equal to USD.
   - Blank and "N/A" currencies are dropped.
8. **Pair illustration (7.8).** The realised correlation needs at least 8 common months of e^A
   among the next 12.

## M6. Order of work

1. Build `outcome.py` and run the development sample (5/16 of families).
2. Development results are for debugging and integrity checks. If they lead to any change, the change
   is listed in `OUTCOME.md` as a post-development deviation, together with the development numbers
   it followed. No change may be chosen because it moves theta or dMSE.
3. Run confirmation once. All frozen gates and both amendments' rules are reported, including any
   that are unfavourable.
