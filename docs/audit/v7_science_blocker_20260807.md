# v7 Science Blocker Audit — P0-1 snapshot & strong-claim freeze

Audit date: 2026-08-07 (Asia/Shanghai)
Snapshot HEAD: `5772eca00d5323e908183a9cbac61cdbd92a669f` (branch `main`)
Audit basis: read-only code/data/artifact/test-log/paper inspection. No contract/code/data modified; no training or formal experiment started; no process terminated.

## State

```text
ENGINEERING_LINEAGE:            PASS_FOR_TASK5_ONLY
V7_ACTIVATION_DECISION:         RECORDED_BUT_FILE_BINDING_INCOMPLETE
T2B_CENTRAL_CLAIM:              BLOCKED_WITH_COUNTEREXAMPLE
T2C_RISK_CLAIM:                 BLOCKED_WITH_COUNTEREXAMPLE
T2D_INTERVAL_DIRECTION:         BLOCKED_WITH_PAPER_CODE_CONTRADICTION
T9_MULTI_ACTION_BHATTACHARYYA:  BLOCKED_WITH_CODE_ERROR
MEASURED_SAMPLE_SIZE_AND_TRANSFER_CLAIMS: NOT_ESTABLISHED
METHOD_SUPERIORITY_AND_SOTA:    NOT_ESTABLISHED
PAPER_SUBMISSION:               BLOCKED_WITH_EVIDENCE
```

## What is frozen (not to be reinterpreted)

- Task5 closure `d0feaa62…` — `TASK5_SYNTHETIC_SOFTWARE_EVALUATION_ONLY`, `scientific_conclusion_authorized=false`.
- v7 activation manifest `eae4ba94…` — `ACTIVE_SUCCESSOR_FOR_FUTURE_TASKS`, `scientific_claim_authorized=false`.
- Historical Task1–5 results: recorded, not reinterpreted by this audit.

## Central blockers (evidence-backed)

1. **T2b object mismatch**: paper defines `gamma(S)` as panel product-law TV; code computes single-action max L1 then min over passive-collision fiber; LP convexizes the discrete catalog without declaration. Paper reports `gamma=49/25=1.96`, but TV must lie in `[0,1]` — an internal contradiction.
2. **T2c minimax mislabel**: `exact_minimax_error()` returns `1/2 sum min(P0,P1)` (equal-prior Bayes average), not per-hypothesis minimax/`alpha`/`beta`/`kappa`. Minimal counterexample: code `1/4`, true randomized minimax `1/3`; `FEASIBLE` emitted when only necessary-information threshold crossed (not proven feasible).
3. **Measured likelihood unidentifiable**: normalized reactivity clamped to `[0.01,0.99]` treated as independent Bernoulli; SE parsed but unused in likelihood/selection/information/`n`; provenance claimed `per_position_error_used=True`. Same profile defines channel, picks probe, sets floor, derives `n`, and "validates". `n=3` (add/miniTTR) and `n=15` (glycine) are not experiment-error-calibrated sample sizes.
4. **SOTA comparison invalid**: greedy Test-Cover / EIG / LM2R-style use the same score and allocator; "Chernoff" is not standard Chernoff information; "exhaustive oracle" hard-truncates allocation at 6 even at budget 8; baselines use different stopping/objective. 11 microcases × 88 runs cannot support superiority/scalability.
5. **T2d interval direction reversed**: no-go should use an upper information bound, constructive achievability a lower bound; `supplementary.tex:145-158` reversed, `costed.py` closer to correct.
6. **Heterogeneous multi-action Bhattacharyya bug**: `matrix.py:469-490` used `BC_0^{sum n_u}`; correct is `prod_u BC_u^{n_u}`.

## P0 response

These blockers are addressed by P0-2 (semantic discrepancy ledger), P0-3/4/5/6 (kernel/decision/measured/benchmark), and P0-7 (fresh regression + evidence rebind). Strong claims remain paused until the corrected `TheoremSpec` passes the kill tests and the paper/code agree on every measured quantity.

## Artifact status

- `manifests/audit/v7_snapshot.json` — snapshot of HEAD, v7 bytes, Task5 closure, paper/data hashes.
