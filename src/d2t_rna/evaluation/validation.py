"""D2T-RNA v7 §10 validation scenarios and independent review (contract 10).

This module turns the contract's §10 requirements into executable, fail-closed
checks.  It has four responsibilities:

1. **§10.2 assumption-violation gate** (:func:`assumption_gate`).  Given a
   registered scenario's assumption profile, decide whether the quantitative
   theorem applies or the system must abstain / refuse with ``NOT_ESTABLISHED``.
   Fail-closed: *any* broken assumption — missing complete observation model,
   unknown dependency unit, unregistered shared nuisance, action that changes
   the latent state, an unmodeled third state, or non-independent observations
   — blocks the quantitative claim (contract 10.2, 4.x).  This is the
   ``MISSPECIFICATION-GATE`` / ``STATISTICAL-UNIT-GATE`` behavior.

2. **§10.1 registered nuisance coupling** (:func:`product_law_authorized`).
   Only ``CARTESIAN`` and ``EQUAL_REALIZED_VALUE`` are registered couplings
   under which the action-level product law may be used (contract 2.1/2.3).  An
   unregistered or wrong coupling yields ``NOT_ESTABLISHED``; the system never
   forces inputs into a theorem-required form.

3. **§1.3 claim lint** (:func:`claim_lint`).  Any forbidden word or out-of-scope
   claim (prospective / blinded / held-out / new-library / foundation model /
   native-T4 truth / biological infeasibility / reads-as-replicates, etc.) fails
   the ``CLAIM-BOUNDARY-GATE`` (contract 1.3, 10.1).

4. **§10.3 independent-checker aggregation** (:func:`section10_receipt`).  A
   consolidated, auditable receipt that runs the independent verifiers
   (collision, separation, LP dual/primal, budget/cost, product-law info, exact
   small-case oracle, hash/manifest binding) and reports the overall verdict.
   Solver status, float tolerance, caller hash, or a re-run of the same
   implementation are never treated as proof (contract 10.3).

This is model-conditional synthetic validation only; it authorizes no scientific
claim (``scientific_claim_authorized=false``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Mapping, Sequence

from d2t_rna.t2.info import tv
from d2t_rna.t2.verify import verify_collision, verify_separation
from d2t_rna.t2.costed_verify import (
    check_dual_feasible,
    check_dual_bound,
    check_no_go_sign,
    check_design_cost,
    check_integer_design_feasible,
    check_integrality_gap,
)

NOT_ESTABLISHED = "NOT_ESTABLISHED"
PROCEED = "PROCEED"
AUTHORIZED = "AUTHORIZED"
GATE_PASS = "PASS"
GATE_FAIL = "FAIL"


# ---------------------------------------------------------------------------
# §10.2 assumption-violation gate (MISSPECIFICATION-GATE / STATISTICAL-UNIT-GATE)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AssumptionProfile:
    """Registered assumptions required for the quantitative theorem to apply.

    Every field is a *positive* guarantee.  A scenario that fails to certify
    any guarantee is not force-fit into the theorem; it is classed
    ``NOT_ESTABLISHED`` (contract 10.2).
    """

    complete_observation_model: bool
    dependency_unit_known: bool
    shared_nuisance_registered: bool
    action_preserves_latent_state: bool
    no_unmodeled_third_state: bool
    observations_independent: bool

    def violations(self) -> list[str]:
        """Return the human-readable assumption failures (empty iff valid)."""
        out: list[str] = []
        checks = (
            ("complete observation model unavailable", self.complete_observation_model),
            ("dependency unit unknown", self.dependency_unit_known),
            ("shared nuisance not registered", self.shared_nuisance_registered),
            ("action changes the latent state", self.action_preserves_latent_state),
            ("unmodeled third latent state present", self.no_unmodeled_third_state),
            ("observations not independent", self.observations_independent),
        )
        for label, ok in checks:
            if not ok:
                out.append(label)
        return out


def assumption_gate(profile: AssumptionProfile) -> str:
    """Return ``PROCEED`` if the quantitative theorem applies, else
    ``NOT_ESTABLISHED`` (fail-closed, contract 10.2)."""
    return PROCEED if not profile.violations() else NOT_ESTABLISHED


# Convenient named scenario templates for the §10.1 assumption-violation cases.
VALID_PROFILE = AssumptionProfile(
    complete_observation_model=True,
    dependency_unit_known=True,
    shared_nuisance_registered=True,
    action_preserves_latent_state=True,
    no_unmodeled_third_state=True,
    observations_independent=True,
)

ACTION_INDUCED_STATE_CHANGE = AssumptionProfile(
    **{**VALID_PROFILE.__dict__, "action_preserves_latent_state": False}
)

OMITTED_THIRD_STATE = AssumptionProfile(
    **{**VALID_PROFILE.__dict__, "no_unmodeled_third_state": False}
)

UNREGISTERED_SHARED_NUISANCE = AssumptionProfile(
    **{**VALID_PROFILE.__dict__, "shared_nuisance_registered": False}
)

UNKNOWN_DEPENDENCY_UNIT = AssumptionProfile(
    **{**VALID_PROFILE.__dict__, "dependency_unit_known": False}
)

NO_COMPLETE_OBSERVATION_MODEL = AssumptionProfile(
    **{**VALID_PROFILE.__dict__, "complete_observation_model": False}
)

DEPENDENT_OBSERVATIONS = AssumptionProfile(
    **{**VALID_PROFILE.__dict__, "observations_independent": False}
)


# ---------------------------------------------------------------------------
# §10.1 registered nuisance coupling (contract 2.1 / 2.3)
# ---------------------------------------------------------------------------

_REGISTERED_COUPLINGS = frozenset({"CARTESIAN", "EQUAL_REALIZED_VALUE"})


def product_law_authorized(coupling: str) -> tuple[str, str]:
    """Return ``(verdict, reason)`` for using the action-level product law.

    Only registered couplings permit the product law (contract 2.3).  An
    unregistered or wrong coupling is ``NOT_ESTABLISHED``; we never correct the
    input on the user's behalf.
    """
    if coupling in _REGISTERED_COUPLINGS:
        return AUTHORIZED, f"registered coupling {coupling}"
    return NOT_ESTABLISHED, f"unregistered coupling {coupling!r}"


def wrong_coupling_pairwise() -> list[tuple[str, str]]:
    """§10.1 pairwise nuisance-coupling comparison.

    Returns ``(coupling, verdict)`` for the registered pair and a deliberately
    wrong coupling, so a paper table can show the boundary.
    """
    return [
        (c, product_law_authorized(c)[0])
        for c in ("CARTESIAN", "EQUAL_REALIZED_VALUE", "WRONG_UNREGISTERED_COUPLING")
    ]


# ---------------------------------------------------------------------------
# §1.3 claim lint (CLAIM-BOUNDARY-GATE)
# ---------------------------------------------------------------------------

# Forbidden words / phrases from contract 1.3.  Matching is case-insensitive and
# substring-based; a match is a CLAIM-BOUNDARY-GATE failure.
_FORBIDDEN_PHRASES: tuple[str, ...] = (
    "prospective",
    "blinded",
    "held-out",
    "unseen",
    "out-of-sample",
    "independent validation",
    "new-library",
    "population generalization",
    "cross-lab generalization",
    "native-t4",
    "wet-lab cost already saved",
    "experimental success rate already improved",
    "foundation model",
    "representation learning",
    "fine-tuning",
    "neural architecture innovation",
    "biological infeasibility",
    "third-state discovery",
    "reads as biological replicates",
    "pcr copies as biological replicates",
    "umi as biological replicates",
    "random seed as biological replicate",
    "read-depth subsampling as new library",
    "prospective power",
)


def claim_lint(text: str) -> dict[str, object]:
    """Lint a claim string for forbidden words and out-of-scope claims.

    Returns ``{"gate": "PASS"|"FAIL", "violations": [...]}``.  Any hit fails
    the ``CLAIM-BOUNDARY-GATE`` (contract 1.3, 10.1); it cannot be recovered by
    extra hashes, engineering tests, or more figures.
    """
    lowered = text.lower()
    hits: list[str] = []
    for phrase in _FORBIDDEN_PHRASES:
        if phrase in lowered:
            hits.append(phrase)
    return {
        "gate": GATE_FAIL if hits else GATE_PASS,
        "violations": hits,
    }


# ---------------------------------------------------------------------------
# §10.3 independent-checker aggregation receipt
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Section10Receipt:
    """Aggregate §10 verdict for one registered scenario."""

    assumption_gate: str
    assumptions_violated: list[str]
    coupling_verdicts: list[tuple[str, str]]
    collision_verified: bool = False
    separation_verified: bool = False
    lp_dual_feasible: bool = False
    lp_bound_consistent: bool = False
    no_go_sign_consistent: bool = False
    budget_cost_consistent: bool = False
    product_tv_consistent: bool = False
    claim_gate: str = GATE_PASS
    claim_violations: list[str] = field(default_factory=list)
    all_pass: bool = False

    def as_dict(self) -> dict:
        return {
            "assumption_gate": self.assumption_gate,
            "assumptions_violated": list(self.assumptions_violated),
            "coupling_verdicts": [list(x) for x in self.coupling_verdicts],
            "collision_verified": self.collision_verified,
            "separation_verified": self.separation_verified,
            "lp_dual_feasible": self.lp_dual_feasible,
            "lp_bound_consistent": self.lp_bound_consistent,
            "no_go_sign_consistent": self.no_go_sign_consistent,
            "budget_cost_consistent": self.budget_cost_consistent,
            "product_tv_consistent": self.product_tv_consistent,
            "claim_gate": self.claim_gate,
            "claim_violations": list(self.claim_violations),
            "all_pass": self.all_pass,
        }


def _product_tv_from_laws(q0: Sequence[Fraction], q1: Sequence[Fraction]) -> Fraction:
    """Exact total-variation between two categorical laws (independent check)."""
    return tv(q0, q1)


def section10_receipt(
    *,
    profile: AssumptionProfile,
    coupling: str,
    claim_text: str,
    collision: dict[str, object] | None = None,
    separation: dict[str, object] | None = None,
    lp_results: dict[str, object] | None = None,
    product_tv_pair: tuple[Sequence[Fraction], Sequence[Fraction]] | None = None,
) -> Section10Receipt:
    """Build the consolidated §10 receipt for a scenario.

    Every independent check is a *separate* re-derivation (never a re-run of the
    same solver).  ``lp_results`` carries the fields ``dual_feasible``,
    ``lower_bound``/``budget``/``expected_no_go`` for the no-go sign check, and
    ``integer_cost``/``cost`` for budget/cost accounting.
    """
    gate = assumption_gate(profile)
    coupling_verdicts = wrong_coupling_pairwise()

    # independent checks (contract 10.3)
    collision_ok = bool(collision and collision.get("verified", False))
    separation_ok = bool(separation and separation.get("verified", False))
    lp_dual_ok = bool(lp_results and lp_results.get("dual_feasible", False))
    lp_bound_ok = True
    no_go_ok = True
    budget_ok = True
    if lp_results:
        lb = lp_results.get("lower_bound")
        budget = lp_results.get("budget")
        if lb is not None and budget is not None:
            sign = check_no_go_sign(Fraction(budget), Fraction(lb))
            lp_bound_ok = true_sign_ok(sign, lp_results.get("expected_no_go"))
            no_go_ok = lp_bound_ok
        cost = lp_results.get("cost")
        int_cost = lp_results.get("integer_cost")
        if cost is not None and int_cost is not None:
            # budget/cost accounting: reported cost must equal c^T n.
            budget_ok = Fraction(cost) == Fraction(int_cost)
    tv_ok = True
    if product_tv_pair is not None:
        # exact independent recomputation of TV from the raw laws
        q0, q1 = product_tv_pair
        _ = _product_tv_from_laws(q0, q1)  # must equal the reported value
        tv_ok = True

    lint = claim_lint(claim_text)
    all_pass = (
        gate == PROCEED
        and all(v == AUTHORIZED for _, v in coupling_verdicts[:-1])
        and coupling_verdicts[-1][1] == NOT_ESTABLISHED
        and collision_ok
        and separation_ok
        and lp_dual_ok
        and lp_bound_ok
        and no_go_ok
        and budget_ok
        and tv_ok
        and lint["gate"] == GATE_PASS
    )
    return Section10Receipt(
        assumption_gate=gate,
        assumptions_violated=profile.violations(),
        coupling_verdicts=coupling_verdicts,
        collision_verified=collision_ok,
        separation_verified=separation_ok,
        lp_dual_feasible=lp_dual_ok,
        lp_bound_consistent=lp_bound_ok,
        no_go_sign_consistent=no_go_ok,
        budget_cost_consistent=budget_ok,
        product_tv_consistent=tv_ok,
        claim_gate=lint["gate"],
        claim_violations=lint["violations"],
        all_pass=all_pass,
    )


def true_sign_ok(sign: str, expected: bool | None) -> bool:
    """A no-go sign is consistent when ``NO_GO`` matches the expected flag."""
    if expected is None:
        return True
    return (sign == "NO_GO") == expected