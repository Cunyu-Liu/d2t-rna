"""K2 audit: empty-discrete vs nonempty-convex dispatch + honest confusion accounting.

The v7 audit flagged the silent mixing of the discrete-catalog and convex-hull
problems.  A microcase can have an *empty* discrete difference set ``D`` (so the
discrete branch is vacuous) while the *convex hulls* of the two catalogs still
contain a nontrivial conflict.  This audit file verifies:

  * the production discrete branch returns a vacuous result for such a model
    (``collapsed=True``, ``gamma=None``) -- an honest empty-``D`` early return;
  * the independent convex oracle is **not** short-circuited by that
    empty-discrete early return: it computes a definite convex value;
  * the independent discrete oracle agrees with the vacuous handling;
  * ``oracle_confusion_accounting`` reports the confusion honestly
    (``false_certificate == 0`` while correctly reporting withholding), and is
    sensitive enough to catch a forged disagreement.
"""

from __future__ import annotations

import os
import sys
from fractions import Fraction

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

import pytest  # noqa: E402

from d2t_rna.t2.fixtures import (  # noqa: E402
    near_collision,
    no_cycle,
    strict_separation,
    symmetric_states,
    two_by_two_alternating,
)
from d2t_rna.t2.model import Action, T2FiniteModel  # noqa: E402
from d2t_rna.t2.theorem import collision_or_separation  # noqa: E402

from tests.independent_oracles.t2_raw_discrete_oracle import (  # noqa: E402
    oracle_confusion_accounting,
    raw_collision_witness,
    raw_separation_gamma,
)
from tests.independent_oracles.t2_raw_convex_oracle import (  # noqa: E402
    raw_convex_checker,
    raw_convex_gamma,
)


def _empty_discrete_convex_model() -> T2FiniteModel:
    """``theta_0={(1,0),(0,1)}``, ``theta_1={(1/4,3/4),(3/4,1/4)}`` with an
    *identity* marginal map ``M=(I)`` and an identity action.

    Discrete: no pair ``(p0 in theta_0, p1 in theta_1)`` has ``M p0 == M p1``
    (identity forces ``p0 == p1``, never true) -> ``D`` empty -> vacuous.
    Convex: the segment ``conv(theta_0)`` and ``conv(theta_1)`` intersect (e.g.
    at ``(1/4,3/4)``), so the convex-hull problem has a definite (collision)
    answer that the empty-discrete early return would mask.
    """
    theta0 = ((Fraction(1), Fraction(0)), (Fraction(0), Fraction(1)))
    theta1 = (
        (Fraction(1, 4), Fraction(3, 4)),
        (Fraction(3, 4), Fraction(1, 4)),
    )
    M = ((Fraction(1), Fraction(0)), (Fraction(0), Fraction(1)))
    identity = Action(
        action_id="id",
        channel=(
            (Fraction(1), Fraction(0)),
            (Fraction(0), Fraction(1)),
        ),
    )
    return T2FiniteModel(
        name="empty_discrete_convex",
        n_states=2,
        theta_0=theta0,
        theta_1=theta1,
        marginal_map=M,
        actions=(identity,),
    )


def _raw(model, panel):
    return {
        "theta_0": model.theta_0,
        "theta_1": model.theta_1,
        "marginal_map": model.marginal_map,
        "channels": {a.action_id: a.channel for a in model.actions},
        "panel": panel,
    }


def test_empty_discrete_is_vacuous():
    model = _empty_discrete_convex_model()
    cert = collision_or_separation(model, ["id"])
    # The discrete branch is honestly vacuous (D empty): never a collision cert.
    assert cert.collapsed is True
    assert cert.gamma is None
    assert cert.enumeration_gamma is None
    assert cert.collision_witness is None
    assert cert.status == "IFF"  # vacuous separation


def test_discrete_oracle_agrees_vacuous():
    model = _empty_discrete_convex_model()
    r = _raw(model, ["id"])
    assert raw_separation_gamma(**r) is None  # D empty
    assert raw_collision_witness(**r) is None


def test_convex_oracle_not_short_circuited_by_empty_discrete():
    """The convex-hull problem is a *different* object: even though the discrete
    difference set is empty (vacuous), the convex hulls intersect, so the convex
    oracle must return a definite value rather than being masked by the
    empty-discrete early return."""
    model = _empty_discrete_convex_model()
    r = _raw(model, ["id"])
    gamma, lam0, lam1 = raw_convex_gamma(**r)
    assert gamma is not None, "convex oracle must not be short-circuited"
    # The hulls intersect -> a convex collision exists (gamma == 0), which the
    # discrete vacuous branch completely missed.
    assert abs(gamma - 0.0) < 1e-9
    chk = raw_convex_checker(
        theta_0=r["theta_0"], theta_1=r["theta_1"],
        marginal_map=r["marginal_map"], channels=r["channels"], panel=r["panel"],
        lambda0=lam0, lambda1=lam1, gamma=gamma,
    )
    assert chk["verified"] is True, chk["failures"]


def test_convex_conflict_masked_by_discrete_vacuous():
    """The two objects genuinely differ: discrete says 'no admissible difference'
    while convex says 'collision exists'.  Asserting the discrete vacuous result
    as the full answer would mask the convex conflict."""
    model = _empty_discrete_convex_model()
    r = _raw(model, ["id"])
    discrete = raw_separation_gamma(**r)
    gamma, _l0, _l1 = raw_convex_gamma(**r)
    assert discrete is None           # discrete object is vacuous
    assert gamma is not None          # convex object is determinate
    assert gamma == 0.0               # ... and is a real collision


# ---------------------------------------------------------------------------
# honest confusion accounting
# ---------------------------------------------------------------------------

def _verdict(model, panel):
    """Build a per-case verdict dict from the production certificate and the
    independent discrete oracle, honestly."""
    cert = collision_or_separation(model, panel)
    r = _raw(model, panel)
    og = raw_separation_gamma(**r)
    oracle_positive = og is not None  # D non-empty -> a certifiable object exists
    if cert.gamma is None:
        issued = False
        positive_claim = False
    else:
        issued = True
        positive_claim = True
    oracle_disagrees = False
    if issued and positive_claim and oracle_positive:
        oracle_disagrees = (cert.gamma != og)
    return {
        "issued": issued,
        "positive_claim": positive_claim,
        "oracle_positive": oracle_positive,
        "oracle_disagrees": oracle_disagrees,
        "eligible": oracle_positive,
        "declared_no_go": False,
    }


def test_honest_microcases_false_certificate_zero_with_honest_withholding():
    cases = [
        (two_by_two_alternating(), ["full_obs"]),  # separation, issued
        (two_by_two_alternating(), ["row_obs"]),   # collision, issued
        (near_collision(), ["diag"]),              # separation 1/4, issued
        (strict_separation(), ["full_obs"]),       # separation 1, issued
        (no_cycle(), ["a"]),                       # empty D -> withheld (vacuous)
        (symmetric_states(), ["a"]),               # empty D -> withheld (vacuous)
    ]
    verdicts = [_verdict(m, p) for m, p in cases]
    acct = oracle_confusion_accounting(verdicts)
    # No forged certificate among issued positive claims.
    assert acct["false_certificate"] == 0
    assert acct["all_issued_agree"] is True
    # No wrongly-withheld real certificate.
    assert acct["false_no_go"] == 0
    assert acct["incorrect_rejection"] == 0
    # Honest withholding accounting: the two empty-D cases are correctly withheld
    # and reported as such (not hidden).
    assert acct["correct_withholding"] == 2
    assert acct["vacuous_count"] == 2
    # Coverage over eligible (non-vacuous) instances is full.
    assert acct["issued_count"] == 4
    assert acct["coverage"] == 1.0


def test_confusion_accounting_catches_forged_certificate():
    """The accounting is not trivially always-zero: a forged positive certificate
    that disagrees with the oracle must be reported as a false certificate."""
    honest = _verdict(two_by_two_alternating(), ["full_obs"])
    forged = dict(honest)
    forged["oracle_disagrees"] = True  # tamper: oracle rejects the positive claim
    acct = oracle_confusion_accounting([honest, forged])
    assert acct["false_certificate"] == 1
    assert acct["all_issued_agree"] is False


def test_confusion_accounting_reports_incorrect_rejection():
    """If production wrongly withholds a certifiable positive result (a real
    false-no-go bug), the accounting must surface it rather than claiming no
    errors among issued certificates."""
    honest = _verdict(two_by_two_alternating(), ["full_obs"])
    wrongly_withheld = dict(honest)
    wrongly_withheld["issued"] = False
    wrongly_withheld["positive_claim"] = False
    wrongly_withheld["declared_no_go"] = True  # production signalled NO_GO
    acct = oracle_confusion_accounting([honest, wrongly_withheld])
    assert acct["false_no_go"] == 1
    assert acct["incorrect_rejection"] == 1
    assert acct["coverage"] == 0.5
