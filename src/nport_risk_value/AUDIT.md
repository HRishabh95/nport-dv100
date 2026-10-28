# N-PORT risk-metric source audit: result

Protocol: `AUDIT_PROTOCOL.md`, sha256 `7c51d52c...202447f4` (`data/interim/nport_risk_value/AUDIT_PROTOCOL_SHA256`),
frozen before the audit was run. Code: `audit.py` (S1-S5), `audit_s6.py` (S6). Outputs:
`data/interim/nport_risk_value/audit/` (`fund_quarters.parquet`, `legs.parquet`, `notes.parquet`,
`audit.json` = frozen-rule summary, `audit_d1.json` = with deviation D1, `s6_*`). No return data was read.

Scope: all 28 data-set quarters (2019q4-2026q3), 105,416 fund-quarters with Item B.3 rate fields,
6,073 funds.

## What the documents say

- Form N-PORT Item B.3.a/b asks for "the change in value of the portfolio resulting from a 1 [100]
  basis point change in interest rates". It gives no direction, and unlike Items B.2, B.5 and C.2 it
  does not say "Report in U.S. dollars". The 2016 adopting release (33-10231) adds neither.
- The February 2026 proposal (IC-35962, pp. 41-42) would add "report in U.S. dollars" because some
  funds report in other currencies. It does not address sign.
- I found no SEC staff FAQ on the point (two searches; the FAQ URL tried returned 404).
- So both readings of the sign comply with the form. What follows measures conventions; it does not
  say any filer reported wrongly.

## Main result: two sign conventions, each used by about half the industry

| | Value |
|---|---|
| Plain long-only bond fund-quarters (true value change for a rate rise is negative) | 53,603 |
| ... reporting negative DV100 (R) | 27,868 (52%) |
| ... reporting positive DV100 (F) | 25,735 (48%) |
| F share by quarter | 43%-50% in every quarter, no trend |
| Registrant-quarters with >= 3 plain funds that are unanimous | 99.0% of 4,844 |
| Leave-one-out: plain fund's convention predicted from its registrant / adviser peers | 99.8% correct (41,074 predicted; registrant 99.9%, adviser 99.2%) |
| Registrants that switched convention at some point | 113 of 1,096 |

The convention is a fund-complex choice, almost certainly the risk system's. F (positive for a long
bond) includes iShares Trust, Fidelity, PIMCO, Northern, Legg Mason, DoubleLine, Schwab, Principal,
MassMutual. R (negative) includes DFA, SPDR, Invesco, Franklin, Eaton Vance, MFS, JNL, Transamerica.

What the positive numbers mean, from the filings' own evidence:
- Only two complexes state it in explanatory notes. MassMutual: DV01 is "the average change in a
  security's market value ... given both up and down ... basis point shifts", i.e. an effective
  duration magnitude. Ellington: "the change in value for a 100 bp decrease in interest rates".
  Both are classified F by the inference rule, consistent with their notes.
- DV100 / (100 x DV01): F filers have a median of exactly 1.000 (66% are linear). Most F filers
  scale DV01 by 100 rather than revaluing at 100 bp, so their DV100 carries no convexity
  information. Among R filers, non-municipal funds split 44% below linear (positive convexity, a
  +100 bp shock) and 35% above. Municipal funds are 76% above linear, consistent with the negative
  convexity of callable bonds.
- Fewer than 1% of fund-quarters say anything about the convention. Of the 2,124 Item B.3 notes,
  1,319 match convention words, nearly all MassMutual boilerplate.

Consequence for comparisons across funds: among 133 million cross-registrant pairs of resolved
fund-quarters, **50.2% have raw net DV100s of opposite sign, so summing them as filed shows one fund
hedging the other's rate risk. After harmonising signs, 3.4% do.** Within a single filing the
convention is consistent, so a fund's own cross-currency offsets survive harmonisation.

## Units

- 493 non-USD legs are reported in local currency: the reported/estimated ratio equals the exchange
  rate within a factor of 4 (JPY 386, KRW 32, MXN 20, CZK 13, THB 12, INR 10). These are converted.
  In the S6 sample the ratios were 206/136, 219/142 and 156/149 for JPY, and 1,498/1,377 and
  1,339/1,336 for KRW.
- 676 legs have ratios above 20 that do not match the exchange rate (UNIT_UNRESOLVED). 148
  fund-quarters are unresolved for this reason.
- Units cannot be tested for currencies trading near 1 USD (EUR, GBP, CHF, AUD, CAD).

## Original filings (S6): bulk data set matches the XML

19 filings were selected by rule (smallest sha256 of accession within each stratum, data sets
2019q4-2026q1): 5 plain R, 5 plain F, 5 multi-currency with inferred convention, 5 with unit flags,
one filing in two strata. **All 950 DV01/DV100 cells and all currency codes match the bulk data
exactly.** None of the 19 has an Item B.3 explanatory note. JPMorgan Diversified Fund (2020q3)
reports DV01 and DV100 with opposite signs on 97% of its gross exposure, which leaves it
INTERNAL_MIXED (unresolved).

## Status of every fund-quarter (with deviation D1)

| | All fund-quarters | Multi-currency offset (O_c >= 0.20, non-USD >= 10%) |
|---|---|---|
| n | 105,416 | 2,566 (435 funds) |
| Comparable as filed (R, USD) | 41.8% (50.3% of NAV) | 33.1% (20.3% of NAV) |
| Comparable after a supported transformation (sign flip and/or unit conversion) | 40.1% (36.4% of NAV) | 35.9% (65.5% of NAV) |
| Unresolved | 18.2% (13.4% of NAV) | 31.1% (14.2% of NAV) |
| ... no convention evidence (no plain sibling in registrant or adviser) | 15,442 | 620 |
| ... DV01 and DV100 signs disagree within the filing (>= 5% of gross) | 2,131 | 106 |
| ... cleaning (DV100/DV01 ratio, gross > 0.5 NAV, NAV) | 1,419 | 0 |
| ... units | 148 | 71 |

So **58% of fund-quarters, and half of NAV, cannot be compared with others as filed**, and 18%
(13% of NAV) cannot be made comparable from the filings and contemporaneous holdings alone. In the
multi-currency funds the proposal affects, 80% of NAV needs interpretation before comparison.

## Deviation D1 (after the result, labelled)

The frozen rule left R fund-quarters with DV100 above linear (k > 1.005) UNRESOLVED as "anomaly"
(12,703 fund-quarters). The distribution shows this is the negative convexity of callable bonds
(76% of municipal R funds versus 35% of others), not evidence of a different convention. D1 keeps
them as R. The frozen-rule numbers are in `audit.json`: 30.2% unresolved by count, 21.1% by NAV.
D1 does not touch any multi-currency offset fund-quarter (6 anomalies there; they become resolved).

## Limits

- Plain-fund classification uses a simple holdings duration model. It only needs the sign of a
  long-only bond book, which is robust; magnitude agreement is median 0.81 with 4.5% outside [1/3, 3].
- The convention of a non-plain fund is inferred from plain siblings in the same registrant or
  adviser and quarter. That is validated at 99.8% on plain funds, but a complex could in principle
  use a different system for derivatives-heavy funds. Nothing in the 19 filings suggests it.
- For F records that measure a -100 bp move, the flip ignores convexity asymmetry (about 1-5% of the
  number for plain bond funds).
