# T2 Semantics v2 Draft Spec — P0-2

Status: DRAFT (supersedes ambiguous v1 semantics; P0-3/4 implemented a matching TheoremSpec).

## 1. Single TheoremSpec

One executable, falsifiable spec governs contract, paper, code, and checker. Every symbol below has an owner, domain, unit, algorithm, and checker.

## 2. Uncertainty kind

- Certified semantics are **DISCRETE_CATALOG**: a finite registered control library of actions, each with an exact known-channel multinomial law.
- **CONVEX_HULL** is only a derived feasibility relaxation (for LP bounding), never the certified separation/decision semantics.
- A certificate must declare which uncertainty kind it covers; `enumeration_matches_lp=False` forbids any formal certificate.

## 3. Separation measure

- `gamma(S)` is a total-variation separation **in observation-probability space**, `TV = L1/2`, and therefore lies in `[0,1]`.
- Code computes action-level L1 separation for the separating probe, then takes the min over the passive-collision fiber; `gamma_tv = gamma_l1 / 2`.
- `TheoremSpec` declares `ACTION_L1` vs `ACTION_TV` explicitly (see `src/d2t_rna/t2/spec.py`).
- Checker: independent witness membership + normalization + `v = p1 - p0`; fails closed on forged witness.

## 4. Decision error

- `exact_bayes_average_error = 1/2 sum min(P0,P1)` is the equal-prior Bayes average — it is **not** per-hypothesis minimax.
- Per-hypothesis guarantees use `ConditionalDecision`: `alpha`, `beta`, `kappa_0`, `kappa_1`, `rho_0`, `rho_1`, computed separately.
- `exact_randomized_minimax_error` is the true randomized minimax via LP.
- `FEASIBLE` is emitted only by an explicit constructive-declaration rule; crossing a necessary information threshold alone yields `AMBIGUOUS`.

## 5. Information bound direction

- No-go (proving no design can achieve a target) uses an **upper bound** on per-action available information.
- Constructive achievability uses a **lower bound**.
- The paper and `costed.py` must agree on this direction.

## 6. Multi-action likelihood

- Heterogeneous multi-action Bhattacharyya: `product_bhattacharyya = prod_u BC_u^{n_u}`.
- True Chernoff information; cap-free complete enumeration oracle (no hard truncation of allocation).

## 7. Measured claims

- Measurement SE must be threaded through likelihood, panel selection, information, and `n` if claimed used (`per_position_error_used=True`).
- Otherwise `per_position_error_used=False`. Glycine is `BLOCKED_PENDING_ARCHIVE_QUALIFICATION` (raw per-replicate counts unavailable).
