"""Replicate-aware observation models for measured RNA data (P0-5).

The v7 audit (§3.4, blocker 3) establishes that the *arbitrary-clamp* model
``p = clamp(normalized_reactivity, floor, 1-floor)`` used by the measured
cases treats a relative normalized reactivity as a Bernoulli probability
without using measurement error, per-position signal, or per-replicate counts,
while the provenance claimed ``per_position_error_used=True``.  This module
implements the three candidate observation models required by P0-5's glycine
replicate kill test:

* ``DirectClampModel`` -- clamp a single normalized reactivity profile to
  ``[floor, 1-floor]`` and treat it as a Bernoulli parameter (the current,
  non-error-aware behavior).
* ``EqualLawNullModel`` -- the null that the two conditions share the same law
  (pooled probability); a no-separation baseline.
* ``WithinReplicateCountModel`` -- a per-replicate categorical/count likelihood
  (binomial, optionally beta-binomial for overdispersion).  This is the only
  model that can identify between-replicate variance and give ``n``,
  ``cost``, ``coverage`` and ``abstention`` experimental meaning.

**Archive qualification.**  The glycine RDAT archive (BSUGLY_DMS_0013/0014)
contains *only* merged, normalized reactivity; its COMMENT states the two
independent replicates were "analyzed separately then merged and normalized".
It therefore provides **no per-replicate raw counts**, so
``WithinReplicateCountModel`` can be unit-tested on synthetic fixtures but
cannot be fit to the real glycine archive.  That is a permanent
data-qualification failure for the post-selection cross-replicate diagnostic
(status ``BLOCKED_PENDING_ARCHIVE_QUALIFICATION``), and both merged replicates
are historically exposed (the same outcome profile selected the probe and
determined ``n``).

A post-selection diagnostic compares log-score / calibration / conditional
errors of the models on a *frozen* probe/rule using a diagnostic replicate not
used to select the probe.  Because both real glycine replicates were merged
before probe selection, neither can serve as a cold diagnostic replicate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from math import lgamma, log
from typing import Mapping, Sequence

# Post-selection diagnostic qualification status for the glycine case.
BLOCKED_PENDING_ARCHIVE_QUALIFICATION = "BLOCKED_PENDING_ARCHIVE_QUALIFICATION"
QUALIFIED = "QUALIFIED"
REPLAY_MISSING = "RAW_COUNT_REPLAY_UNAVAILABLE"


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _bin_logpmf(k: int, n: int, p: float) -> float:
    """Log of the binomial probability mass at ``k`` successes in ``n`` trials."""
    if not (0 <= p <= 1):
        raise ValueError(f"binomial parameter p={p!r} out of [0,1]")
    if k < 0 or k > n:
        return float("-inf")
    if p == 0:
        return 0.0 if k == 0 else float("-inf")
    if p == 1:
        return 0.0 if k == n else float("-inf")
    return (
        lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)
        + k * log(p)
        + (n - k) * log(1 - p)
    )


@dataclass(frozen=True)
class DirectClampModel:
    """Non-error-aware model: p = clamp(normalized reactivity, floor, 1-floor).

    This is the model the current measured cases use.  It ignores measurement
    error/replicates and is the *status quo* against which the replicate-aware
    model is compared in the kill test.
    """

    apo_reactivity: Sequence[float]
    bound_reactivity: Sequence[float]
    floor: float = 0.01

    def __post_init__(self) -> None:
        if len(self.apo_reactivity) != len(self.bound_reactivity):
            raise ValueError("apo/bound reactivity length mismatch")
        if not (0 < self.floor < Fraction(1, 2)):
            raise ValueError("floor must lie strictly in (0, 1/2)")

    def p(self, condition: str, u: int) -> float:
        """P(reads reactive/unpaired) at position ``u`` under ``condition``."""
        r = self.bound_reactivity[u] if condition == "bound" else self.apo_reactivity[u]
        return _clamp(r, self.floor, 1 - self.floor)

    def log_score_binary(self, condition: str, u: int, y: int) -> float:
        p = self.p(condition, u)
        return _bin_logpmf(y, 1, p)


@dataclass(frozen=True)
class EqualLawNullModel:
    """Null model: both conditions share the same per-position law.

    Pooled probability ``p(u) = (p_apo(u) + p_bound(u))/2`` regardless of
    condition.  Used as a no-separation baseline in the likelihood comparison.
    """

    apo_reactivity: Sequence[float]
    bound_reactivity: Sequence[float]
    floor: float = 0.01

    def __post_init__(self) -> None:
        if len(self.apo_reactivity) != len(self.bound_reactivity):
            raise ValueError("apo/bound reactivity length mismatch")

    def pooled_p(self, u: int) -> float:
        dp = DirectClampModel(self.apo_reactivity, self.bound_reactivity, self.floor)
        return (dp.p("apo", u) + dp.p("bound", u)) / 2

    def log_score_binary(self, condition: str, u: int, y: int) -> float:
        p = self.pooled_p(u)
        return _bin_logpmf(y, 1, p)


@dataclass(frozen=True)
class WithinReplicateCountModel:
    """Per-replicate count likelihood (binomial; optionally beta-binomial).

    ``replicate_counts[rep][condition][u] = (k, n)`` where ``k`` reactive
    reads in ``n`` total reads at position ``u`` in replicate ``rep`` under
    ``condition``.  This is the only model that can identify
    between-replicate variance.  Requires per-replicate raw counts, which the
    real glycine archive does not provide.
    """

    replicate_counts: Mapping[str, Mapping[str, Sequence[tuple[int, int]]]]
    dispersion: float | None = None  # beta-binomial overdispersion eta (>=0)

    def __post_init__(self) -> None:
        if self.dispersion is not None and self.dispersion < 0:
            raise ValueError("dispersion must be non-negative")

    def _p_rep(self, rep: str, condition: str, u: int) -> float:
        try:
            k, n = self.replicate_counts[rep][condition][u]
        except (KeyError, IndexError) as e:  # pragma: no cover - defensive
            raise ValueError(f"missing counts for rep={rep} condition={condition} u={u}") from e
        if n <= 0:
            raise ValueError("zero total reads in replicate count")
        return k / n

    def log_likelihood(self) -> float:
        """Total log-likelihood over all replicates/positions."""
        total = 0.0
        for rep, conds in self.replicate_counts.items():
            for condition, positions in conds.items():
                for u, (k, n) in enumerate(positions):
                    p = self._p_rep(rep, condition, u)
                    if self.dispersion is None:
                        total += _bin_logpmf(k, n, p)
                    else:
                        total += _beta_binom_logpmf(k, n, p, self.dispersion)
        return total

    def log_score_binary(self, condition: str, u: int, y: int) -> float:
        # Aggregate counts across replicates for a single binary score.
        k = n = 0
        for rep in self.replicate_counts:
            rk, rn = self.replicate_counts[rep][condition][u]
            k += rk
            n += rn
        return _bin_logpmf(k, n, self._p_rep(next(iter(self.replicate_counts)), condition, u))


def _beta_binom_logpmf(k: int, n: int, p: float, eta: float) -> float:
    """Log PMF of a re-parameterised beta-binomial with mean ``p`` and
    overdispersion ``eta`` (0 = binomial)."""
    if eta == 0:
        return _bin_logpmf(k, n, p)
    a = p / eta
    b = (1 - p) / eta
    lhs = lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)
    rhs = (
        lgamma(k + a)
        + lgamma(n - k + b)
        + lgamma(a + b)
        - lgamma(n + a + b)
        - lgamma(a)
        - lgamma(b)
    )
    return lhs + rhs


@dataclass(frozen=True)
class PostSelectionDiagnostic:
    """Result of comparing candidate models on a post-selection diagnostic set."""

    log_score: Mapping[str, float]  # model name -> total log-likelihood on diagnostic data
    conditional_errors: Mapping[str, Mapping[str, float]]  # model -> {alpha,beta,abstain}
    verdict: str
    notes: tuple[str, ...] = ()


def run_post_selection_diagnostic(
    models: Mapping[str, object],
    diagnostic: Sequence[tuple[str, int, int]],  # (condition, u, y) frozen-rule data
    probe_indices: Sequence[int],
    rule=lambda cond, u, y, model: _lrt_label(model, cond, u),
) -> PostSelectionDiagnostic:
    """Compare models on a frozen probe/rule over a diagnostic replicate.

    ``diagnostic`` is a list of ``(condition, u, y)`` observations on the
    diagnostic replicate (which must not have been used to select the probes).
    ``probe_indices`` are the frozen post-selection probe positions.
    """
    log_score: dict[str, float] = {}
    cond_errors: dict[str, dict[str, float]] = {}
    for name, model in models.items():
        score = 0.0
        alpha = beta = abstain = 0.0
        n0 = n1 = 0
        for cond, u, y in diagnostic:
            if u not in probe_indices:
                continue
            score += _score(model, cond, u, y)
            label = rule(cond, u, y, model)
            if cond == "apo":
                n0 += 1
                if label == "H1":
                    alpha += 1
                elif label == "abstain":
                    abstain += 1
            else:
                n1 += 1
                if label == "H0":
                    beta += 1
                elif label == "abstain":
                    abstain += 1
        log_score[name] = score
        cond_errors[name] = {
            "alpha": alpha / n0 if n0 else float("nan"),
            "beta": beta / n1 if n1 else float("nan"),
            "abstain": abstain / (n0 + n1) if (n0 + n1) else float("nan"),
        }
    best = max(log_score, key=log_score.get)
    verdict = f"best_log_score={best}"
    return PostSelectionDiagnostic(log_score, cond_errors, verdict)


def _score(model, cond: str, u: int, y: int) -> float:
    if hasattr(model, "log_likelihood"):
        # count model: score the single binary event via its binomial law
        return model.log_score_binary(cond, u, y)
    return model.log_score_binary(cond, u, y)


def _lrt_label(model, cond: str, u: int) -> str:
    """Frozen likelihood-ratio / threshold rule label (H0 / H1 / abstain)."""
    try:
        p0 = model.p("apo", u)
        p1 = model.p("bound", u)
    except (AttributeError, TypeError):
        return "abstain"
    if abs(p1 - p0) < 1e-9:
        return "abstain"
    return "H1" if p1 > p0 else "H0"