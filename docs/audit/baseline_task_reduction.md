# D2T-RNA v7 — Baseline Task Reduction (P0, Batch 4.1)

> Status: `SOTA_NOT_ADJUDICATED`
> Purpose: record the reduction of every pre-registered potentially-comparable prior-art
> candidate to a same-task, same-metric executable comparison (or a concrete
> `NOT_COMPARABLE` reason). No candidate is dropped merely because it is hard to implement.

## 1. Frozen comparison contract

Any same-task reduction must run on the **frozen synthetic benchmark** under the corrected
Batch-2 metric/schema:

- estimand: exact two-class minimax decision error and separation measure over the registered
  product observation law;
- unit: registered action/cost cell on the frozen catalog pair grid; cells are NOT independent N;
- comparison metric identical across methods (no re-scaling, no per-method estimand re-definition);
- evidence bound to current HEAD and corrected certificate schema.

Until a fair external-SOTA reduction exists, the state is `SOTA_NOT_ADJUDICATED` (plan 4.1).

## 2. Internal baselines (already reduced + executed)

| Baseline | Same task | Same metric | Status |
|---|---|---|---|
| exhaustive_oracle | exact minimax decision | yes | REDUCED_EXECUTED |
| greedy_test_cover | costed test-subset selection | yes | REDUCED_EXECUTED |
| eig_design | expected-information design | yes | REDUCED_EXECUTED |
| chernoff_design | fixed-horizon KL allocation | yes | REDUCED_EXECUTED |
| lm2r_heuristic | RNA rational-design heuristic | yes | REDUCED_EXECUTED |

These are **executed model-conditional baselines**, not biological superiority evidence.

## 3. External prior-art candidates (not yet fair-reduced)

| Candidate | Basket | Reduction status / reason |
|---|---|---|
| Controlled Sensing for Multihypothesis Testing | B3 | NOT_COMPARABLE as-is: adaptive multihypothesis active sensing; no complete registered finite difference set, no replayable exact certificate; full text ACCESS_LIMITATION |
| Active Sequential Hypothesis Testing | B3 | NOT_COMPARABLE as-is: sequential; no complete registered D; ACCESS_LIMITATION |
| M2 / M2R | B4 | NOT_COMPARABLE as-is: RNA structure inference, different observation law/estimand; no decision certificate over complete D; ACCESS_LIMITATION |
| Markov-basis / fiber identifiability | B1 | NOT_COMPARABLE as-is: fiber connectivity criterion only; no decision/budget/no-go consequence |
| Bayesian / T-optimal / robust-T design | B3 | NOT_COMPARABLE as-is: EIG/optimality designs; no exact collision-or-separation certificate over complete D |
| Moret-Shapiro test cover | B2 | reduced to greedy_test_cover baseline (internal executable) |

`NOT_COMPARABLE` here means the candidate answers a different estimand / operates under a
different observation law, or its full text could not be obtained. These entries do NOT count
as adjudicated SOTA; SOTA remains `NOT_ADJUDICATED`.

## 4. Program-invariant check (20/20 pair access)

P0 also requires that all 20 catalog pairs are actually visited during benchmark construction
(no `theta_0[0] / theta_1[0]` single-pair shortcut). This is a **program invariant**, not a
scientific benchmark. See the Batch 2/conditional-Phase-1 implementation; the regression must
confirm all 20 pairs are enumerated.

## 5. Conclusion

- Same-metric internal baselines: REDUCED_EXECUTED.
- External SOTA: NOT fair-reduced -> `SOTA_NOT_ADJUDICATED`.
- No superiority / transfer claim is authorized on the real-data route (`REAL_DATA_ROUTE` gated).
