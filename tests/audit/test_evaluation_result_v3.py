"""P0-3: EvaluationResultV3, Bayes/randomized minimax, and abstention.

Contract fixed tests:

    P0=(1,0), P1=(1/2,1/2), n=1:
        bayes_average_error      = 1/4
        randomized_minimax_error = 1/3

    CA_p1, n=4 (p0=(1/4,3/4), p1=(0,1)):
        bayes_average_error      = 81/512
        randomized_minimax_error = 81/337

Plus >= 3 exact fixtures x abstain_ratio in {1, 2}, checking per-hypothesis
quantities and the partition/sum identities.  All assertions call the
production API (``compute_evaluation_result`` / ``EvaluationResultV3``); they
do not reimplement a parallel solver.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from d2t_rna.evaluation.result import (
    EvaluationResultMigrationError,
    EvaluationResultV3,
    EvaluationStatus,
    compute_evaluation_result,
    legacy_oracle_minimax_error,
)


class _LegacyStub:
    def __init__(self, value):
        self.minimax_error = value


# ---------------------------------------------------------------------------
# 1. Contract fixed fixtures
# ---------------------------------------------------------------------------

def test_fixed_counterexample_bayes_vs_minimax():
    p0 = (Fraction(1), Fraction(0))
    p1 = (Fraction(1, 2), Fraction(1, 2))
    r = compute_evaluation_result(p0, p1, 1)
    assert r.bayes_average_error == Fraction(1, 4)
    assert r.randomized_minimax_error == Fraction(1, 3)
    assert r.randomized_minimax_error > r.bayes_average_error
    assert r.status == EvaluationStatus.COMPUTED.value
    assert r.estimand == "RANDOMIZED_MINIMAX_ERROR"


def test_fixed_ca_p1_n4():
    # CA_p1 = catalog class CA, pair 1: p0=(1/4,3/4), p1=(0,1), n=4.
    p0 = (Fraction(1, 4), Fraction(3, 4))
    p1 = (Fraction(0), Fraction(1))
    r = compute_evaluation_result(p0, p1, 4)
    assert r.bayes_average_error == Fraction(81, 512)
    assert r.randomized_minimax_error == Fraction(81, 337)


# ---------------------------------------------------------------------------
# 2. Abstention: per-hypothesis quantities and sum identities
# ---------------------------------------------------------------------------

_FIXTURES = [
    ((Fraction(1), Fraction(0)), (Fraction(1, 2), Fraction(1, 2)), 1),
    ((Fraction(1, 4), Fraction(3, 4)), (Fraction(0), Fraction(1)), 4),
    ((Fraction(1, 3), Fraction(2, 3)), (Fraction(1, 2), Fraction(1, 2)), 2),
]


@pytest.mark.parametrize("p0,p1,n", _FIXTURES)
@pytest.mark.parametrize("abstain_ratio", [Fraction(1), Fraction(2)])
def test_abstention_per_hypothesis_identities(p0, p1, n, abstain_ratio):
    r = compute_evaluation_result(p0, p1, n, abstain_ratio=abstain_ratio)
    assert r.status == EvaluationStatus.COMPUTED.value
    # per-hypothesis partition identities (also enforced by the dataclass)
    assert r.alpha + r.kappa_0 + r.rho_0 == 1
    assert r.beta + r.kappa_1 + r.rho_1 == 1
    assert r.abstain_probability == (r.rho_0 + r.rho_1) / 2
    # all quantities are probabilities
    for v in (r.alpha, r.beta, r.kappa_0, r.kappa_1, r.rho_0, r.rho_1,
              r.abstain_probability, r.bayes_average_error):
        assert 0 <= v <= 1
    assert r.randomized_minimax_error is not None
    assert 0 <= r.randomized_minimax_error <= 1


@pytest.mark.parametrize("p0,p1,n", _FIXTURES)
def test_abstention_never_folded_into_minimax(p0, p1, n):
    """The no-abstention minimax must not change when abstention is widened."""
    r1 = compute_evaluation_result(p0, p1, n, abstain_ratio=Fraction(1))
    r2 = compute_evaluation_result(p0, p1, n, abstain_ratio=Fraction(2))
    assert r1.randomized_minimax_error == r2.randomized_minimax_error
    # Bayes average is likewise independent of the abstention band.
    assert r1.bayes_average_error == r2.bayes_average_error
    # a wider band can only keep or increase abstention
    assert r2.abstain_probability >= r1.abstain_probability


def test_abstention_ratio_one_is_no_abstention_for_distinct_laws():
    p0 = (Fraction(1), Fraction(0))
    p1 = (Fraction(1, 2), Fraction(1, 2))
    r = compute_evaluation_result(p0, p1, 1, abstain_ratio=Fraction(1))
    assert r.rho_0 == 0
    assert r.rho_1 == 0
    assert r.alpha + r.beta + r.kappa_0 + r.kappa_1 == 2


# ---------------------------------------------------------------------------
# 3. Legacy minimax_error: no silent alias
# ---------------------------------------------------------------------------

def test_legacy_reader_returns_typed_bayes():
    stub = _LegacyStub(Fraction(1, 4))
    v = legacy_oracle_minimax_error(stub)
    assert v == Fraction(1, 4)
    # explicit non-legacy read is rejected
    with pytest.raises(EvaluationResultMigrationError):
        legacy_oracle_minimax_error(stub, typed_legacy=False)


def test_legacy_reader_missing_field_raises():
    with pytest.raises(EvaluationResultMigrationError):
        legacy_oracle_minimax_error(_LegacyStub(None))


# ---------------------------------------------------------------------------
# 4. WITHHELD status: Bayes never substituted for minimax
# ---------------------------------------------------------------------------

def test_withheld_minimax_never_substitutes_bayes():
    p0 = (Fraction(1), Fraction(0))
    p1 = (Fraction(1, 2), Fraction(1, 2))
    r = compute_evaluation_result(p0, p1, 1, withhold_minimax=True)
    assert r.status == EvaluationStatus.WITHHELD_RANDOMIZED_MINIMAX_UNAVAILABLE.value
    assert r.randomized_minimax_error is None
    # Bayes is still reported exactly, but is NOT labelled as minimax.
    assert r.bayes_average_error == Fraction(1, 4)
    with pytest.raises(ValueError):
        # cannot construct COMPUTED with a None minimax
        EvaluationResultV3(
            bayes_average_error=Fraction(1, 4),
            randomized_minimax_error=None,
            alpha=Fraction(0), beta=Fraction(0),
            kappa_0=Fraction(1), kappa_1=Fraction(1),
            rho_0=Fraction(0), rho_1=Fraction(0),
            abstain_probability=Fraction(0),
        )


# ---------------------------------------------------------------------------
# 5. Serialization round-trip
# ---------------------------------------------------------------------------

def test_serialization_round_trip():
    p0 = (Fraction(1, 4), Fraction(3, 4))
    p1 = (Fraction(0), Fraction(1))
    r = compute_evaluation_result(p0, p1, 4, abstain_ratio=Fraction(2))
    d = r.to_dict()
    assert d["schema_id"] == "d2t_rna.evaluation_result.v3"
    assert d["bayes_average_error"] == "81/512"
    r2 = EvaluationResultV3.from_dict(d)
    assert r2 == r


def test_schema_required_fields_present():
    """The serialized record carries every contract field."""
    import json
    import os
    p0 = (Fraction(1), Fraction(0))
    p1 = (Fraction(1, 2), Fraction(1, 2))
    r = compute_evaluation_result(p0, p1, 1)
    d = r.to_dict()
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    with open(os.path.join(repo, "schemas",
                           "evaluation_result_v3.schema.json")) as fh:
        schema = json.load(fh)
    assert schema["$id"] == "d2t_rna.evaluation_result.v3"
    for field in schema["required"]:
        assert field in d, f"missing field {field}"
