# N-PORT risk-metric source audit: frozen protocol

Purpose: establish what the reported Item B.3 interest-rate numbers mean (direction of the rate move,
signed change vs loss magnitude, currency units) from the form, the filings and contemporaneous
holdings, before any return data is opened. Returns are not used anywhere in this audit. Records
whose meaning cannot be established stay UNRESOLVED; they are never resolved by fit to later returns.

Frozen 2026-10-27, before the audit was run on 2019q4-2026q1. The 2026q2-2026q3 risk fields were
already inspected in `CHECK.md`. Changes after this point are reported as deviations in `AUDIT.md`.

## Documentary evidence (already read)

- Form N-PORT Item B.3.a/b (current form, `ref/formn-port.txt` lines 254-261; identical text in the
  2016 adopting release 33-10231, `ref/33-10231.txt` line 25488): "the change in value of the
  portfolio resulting from a 1 [100] basis point change in interest rates". No direction is given.
  Item B.3 has no "Report in U.S. dollars" instruction, whereas Items B.2, B.5 and C.2 do, and B.5
  says losses are negative. The adopting release's DV01/DV100 discussion gives no direction either.
- Proposal IC-35962 pp. 41-42: proposes "report in U.S. dollars" and says some funds report risk
  metrics in non-USD currencies. It does not address sign.
- So a positive DV100 for a long-only bond fund is a permitted reading of the form, not by itself
  a misreport. The audit measures conventions; it does not label filers as wrong.

## Data

All 28 N-PORT data-set quarters on disk (2019q4-2026q3), extracted by `extract.py` (one public report
per fund per data-set quarter, same keys as PROTOCOL.md). Cleaning rules 1-4 of PROTOCOL.md apply
first; their exclusions are counted as UNRESOLVED (reason: cleaning). Holdings-based estimates use
the v2 futures table in `gates.py` (`NRV_V2=1`), the same duration formulas, unchanged.

## Step S1: plain-fund evidence

A clean fund-quarter is PLAIN if all hold:
- debt holdings value >= 50% of NAV;
- interest-rate futures + fixed/floating swap |notional| (USD) < 5% of debt holdings value;
- debt holdings with PAYOFF_PROFILE Short < 1% of debt holdings value;
- holdings-estimated net DV100 is negative and |estimate| >= 0.5% of NAV.

For a PLAIN fund-quarter the true value change for a rate rise is negative. Reported net DV100
(sum over currencies and buckets) is classified:
- R (rise, signed change): reported net < 0.
- F (positive for a long bond fund): reported net > 0.
- Z: reported net = 0 (unresolved).
Magnitude check: m = |reported net| / |estimate|. m outside [1/3, 3] is recorded as MAG (scale or
units problem); MAG fund-quarters are not used as convention evidence.

Direction test (only where both DV01 and DV100 are reported non-zero, MBS < 20% of debt value):
k = |sum DV100| / (100 x |sum DV01|).
- k < 0.995: the 100 bp number is smaller than linear: consistent with a +100 bp shock.
- k > 1.005: larger than linear: consistent with a -100 bp shock.
- otherwise LINEAR (DV100 computed as 100 x DV01; direction not identified).
Combined with the sign: R & k<0.995 = "value change for +100 bp"; F & k>1.005 = "value change for
-100 bp"; F & k<0.995 = "loss magnitude for +100 bp"; R & k>1.005 = ANOMALY (unresolved).

## Step S2: within-filing consistency (all clean fund-quarters)

DV01 and DV100 for the same currency and bucket must have the same sign under any single convention.
Share of gross |DV100| on cells where both are non-zero and signs disagree: if >= 5% the fund-quarter
is INTERNAL_MIXED (unresolved).

## Step S3: convention inference for non-plain fund-quarters

Convention C in {R, F} for a fund-quarter, first rule that applies:
1. Own: the fund-quarter is PLAIN with class R or F (not MAG).
2. Registrant-quarter: same registrant CIK, same data-set quarter, >= 2 other PLAIN non-MAG
   fund-quarters, >= 90% agreeing.
3. Adviser-quarter: same primary adviser (N-CEN, ADVISER_TYPE "Advisor", CRD number; latest N-CEN
   quarter at or before the data-set quarter), same data-set quarter, >= 2 other PLAIN non-MAG
   fund-quarters, >= 90% agreeing.
4. Otherwise UNRESOLVED (reason: no convention evidence). A conflict between rule 1 and rule 2 is
   resolved by rule 1 and counted.

Validation (decides whether rules 2-3 may be used at all): leave-one-out on PLAIN non-MAG
fund-quarters. Predict each one's class from rule 2 (then 3) excluding itself; report coverage and
accuracy. Rules 2-3 are ACCEPTED only if accuracy >= 0.95 on >= 200 predicted fund-quarters;
if not, only rule 1 is used and all non-plain fund-quarters are UNRESOLVED.

## Step S4: currency units (per reported non-USD currency leg)

For legs where the holdings estimate for that currency is non-zero: r = |reported_c| / |estimate_c|,
X = data-set median exchange rate (units per USD).
- LOCAL_UNITS if X >= 20 and r in [X/4, 4X] and r >= 5: the leg is converted by dividing by X.
- UNIT_UNRESOLVED if r > 20 and not LOCAL_UNITS. A fund-quarter with UNIT_UNRESOLVED legs worth
  >= 10% of its gross is unresolved (reason: units).
Currencies with X < 20 (EUR, GBP, CHF, AUD, CAD, ...) cannot be tested this way; stated as a limit.

## Step S5: explanatory notes

All EXPLANATORY_NOTE rows with ITEM_NO starting "B.3" are tagged by keyword: COVERAGE (excludes /
does not consider / not included / look through), CONVENTION (increase / decrease / rise / fall /
shift / positive / negative / parallel), CURRENCY (currency / CNH / converted / U.S. dollar), OTHER.
CONVENTION notes are read in full and their statement compared with the S1-S3 class. COVERAGE notes
mark the fund-quarter PARTIAL_COVERAGE (kept; a limitation, used as a sensitivity in the outcome
study).

## Step S6: original-filing check (15-20 filings)

Selected by rule, after S1-S5 have run, before anything else is looked at: within each stratum, the
fund-quarters with the smallest sha256(ACCESSION_NUMBER), from data-set quarters 2019q4-2026q1:
(a) 5 PLAIN R; (b) 5 PLAIN F; (c) 5 non-plain multi-currency fund-quarters with O_c >= 0.20 and
non-USD share >= 0.10 whose convention comes from rule 2 or 3; (d) up to 5 with a LOCAL_UNITS or
UNIT_UNRESOLVED leg. For each: open the original primary_doc.xml on EDGAR; check every DV01/DV100
cell and currency code against the bulk data (match = equal to 6 significant figures); read all
explanatory notes. Record mismatches. Every fund in this sample is listed in `AUDIT.md` as INSPECTED
and is excluded from any confirmation sample.

## Outputs (`AUDIT.md`, `data/interim/nport_risk_value/audit/`)

Per fund-quarter: convention class and rule, direction evidence, unit flags, coverage tag, final
status in {COMPARABLE_AS_FILED, COMPARABLE_AFTER_TRANSFORM (flip and/or unit conversion, with the
evidence rule), UNRESOLVED (reason)}. Reported shares by count and NAV, by quarter, overall and for
multi-currency offset fund-quarters.

Harmonised value = reported x (+1 if R, -1 if F), legs in LOCAL_UNITS divided by X. This targets
"value change for a +100 bp parallel rise in that currency and bucket". For F records that are
value changes for -100 bp, the flip ignores convexity asymmetry (about 1-5% of the number for plain
bond funds); stated as a limit.

Descriptive consequence (no gate): among pairs of PLAIN fund-quarters in the same data-set quarter
from different registrants, the share whose raw reported net DV100s have opposite signs (they appear
to offset) versus the share after harmonisation.
