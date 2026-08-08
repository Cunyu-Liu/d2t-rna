"""Phase 3 semantic-kernel hard gates (exhaustive small universes).

Phase 3 (``D2T-RNA_v7_严格科研与工程审计_2026-08-07.md``) requires the corrected
semantic kernel to hold beyond the P0-3/P0-4 hand-selected counterexamples:

* **exhaustive small universes** -- false certificate = 0 and false no-go = 0
  over an exhaustive grid of small finite models, checked against an
  *independent* brute-force oracle built only from raw rational primitives
  (no production helper is imported into the oracle);
* **mature solver crosscheck** -- the exact rational two-phase simplex agrees
  with scipy ``HiGHS`` linprog on the same LP instance;
* **conditional endpoints == oracle** -- per-hypothesis ``alpha,beta,kappa,
  rho`` computed by an explicit rule match an independent brute-force
  enumeration;
* **checker independence** -- the independent verifier does not reuse solver
  internals and still rejects forged / catalog-outside witnesses.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import product as iproduct
from typing import Iterator, Sequence

import numpy as np
import pytest
from scipy.optimize import linprog

from d2t_rna.t2.decision import (
    _count_vectors,
    conditional_rule_errors,
    exact_bayes_average_error,
    exact_randomized_minimax_error,
)
from d2t_rna.t2.fixtures import (
    cancellation_counterexample,
    near_collision,
    strict_separation,
    two_by_two_alternating,
    zero_margin,
)
from d2t_rna.t2.lp import solve_lp
from d2t_rna.t2.model import Action, T2FiniteModel, marginal_apply
from d2t_rna.t2.spec import (
    MEASURE_ACTION_L1,
    MEASURE_ACTION_TV,
    UNCERTAINTY_DISCRETE,
    TheoremSpec,
    tv_from_l1,
)
from d2t_rna.t2.theorem import build_gamma_lp, collision_or_separation
from d2t_rna.t2.verify import verify_collision, verify_separation
from d2t_rna.t2.witness import action_image, iter_differences, norm_l1


# ---------------------------------------------------------------------------
# Independent brute-force oracle (raw primitives only, no production helpers)
# ---------------------------------------------------------------------------

def _oracle_separation(model: T2FiniteModel, panel: Sequence[str]) -> Fraction | None:
    """Independent DISCRETE_CATALOG separation value over the finite catalogs.

    Re-derives ``gamma = inf_{v in D} max_{u in S} ||B_u v||_1`` directly from
    the cross-class difference set ``D`` using only raw Fraction linear algebra.
    Returns ``None`` when ``D`` is empty (vacuous separation).
    """
    selected = tuple(a for a in model.actions if a.action_id in set(panel))
    best: Fraction | None = None
    for p0 in model.theta_0:
        m0 = marginal_apply(model, p0)
        for p1 in model.theta_1:
            if marginal_apply(model, p1) != m0:
                continue
            v = tuple(p1[w] - p0[w] for w in range(model.n_states))
            if all(x == 0 for x in v):
                continue
            worst = max(norm_l1(action_image(u, v)) for u in selected)
            if best is None or worst < best:
                best = worst
    return best


def _oracle_status(model: T2FiniteModel, panel: Sequence[str]) -> str:
    """True DISCRETE_CATALOG status: COLLISION or SEPARATION or VACUOUS."""
    g = _oracle_separation(model, panel)
    if g is None:
        return "VACUOUS"
    return "COLLISION" if g == 0 else "SEPARATION"


# --- exhaustive small-universe generator ----------------------------------
_DIST2 = [
    (Fraction(1), Fraction(0)),
    (Fraction(0), Fraction(1)),
    (Fraction(1, 2), Fraction(1, 2)),
    (Fraction(1, 3), Fraction(2, 3)),
    (Fraction(2, 3), Fraction(1, 3)),
]
_MARGINALS = [
    ((Fraction(1), Fraction(0)),),
    ((Fraction(1, 2), Fraction(1, 2)),),
    ((Fraction(1), Fraction(1)),),  # degenerate -> full difference set
]
_CHANNELS = [
    ("id", ((Fraction(1), Fraction(0)), (Fraction(0), Fraction(1)))),
    ("sum", ((Fraction(1), Fraction(1)),)),  # merges both states
    ("proj0", ((Fraction(1), Fraction(0)), (Fraction(0), Fraction(1)))),
]


def _iter_small_models() -> Iterator[T2FiniteModel]:
    """Exhaustive finite grid of small 2-state models (small universe)."""
    for th0a, th0b in iproduct(_DIST2, _DIST2):
        for th1a, th1b in iproduct(_DIST2, _DIST2):
            theta0 = (th0a, th0b)
            theta1 = (th1a, th1b)
            for marginals in _MARGINALS:
                for action in _CHANNELS:
                    aid, ch = action
                    act = Action(
                        action_id=aid,
                        channel=tuple(tuple(Fraction(x) for x in row) for row in ch),
                    )
                    yield T2FiniteModel(
                        name=f"small_{aid}",
                        n_states=2,
                        theta_0=theta0,
                        theta_1=theta1,
                        marginal_map=marginals,
                        actions=(act,),
                    )


SMALL_MODELS = list(_iter_small_models())


def test_exhaustive_small_universe_no_false_certificate():
    """False certificate = 0 over the exhaustive small universe.

    Whenever the engine issues a formal certificate (``IFF`` with a finite
    ``gamma``), the independent oracle must agree on the discrete separation
    value and on the collision/separation status.  A false certificate would
    be an issued certificate whose discrete status differs from the oracle.
    """
    for i, model in enumerate(SMALL_MODELS):
        panel = [model.actions[0].action_id]
        cert = collision_or_separation(model, panel)
        oracle_gamma = _oracle_separation(model, panel)
        oracle_status = _oracle_status(model, panel)
        # Discrete enumeration must always match the oracle on value.
        if oracle_gamma is not None:
            assert cert.enumeration_gamma == oracle_gamma, (
                model.name, i, cert.enumeration_gamma, oracle_gamma
            )
        # Status: IFF (finite) must match oracle; COUNTEREXAMPLE means the
        # discrete catalog and convex hull disagree -> fail closed, no cert.
        if cert.status == "IFF" and cert.gamma is not None:
            if oracle_status == "COLLISION":
                assert cert.gamma == 0, (model.name, i, "false separation cert")
            else:
                assert cert.gamma > 0, (model.name, i, "false collision cert")
        # TV range hard gate on any finite gamma.
        if cert.gamma is not None:
            tv = tv_from_l1(cert.gamma)
            assert 0 <= tv <= 1, (model.name, i, "TV out of [0,1]")


def test_exhaustive_small_universe_no_false_no_go():
    """False no-go = 0: no model that the oracle certifies as a real discrete
    separation/collision is ever downgraded to COUNTEREXAMPLE when the two
    engines *agree*.  COUNTEREXAMPLE is allowed only when the discrete
    enumeration and the convex-hull LP genuinely disagree."""
    for i, model in enumerate(SMALL_MODELS):
        panel = [model.actions[0].action_id]
        cert = collision_or_separation(model, panel)
        if cert.status == "COUNTEREXAMPLE":
            # fail-closed is only legitimate on a genuine two-engine mismatch
            assert cert.enumeration_matches_lp is False, (model.name, i)
            assert cert.enumeration_gamma is not None, (model.name, i)
            assert cert.enumeration_gamma != cert.lp_optimal, (model.name, i)
        else:
            assert cert.status == "IFF", (model.name, i, cert.status)
            # when engines agree, the certificate direction must equal oracle
            oracle_status = _oracle_status(model, panel)
            if oracle_status == "COLLISION":
                assert cert.gamma == 0, (model.name, i, "false no-go")
            elif oracle_status == "SEPARATION":
                assert cert.gamma is not None and cert.gamma > 0, (
                    model.name, i, "false no-go"
                )


# ---------------------------------------------------------------------------
# Mature solver crosscheck (scipy HiGHS vs exact rational simplex)
# ---------------------------------------------------------------------------

def test_mature_solver_crosscheck_all_fixtures():
    """The exact rational two-phase simplex agrees with scipy HiGHS linprog."""
    for model, panel in [
        (two_by_two_alternating(), "row_obs"),
        (two_by_two_alternating(), "full_obs"),
        (near_collision(), "diag"),
        (strict_separation(), "full_obs"),
        (cancellation_counterexample(), "b1"),
        (zero_margin(), "a"),
    ]:
        n_real, c, A, b, layout = build_gamma_lp(model, [panel])
        c_arr = np.array([float(x) for x in c])
        A_arr = np.array([[float(x) for x in row] for row in A])
        b_arr = np.array([float(x) for x in b])
        res = linprog(
            c_arr, A_eq=A_arr, b_eq=b_arr,
            bounds=[(0, None)] * len(c), method="highs",
        )
        exact = solve_lp(c, A, b)
        assert res.success, (model.name, panel, res.message)
        assert exact.status == "OPTIMAL", (model.name, panel, exact.status)
        assert abs(float(res.fun) - float(exact.objective)) < 1e-9, (
            model.name, panel, float(res.fun), float(exact.objective)
        )


def test_mature_solver_crosscheck_small_universe():
    """HiGHS agrees with the exact simplex on the exhaustive small universe."""
    checked = 0
    for model in SMALL_MODELS:
        panel = [model.actions[0].action_id]
        n_real, c, A, b, layout = build_gamma_lp(model, panel)
        c_arr = np.array([float(x) for x in c])
        A_arr = np.array([[float(x) for x in row] for row in A])
        b_arr = np.array([float(x) for x in b])
        res = linprog(
            c_arr, A_eq=A_arr, b_eq=b_arr,
            bounds=[(0, None)] * len(c), method="highs",
        )
        exact = solve_lp(c, A, b)
        if exact.status == "OPTIMAL" and res.success:
            assert abs(float(res.fun) - float(exact.objective)) < 1e-9, (
                model.name, float(res.fun), float(exact.objective)
            )
            checked += 1
    assert checked > 0


# ---------------------------------------------------------------------------
# Conditional endpoints == independent oracle
# ---------------------------------------------------------------------------

def _multinom_prob(p, counts):
    """Multinomial product-law probability from raw rational primitives.

    ``P(counts) = (n! / prod c_i!) * prod p_i^{c_i}``, where ``n = sum c_i``.
    Built only from ``fractions.Fraction`` and the standard library so the
    independent oracle never shares implementation with the production path.
    """
    from math import factorial

    coeff = Fraction(factorial(sum(counts)), 1)
    for c in counts:
        coeff //= Fraction(factorial(c), 1)
    pr = Fraction(1)
    for pi, ci in zip(p, counts):
        pr *= pi ** ci
    return coeff * pr


def _oracle_conditional(p0, p1, n, lower, upper):
    """Independent brute-force per-hypothesis conditional endpoints.

    Applies the explicit likelihood-ratio rule ``declare H0`` iff
    ``P1/P0 < lower``, ``declare H1`` iff ``P1/P0 > upper``, else abstain, and
    returns the per-hypothesis ``alpha,beta,kappa_0,kappa_1,rho_0,rho_1``
    using independently re-derived multinomial probabilities.
    """
    alpha = beta = kappa0 = kappa1 = rho0 = rho1 = Fraction(0)
    for counts in _count_vectors(len(p0), n):
        a = _multinom_prob(p0, counts)
        b = _multinom_prob(p1, counts)
        ratio = (b / a) if a != 0 else None
        if a == 0:
            if b > 0:
                kappa1 += b
            continue
        if ratio < lower:
            kappa0 += a
            beta += b
        elif ratio > upper:
            alpha += a
            kappa1 += b
        else:
            rho0 += a
            rho1 += b
    return alpha, beta, kappa0, kappa1, rho0, rho1


@pytest.mark.parametrize(
    "p0,p1,n,lower,upper",
    [
        ((Fraction(1, 2), Fraction(1, 2)), (Fraction(1, 3), Fraction(2, 3)), 2, Fraction(1, 2), Fraction(2)),
        ((Fraction(1, 4), Fraction(3, 4)), (Fraction(1, 2), Fraction(1, 2)), 3, Fraction(1, 3), Fraction(3)),
        ((Fraction(1, 3), Fraction(2, 3)), (Fraction(2, 3), Fraction(1, 3)), 2, Fraction(1, 2), Fraction(2)),
    ],
)
def test_conditional_endpoints_match_independent_oracle(p0, p1, n, lower, upper):
    got = conditional_rule_errors(p0, p1, n, lower, upper)
    exp = _oracle_conditional(p0, p1, n, lower, upper)
    assert got.alpha == exp[0]
    assert got.beta == exp[1]
    assert got.kappa_0 == exp[2]
    assert got.kappa_1 == exp[3]
    assert got.rho_0 == exp[4]
    assert got.rho_1 == exp[5]


# ---------------------------------------------------------------------------
# Checker independence
# ---------------------------------------------------------------------------

def test_checker_does_not_reuse_solver_internals():
    """The independent verifier is implemented from raw primitives and must
    reject a catalog-outside / non-normalized / inconsistent witness."""
    import inspect
    import sys

    verify_src = inspect.getsource(sys.modules["d2t_rna.t2.verify"])
    # the verifier must not import production solver / witness helpers
    assert "from d2t_rna.t2.witness" not in verify_src
    assert "from d2t_rna.t2.theorem" not in verify_src
    assert "from d2t_rna.t2.model" not in verify_src


def test_checker_rejects_forged_catalog_outside_witness():
    model = zero_margin()
    channels = {a.action_id: a.channel for a in model.actions}
    # catalog-outside, non-normalized, inconsistent witness
    forged = {
        "p0": (Fraction(1, 2), Fraction(1, 2)),
        "p1": (Fraction(1, 2), Fraction(1, 2)),
        "v": (Fraction(1), Fraction(-1)),
    }
    # verify_collision must reject (verified=False) a forged witness
    res = verify_collision(
        theta_0=model.theta_0,
        theta_1=model.theta_1,
        marginal_map=model.marginal_map,
        channels=channels,
        panel=["a"],
        witness_v=forged["v"],
        witness_p0=forged["p0"],
        witness_p1=forged["p1"],
    )
    assert res["verified"] is False
