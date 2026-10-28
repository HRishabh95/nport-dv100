# Independent check of inferred sign conventions (frozen 2026-10-28, before running)

**Why.** `AUDIT.md` assigns a convention to non-plain funds from the majority of their plain siblings
in the same registrant-quarter or adviser-quarter. That inference was validated only on plain
funds, by leave-one-out. This check tests it on the records where it was actually used, with
evidence the inference did not use: each fund's own holdings, currency by currency. No returns are
used.

## Population

Records with STATUS_D1 not UNRESOLVED and CONV_RULE in {registrant, adviser}, i.e. the convention
was inferred rather than read from the record itself.

## Qualifying legs

A qualifying leg is a (record, currency) pair from `audit/legs.parquet` where all of the following
hold:
- UNIT is not UNIT_UNRESOLVED;
- the holdings estimate |EST_C| >= 0.25% of NAV;
- the reported |DV100| >= 0.25% of NAV, after converting LOCAL_UNITS legs.

## Statistics

- **Agreement:** sign(reported DV100 x SIGN_D1) == sign(EST_C).
- **Weighted agreement:** agreement weighted by |EST_C| (primary), and also unweighted.
- **Reported:**
  - overall;
  - separately for inferred-R and inferred-F records;
  - by rule (registrant, adviser);
  - by family (`CRD` adviser, else registrant CIK).
- **Benchmark (same statistic, not used for any decision):** non-plain records whose convention came
  from their own plain evidence do not exist by construction. The benchmark is therefore the
  agreement on legs of records COMPARABLE_AS_FILED that are not plain.

## Decision

- **CONFIRMED** if the primary weighted agreement is >= 0.80 overall and >= 0.75 within both
  inferred-R and inferred-F.
- **NOT CONFIRMED** if the overall weighted agreement is < 0.65, or either group is < 0.60.
- **MIXED** otherwise.

## Families flagged for disclosure

Any family with >= 5 qualifying legs and weighted agreement < 0.50 is listed by name. A sensitivity
reclassifies its inferred records as UNRESOLVED, and the census headline (share positive, pair flip
rates) and the 7.2 convention-cost numbers are recomputed without them.

The holdings estimate is itself noisy for derivatives-heavy funds; agreement well below 1 is
expected even when the convention is right. The check is whether agreement is far above the 0.5 a
wrong convention would produce on average (a wrong convention gives 1 - agreement).
