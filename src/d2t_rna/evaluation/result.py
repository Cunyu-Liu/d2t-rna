"""EvaluationResultV3: exact Bayes-average vs randomized-minimax, with abstention.

This module is the production result type for the v7 audit repair (P0-3).  It
replaces the legacy conflation in which the equal-prior Bayes average error was
mislabelled ``minimax_error``.  The two quantities are genuinely distinct, e.g.
``P0=(1,0)``, ``P1=(1/2,1/2)``, ``n=1``: Bayes average ``1/4`` vs true
randomized minimax ``1/3``; and ``CA_p1`` (``p0=(1/4,3/4)``,
``p1=(0,1)``, ``n=4``): Bayes ``81/512`` vs randomized minimax ``81/337``.

Semantics (contract P0-3):

* ``bayes_average_error`` = equal-prior Bayes average error
  ``(1/2) sum_z min(P0^n(z), P1^n(z))``.
* ``randomized_minimax_error`` = minimax error of the optimal *randomised*
  proper (no-abstention) classifier over the product observation law, solved
  as an exact rational LP.  It is the **Track R primary** endpoint; Bayes is
  secondary.
* Abstention is reported separately via ``alpha,beta,kappa_0,kappa_1,
  rho_0,rho_1`` and ``abstain_probability``.  Unless an explicit
  ``abstention_loss_*`` is registered, abstention is **never** folded back into
  ``randomized_minimax_error`` (which remains the no-abstention minimax).
* If the randomized minimax LP cannot be solved (unsupported / too large), the
  result is ``status == WITHHELD_RANDOMIZED_MINIMAX_UNAVAILABLE`` and
  ``randomized_minimax_error is None``; Bayes is **never** substituted.

Legacy ``OracleResult.minimax_error`` must not silently alias to any V3 risk
field.  It is only readable through :func:`legacy_oracle_minimax_error`, which
returns an explicit typed legacy-Bayes value or raises a migration error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from typing import Sequence

from d2t_rna.t2.decision import (
    conditional_rule_errors,
    exact_bayes_average_error,
    exact_randomized_minimax_error,
)

SCHEMA_ID = "d2t_rna.evaluation_result.v3"
SCHEMA_VERSION = "3"


class EvaluationStatus(str, Enum):
    COMPUTED = "COMPUTED"
    WITHHELD_RANDOMIZED_MINIMAX_UNAVAILABLE = (
        "WITHHELD_RANDOMIZED_MINIMAX_UNAVAILABLE"
    )


class Estimand(str, Enum):
    BAYES_AVERAGE_ERROR = "BAYES_AVERAGE_ERROR"
    RANDOMIZED_MINIMAX_ERROR = "RANDOMIZED_MINIMAX_ERROR"


def _frac_str(x: Fraction | None) -> str | None:
    return None if x is None else str(x)


def _parse_frac(s: str | None) -> Fraction | None:
    return None if s is None else Fraction(s)


@dataclass(frozen=True)
class EvaluationResultV3:
    """Exact evaluation result: Bayes average and randomised minimax separated.

    ``estimand`` declares which quantity is the *primary* endpoint of the
    enclosing task (Track R primary is ``RANDOMIZED_MINIMAX_ERROR``); it is a
    statement about the task, not a re-scaling of the risk fields.
    """

    bayes_average_error: Fraction
    randomized_minimax_error: Fraction | None
    alpha: Fraction
    beta: Fraction
    kappa_0: Fraction
    kappa_1: Fraction
    rho_0: Fraction
    rho_1: Fraction
    abstain_probability: Fraction
    abstention_loss_name: str | None = None
    abstention_loss_value: Fraction | None = None
    estimand: str = Estimand.RANDOMIZED_MINIMAX_ERROR.value
    status: str = EvaluationStatus.COMPUTED.value
    schema_id: str = SCHEMA_ID
    schema_version: str = SCHEMA_VERSION

    # -------- invariants ---------------------------------------------------
    def __post_init__(self) -> None:
        if self.schema_id != SCHEMA_ID:
            raise ValueError(f"schema_id must be {SCHEMA_ID!r}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        if self.status == EvaluationStatus.COMPUTED.value:
            if self.randomized_minimax_error is None:
                raise ValueError(
                    "COMPUTED requires randomized_minimax_error to be set"
                )
        elif self.status == (
            EvaluationStatus.WITHHELD_RANDOMIZED_MINIMAX_UNAVAILABLE.value
        ):
            if self.randomized_minimax_error is not None:
                raise ValueError(
                    "WITHHELD requires randomized_minimax_error to be None"
                )
        else:
            raise ValueError(f"unknown status {self.status!r}")
        # per-hypothesis partition identities
        if self.alpha + self.kappa_0 + self.rho_0 != 1:
            raise ValueError("alpha + kappa_0 + rho_0 must equal 1")
        if self.beta + self.kappa_1 + self.rho_1 != 1:
            raise ValueError("beta + kappa_1 + rho_1 must equal 1")
        if not (self.abstention_loss_name is None) == (
            self.abstention_loss_value is None
        ):
            raise ValueError(
                "abstention_loss_name and abstention_loss_value must be set "
                "together (or both None)"
            )
        if self.abstain_probability != (self.rho_0 + self.rho_1) / 2:
            raise ValueError(
                "abstain_probability must equal (rho_0 + rho_1)/2"
            )

    # -------- serialization ------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "status": self.status,
            "estimand": self.estimand,
            "bayes_average_error": _frac_str(self.bayes_average_error),
            "randomized_minimax_error": _frac_str(self.randomized_minimax_error),
            "alpha": _frac_str(self.alpha),
            "beta": _frac_str(self.beta),
            "kappa_0": _frac_str(self.kappa_0),
            "kappa_1": _frac_str(self.kappa_1),
            "rho_0": _frac_str(self.rho_0),
            "rho_1": _frac_str(self.rho_1),
            "abstain_probability": _frac_str(self.abstain_probability),
            "abstention_loss_name": self.abstention_loss_name,
            "abstention_loss_value": _frac_str(self.abstention_loss_value),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationResultV3":
        return cls(
            bayes_average_error=_parse_frac(data["bayes_average_error"]),
            randomized_minimax_error=_parse_frac(
                data["randomized_minimax_error"]
            ),
            alpha=_parse_frac(data["alpha"]),
            beta=_parse_frac(data["beta"]),
            kappa_0=_parse_frac(data["kappa_0"]),
            kappa_1=_parse_frac(data["kappa_1"]),
            rho_0=_parse_frac(data["rho_0"]),
            rho_1=_parse_frac(data["rho_1"]),
            abstain_probability=_parse_frac(data["abstain_probability"]),
            abstention_loss_name=data.get("abstention_loss_name"),
            abstention_loss_value=_parse_frac(
                data.get("abstention_loss_value")
            ),
            estimand=data.get(
                "estimand", Estimand.RANDOMIZED_MINIMAX_ERROR.value
            ),
            status=data.get("status", EvaluationStatus.COMPUTED.value),
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )


class EvaluationResultMigrationError(RuntimeError):
    """Raised when legacy ``minimax_error`` is read outside the legacy reader."""


def compute_evaluation_result(
    p0: Sequence[Fraction],
    p1: Sequence[Fraction],
    n: int,
    abstain_ratio: Fraction | int = Fraction(1),
    abstention_loss_name: str | None = None,
    abstention_loss_value: Fraction | None = None,
    withhold_minimax: bool = False,
    estimand: str = Estimand.RANDOMIZED_MINIMAX_ERROR.value,
) -> EvaluationResultV3:
    """Compute a complete ``EvaluationResultV3`` from the raw single-action laws.

    ``abstain_ratio >= 1`` scales the likelihood-ratio band: the rule declares
    ``H0`` when ``P1/P0 <= 1/k``, ``H1`` when ``P1/P0 >= k``, and abstains
    otherwise.  ``abstain_ratio == 1`` is the no-abstention (ties-abstain) rule.

    ``withhold_minimax=True`` produces
    ``WITHHELD_RANDOMIZED_MINIMAX_UNAVAILABLE`` with ``randomized_minimax_error
    is None`` (used when the exact LP is unsupported / out of scale); Bayes is
    always reported, but is never substituted for the minimax endpoint.
    """
    k = Fraction(abstain_ratio)
    if k < 1:
        raise ValueError("abstain_ratio must be >= 1")
    lower = 1 / k
    upper = k

    bayes = exact_bayes_average_error(p0, p1, n)
    rule = conditional_rule_errors(p0, p1, n, lower, upper)

    if withhold_minimax:
        mm = None
        status = EvaluationStatus.WITHHELD_RANDOMIZED_MINIMAX_UNAVAILABLE.value
    else:
        try:
            mm = exact_randomized_minimax_error(p0, p1, n)
        except Exception as exc:  # noqa: BLE001 - fail closed, do not use Bayes
            raise EvaluationResultMigrationError(
                "randomized minimax LP unavailable and Bayes will NOT be "
                "substituted; use withhold_minimax=True to emit a WITHHELD "
                "status"
            ) from exc
        status = EvaluationStatus.COMPUTED.value

    abstain_probability = (rule.rho_0 + rule.rho_1) / 2

    return EvaluationResultV3(
        bayes_average_error=bayes,
        randomized_minimax_error=mm,
        alpha=rule.alpha,
        beta=rule.beta,
        kappa_0=rule.kappa_0,
        kappa_1=rule.kappa_1,
        rho_0=rule.rho_0,
        rho_1=rule.rho_1,
        abstain_probability=abstain_probability,
        abstention_loss_name=abstention_loss_name,
        abstention_loss_value=abstention_loss_value,
        estimand=estimand,
        status=status,
    )


def legacy_oracle_minimax_error(result, *, typed_legacy: bool = True) -> Fraction:
    """Read the legacy ``OracleResult.minimax_error`` field, never silently.

    The legacy field actually stores the equal-prior Bayes average error.  By
    default (``typed_legacy=True``) it is returned as the typed legacy-Bayes
    value; the caller must opt into this.  There is **no** silent alias to any
    V3 risk field.

    If ``typed_legacy=False`` and the caller is not a registered legacy reader,
    we raise ``EvaluationResultMigrationError`` (defensive migration gate).
    """
    value = getattr(result, "minimax_error", None)
    if value is None:
        raise EvaluationResultMigrationError(
            "legacy OracleResult has no minimax_error field"
        )
    if not typed_legacy:
        raise EvaluationResultMigrationError(
            "OracleResult.minimax_error is a mislabelled Bayes average error; "
            "migrate to EvaluationResultV3.bayes_average_error / "
            "randomized_minimax_error instead of silently aliasing"
        )
    return value
