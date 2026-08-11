"""method_role.py -- method-role registry + fail-closed consumer guard (P0-7).

Every evaluation method is classified into exactly one role:

* ``oracle``      -- an independent exhaustive/DP/MILP *reference*.  It is used
                     ONLY for small ground truth, regret and gap reporting.  It
                     must NEVER be ranked as a method in a comparative table,
                     nor feed a win/tie/worse, CI, superiority or Pareto claim.
* ``deployable``  -- an explicitly named D2T solver (e.g. the D2T fixed-budget
                     solver).  This is the production method under evaluation.
* ``comparator``  -- a method run on the SAME task / information / cost /
                     horizon / endpoint as the deployable.

The role registry is *authoritative*: consumers MUST route every method
through :func:`evaluate_method_role` / :func:`assert_no_oracle_ranking` before
emitting any win/tie/worse, CI, superiority or Pareto statement.  An oracle row
fed into such a consumer raises :class:`OracleRankingError` (fail-closed, the
consumer must exit non-zero).

Oracle rows are permitted ONLY for ``regret`` and ``gap`` reporting (and, by
extension, ground-truth containment).  Any other downstream claim on an oracle
row is refused.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# role classification
# ---------------------------------------------------------------------------


class MethodRole(str, Enum):
    ORACLE = "oracle"
    DEPLOYABLE = "deployable"
    COMPARATOR = "comparator"


# Default role table for the methods known to this repository.  The D2T
# fixed-budget solver is the named *deployable*.  Everything listed as a
# comparable baseline (same task / information / cost / horizon / endpoint) is
# a *comparator*.  Independent exhaustive / DP / MILP references are *oracles*.
KNOWN_METHOD_ROLES: dict[str, MethodRole] = {
    # --- oracles (independent references; regret/gap/ground-truth only) ---
    "INDEPENDENT_ORACLE_EXACT": MethodRole.ORACLE,
    "exhaustive_oracle": MethodRole.ORACLE,
    "exact_oracle": MethodRole.ORACLE,
    "milp_reference": MethodRole.ORACLE,
    # --- deployable (the named D2T solver) ---
    "D2T_FIXED_BUDGET_SOLVER": MethodRole.DEPLOYABLE,
    "d2t_fixed_budget_solver": MethodRole.DEPLOYABLE,
    "d2t": MethodRole.DEPLOYABLE,
    # --- comparators (same task/cost/horizon/endpoint as the deployable) ---
    "chernoff": MethodRole.COMPARATOR,
    "eig": MethodRole.COMPARATOR,
    "full_matrix": MethodRole.COMPARATOR,
    "random": MethodRole.COMPARATOR,
    "greedy_test_cover": MethodRole.COMPARATOR,
    "lm2r_heuristic": MethodRole.COMPARATOR,
    "t2_integer_lp": MethodRole.COMPARATOR,
}


def classify_method_role(method_id: str) -> MethodRole:
    """Classify a method id into exactly one role.

    Unknown ids default to ``comparator`` ONLY when they are unambiguously
    solution methods on the same task; ids that are *references* (contain
    ``oracle``, ``reference``, ``exact``, ``milp``) default to ``oracle`` so the
    guard fails closed toward the safer side.
    """
    key = method_id.strip()
    if key in KNOWN_METHOD_ROLES:
        return KNOWN_METHOD_ROLES[key]
    lower = key.lower()
    if any(tok in lower for tok in ("oracle", "reference", "exact", "milp")):
        return MethodRole.ORACLE
    if any(tok in lower for tok in ("d2t", "solver")):
        return MethodRole.DEPLOYABLE
    return MethodRole.COMPARATOR


# ---------------------------------------------------------------------------
# fail-closed consumer guard
# ---------------------------------------------------------------------------


class OracleRankingError(RuntimeError):
    """Raised when a consumer tries to rank / CI / superiority / Pareto an
    oracle row.  Oracle rows may only be used for regret / gap reporting."""


# claims that are FORBIDDEN on an oracle row
ORACLE_FORBIDDEN_CLAIMS = frozenset(
    {"win", "tie", "worse", "ci", "confidence", "superiority", "pareto",
     "strict_improvement", "dominated"}
)
# claims that are ALLOWED on an oracle row (reference-only)
ORACLE_ALLOWED_CLAIMS = frozenset(
    {"regret", "gap", "ground_truth", "containment", "correctness"}
)


def assert_no_oracle_ranking(
    role: MethodRole | str,
    claim: str,
    method_id: Optional[str] = None,
) -> None:
    """Fail-closed: refuse any ranking/CI/superiority/Pareto claim on an oracle.

    Raises :class:`OracleRankingError` (consumer must propagate as a non-zero
    exit).  For a non-oracle role this is a no-op returning ``None``.
    """
    if isinstance(role, str):
        role = MethodRole(role)
    if role is not MethodRole.ORACLE:
        return
    claim_norm = claim.strip().lower()
    if claim_norm in ORACLE_FORBIDDEN_CLAIMS:
        raise OracleRankingError(
            f"refusing to rank/CI/superiority/Pareto an ORACLE row "
            f"(claim={claim!r}, method_id={method_id!r}). Oracle rows may only "
            f"be used for regret/gap/ground-truth reporting."
        )
    if claim_norm not in ORACLE_ALLOWED_CLAIMS:
        raise OracleRankingError(
            f"unknown claim {claim!r} on an ORACLE row; only "
            f"{sorted(ORACLE_ALLOWED_CLAIMS)} are permitted."
        )


def evaluate_method_role(method_id: str, claim: str) -> MethodRole:
    """Classify a method and enforce the fail-closed guard for one claim.

    Returns the role when the claim is permissible; raises
    :class:`OracleRankingError` when an oracle row is fed a ranking/CI/
    superiority/Pareto claim.
    """
    role = classify_method_role(method_id)
    assert_no_oracle_ranking(role, claim, method_id=method_id)
    return role


# ---------------------------------------------------------------------------
# role-table helpers (for the frozen decision registry)
# ---------------------------------------------------------------------------


def method_role_table(method_ids: Iterable[str]) -> list[dict]:
    """Return a deterministic method-role table for a set of method ids."""
    out = []
    for mid in method_ids:
        role = classify_method_role(mid)
        out.append(
            {
                "method_id": mid,
                "method_role": role.value,
                "rankable": role is not MethodRole.ORACLE,
                "oracle_allowed_claims": (
                    sorted(ORACLE_ALLOWED_CLAIMS) if role is MethodRole.ORACLE
                    else None
                ),
            }
        )
    # deterministic sort
    out.sort(key=lambda r: (r["method_role"], r["method_id"]))
    return out
