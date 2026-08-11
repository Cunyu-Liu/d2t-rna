"""T2b exact collision-or-separation theorem (contract sections 5.2, T2-2).

For a finite registered RNA model with cross-class difference set ``D`` and a
panel ``S``, define the robust action-image separation

    gamma(S) = inf_{v in D} max_{u in S} || B_u v ||_1 .

The T2b theorem states the exact logic:

* ``gamma(S) = 0``  <=>  there exists a nonzero admissible ``v in D`` with
  ``B_u v = 0`` for every ``u in S``.  Such a vector is a *collision witness*:
  the complete observation law (hence the full product law) is identical under
  both model classes on every selected action, so no rule based on ``S`` can
  extract positive information from that witness.
* ``gamma(S) > 0``  <=>  no such collision witness exists; the attained witness
  ``v*`` with ``max_u ||B_u v*|| = gamma(S) > 0`` is a *separation witness*.

For a finite catalog the infimum over ``D`` is attained, so the theorem is
``IFF``.  ``NECESSARY_ONLY`` / ``SUFFICIENT_ONLY`` are reserved for the
non-atomic / infimum-only obstruction case (contract section 5.2 boundary),
where only one direction is certified.

For a finite catalog the separation ``gamma(S)`` is computed exactly by
exhaustive enumeration of the discrete difference set ``D`` (the
``DISCRETE_CATALOG`` object).  ``build_gamma_lp`` builds the *separate*
convex-hull LP, which optimises over the convex hulls of the catalogs and
solves a different problem; it is retained only as an explicit convex /
diagnostic object and is never used as a gate on the discrete certificate.

**P0-2 repair.**  The DISCRETE_CATALOG path certifies purely from exact
enumeration and never invokes the convex-hull LP.  Previously the discrete
path called the convex LP unconditionally and wrongly returned
``COUNTEREXAMPLE, gamma=None`` for a legitimate discrete certificate
(``gamma_l1=1/2``) whenever the convex hulls overlapped (``gamma=0``).
The raw separation is reported as action-level L1 (``gamma``) and, when the
declared ``TheoremSpec`` measure is a TV, as ``gamma_tv = gamma / 2 in [0,1]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Sequence

from .model import Action, T2FiniteModel
from .spec import (
    MEASURE_PRODUCT_TV,
    UNCERTAINTY_CONVEX,
    TheoremSpec,
    tv_from_l1,
)
from .witness import collision_witness, iter_differences, norm_l1

_Status = str  # "IFF" | "NECESSARY_ONLY" | "SUFFICIENT_ONLY" | "COUNTEREXAMPLE"


@dataclass(frozen=True)
class T2bCertificate:
    """A T2b collision-or-separation certificate (contract section 6.4)."""

    theorem: str = "T2b"
    status: _Status = "IFF"
    gamma: Fraction | None = None
    gamma_tv: Fraction | None = None  # gamma expressed as TV (gamma/2), in [0,1]
    collision_witness: tuple[Fraction, ...] | None = None
    separation_witness: tuple[Fraction, ...] | None = None
    panel: tuple[str, ...] = ()
    lp_optimal: Fraction | None = None
    lp_primal_feasible: bool = False
    lp_dual_feasible: bool = False
    lp_strong_duality: bool = False
    enumeration_gamma: Fraction | None = None
    enumeration_matches_lp: bool = False
    collapsed: bool = False  # D empty -> vacuous separation
    spec: TheoremSpec = field(default_factory=TheoremSpec)
    notes: tuple[str, ...] = field(default_factory=tuple)


def _action_image(action: Action, v: Sequence[Fraction]) -> tuple[Fraction, ...]:
    return tuple(
        sum(action.channel[y][w] * v[w] for w in range(len(v)))
        for y in range(action.alphabet_size())
    )


def build_gamma_lp(
    model: T2FiniteModel, panel: Sequence[str]
) -> tuple[list[int], list[Fraction], list[list[Fraction]], list[Fraction], dict]:
    """Build the standard-form LP ``min c^T x, A x = b, x >= 0`` for ``gamma(S)``.

    Returns ``(n_real_dims, c, A, b, layout)`` where ``layout`` maps role names
    to their run of column indices:

    * ``lambda0``  convex weights over ``theta_0`` (length J0);
    * ``lambda1``  convex weights over ``theta_1`` (length J1);
    * ``w``        per-(action, outcome) L1 epigraph variables (length S*Y);
    * ``t``        the objective (max action-image L1 norm).

    Inequality constraints are converted to equality form with non-negative
    slack columns, so every RHS is ``>= 0`` and the two-phase simplex starts
    from a feasible artificial basis.

    .. note:: This LP optimizes over the *convex hulls* of the two catalogs.
       It is the ``CONVEX_HULL`` uncertainty problem and is deliberately kept
       separate from the discrete enumeration (P0-3).  A certificate issued
       from this LP must declare ``uncertainty_kind=CONVEX_HULL``.
    """
    selected = tuple(a for a in model.actions if a.action_id in set(panel))
    if len(selected) != len(set(panel)):
        raise ValueError("panel refers to an unknown or duplicate action")

    J0 = len(model.theta_0)
    J1 = len(model.theta_1)
    R = len(model.marginal_map)
    S = len(selected)
    n_y = sum(a.alphabet_size() for a in selected)  # total outcomes across panel

    # real decision variables (before slacks): lambda0 + lambda1 + w + t
    n_real = J0 + J1 + n_y + 1
    w_start = J0 + J1
    t_col = J0 + J1 + n_y

    # inequality rows being slack-converted:
    #   per (u,y):  (B_u v)_y - w_{uy} <= 0   and  -(B_u v)_y - w_{uy} <= 0
    #   per u:      sum_y w_{uy} - t <= 0
    n_ineq = 2 * n_y + S
    n_total = n_real + n_ineq
    slack_start = n_real

    rows: list[list[Fraction]] = []
    rhs: list[Fraction] = []
    # Running index of the inequality row being appended (0-based within the
    # block that starts after the 2 + R equality rows).
    ineq_idx = 0

    def new_row() -> list[Fraction]:
        return [Fraction(0) for _ in range(n_total)]

    # --- equality: sum_j lambda0_j = 1
    row = new_row()
    for j in range(J0):
        row[j] = Fraction(1)
    rows.append(row)
    rhs.append(Fraction(1))

    # --- equality: sum_k lambda1_k = 1
    row = new_row()
    for k in range(J1):
        row[J0 + k] = Fraction(1)
    rows.append(row)
    rhs.append(Fraction(1))

    # --- M-alignment: for each marginal row r, row_r . (x_1 - x_0) = 0
    for r in range(R):
        row = new_row()
        for k in range(J1):
            th1 = model.theta_1[k]
            row[J0 + k] += sum(model.marginal_map[r][w] * th1[w] for w in range(model.n_states))
        for j in range(J0):
            th0 = model.theta_0[j]
            row[j] -= sum(model.marginal_map[r][w] * th0[w] for w in range(model.n_states))
        rows.append(row)
        rhs.append(Fraction(0))

    # --- L1 epigraph inequalities (B_u v)_y - w_{uy} <= 0 and its negative.
    # Here (B_u v)_y = sum_w Q_u[y][w] (x1[w] - x0[w]) with
    #   x1[w] = sum_k lambda1_k theta_1[k][w],  x0[w] = sum_j lambda0_j theta_0[j][w].
    # So the lambda-coefficients are the channel composed with each catalog
    # distribution, NOT the raw channel entry at the catalog index.
    w_off = 0
    for u in selected:
        Yu = u.alphabet_size()
        for y in range(Yu):
            c1 = [Fraction(0) for _ in range(J1)]
            c0 = [Fraction(0) for _ in range(J0)]
            for w in range(model.n_states):
                q = u.channel[y][w]
                for k in range(J1):
                    c1[k] += q * model.theta_1[k][w]
                for j in range(J0):
                    c0[j] += q * model.theta_0[j][w]
            # (B_u v)_y - w_{uy} <= 0  ->  + slack = 0
            row = new_row()
            for k in range(J1):
                row[J0 + k] += c1[k]
            for j in range(J0):
                row[j] -= c0[j]
            row[w_start + w_off + y] = Fraction(-1)
            row[slack_start + ineq_idx] = Fraction(1)
            rows.append(row)
            rhs.append(Fraction(0))
            ineq_idx += 1

            # -(B_u v)_y - w_{uy} <= 0  ->  + slack = 0
            row = new_row()
            for k in range(J1):
                row[J0 + k] -= c1[k]
            for j in range(J0):
                row[j] += c0[j]
            row[w_start + w_off + y] = Fraction(-1)
            row[slack_start + ineq_idx] = Fraction(1)
            rows.append(row)
            rhs.append(Fraction(0))
            ineq_idx += 1
        w_off += Yu

    # --- for each u: sum_y w_{uy} - t <= 0 -> + slack = 0
    w_off = 0
    for u in selected:
        Yu = u.alphabet_size()
        row = new_row()
        for y in range(Yu):
            row[w_start + w_off + y] = Fraction(1)
        row[t_col] = Fraction(-1)
        row[slack_start + ineq_idx] = Fraction(1)
        rows.append(row)
        rhs.append(Fraction(0))
        ineq_idx += 1
        w_off += Yu

    # objective: min t
    c = [Fraction(0) for _ in range(n_total)]
    c[t_col] = Fraction(1)

    layout = {
        "J0": J0,
        "J1": J1,
        "R": R,
        "n_y": n_y,
        "lambda0": list(range(J0)),
        "lambda1": list(range(J0, J0 + J1)),
        "w": list(range(w_start, w_start + n_y)),
        "t": t_col,
        "n_real": n_real,
        "n_total": n_total,
        "actions": [a.action_id for a in selected],
    }
    return n_real, c, rows, rhs, layout


def _with_tv(cert: T2bCertificate) -> T2bCertificate:
    """Set ``gamma_tv = gamma / 2`` whenever ``gamma`` is not ``None``."""
    if cert.gamma is None:
        return cert
    return replace(cert, gamma_tv=tv_from_l1(cert.gamma))


def collision_or_separation(
    model: T2FiniteModel,
    panel: Sequence[str],
    spec: TheoremSpec | None = None,
) -> T2bCertificate:
    """Determine the exact collision-or-separation status for ``panel``.

    Returns a ``T2bCertificate`` with the direction (``IFF`` for finite
    catalogs), the collision witness (gamma = 0) or separation witness
    (gamma > 0), all computed exactly by enumeration of the discrete
    difference set.

    **P0-2 repair.**  The DISCRETE_CATALOG path is pure exact enumeration and
    does not call the convex-hull LP.  CONVEX_HULL uncertainty and PRODUCT_TV
    separation are not currently certified and return ``UNSUPPORTED_SPEC``.
    ``spec`` declares which uncertainty object and separation measure the
    certificate is about.
    """
    selected = tuple(a for a in model.actions if a.action_id in set(panel))
    if len(selected) != len(set(panel)):
        raise ValueError("panel refers to an unknown or duplicate action")
    if spec is None:
        spec = TheoremSpec()
    # P0-3b fail-closed dispatch (plan Batch 2.2/2.4): only the combinations
    # that are formally supported may run.  CONVEX_HULL uncertainty and
    # PRODUCT_TV separation are NOT currently certified; requesting them
    # returns UNSUPPORTED_SPEC instead of silently running the discrete /
    # action-level engine and mislabelling the result (the exact drift the
    # audit flags).  ACTION_L1 and ACTION_TV over a discrete catalog are the
    # supported, certified objects.
    if spec.uncertainty_kind == UNCERTAINTY_CONVEX:
        return T2bCertificate(
            panel=tuple(panel),
            status="UNSUPPORTED_SPEC",
            gamma=None,
            spec=spec,
            notes=(
                "CONVEX_HULL uncertainty is not a currently supported, "
                "certified object; no formal certificate is issued.",
            ),
        )
    if spec.separation_measure == MEASURE_PRODUCT_TV:
        return T2bCertificate(
            panel=tuple(panel),
            status="UNSUPPORTED_SPEC",
            gamma=None,
            spec=spec,
            notes=(
                "PRODUCT_TV requires a registered allocation/repeats and an "
                "exact product-law computation; not supported here.  The "
                "action-level L1/TV separation is never relabelled as product TV.",
            ),
        )


    # Enumeration results (exact, DISCRETE_CATALOG engine).
    # P0-2 repair: the DISCRETE_CATALOG path certifies purely from exact
    # enumeration and NEVER calls the convex-hull LP.  The convex LP solves
    # a different problem (optimising over the convex hulls); invoking it on
    # the discrete path wrongly rejected valid discrete certificates as
    # COUNTEREXAMPLE whenever the hulls overlapped.  enumeration_matches_lp
    # remains only a cross-object diagnostic and is not a discrete gate.
    enum_collision = collision_witness(model, panel)
    from .witness import panel_separation

    sep = panel_separation(model, panel)
    enum_gamma = sep.gamma

    cert = T2bCertificate(panel=tuple(panel), enumeration_gamma=enum_gamma, spec=spec)
    if enum_collision is not None:
        return _with_tv(
            replace(cert, collision_witness=enum_collision, gamma=Fraction(0), status="IFF")
        )
    if enum_gamma is None:
        return _with_tv(
            replace(
                cert,
                collapsed=True,
                status="IFF",
                gamma=None,
                notes=("D empty: vacuous separation.",),
            )
        )
    return _with_tv(
        replace(
            cert,
            separation_witness=sep.witness_v,
            gamma=enum_gamma,
            status="IFF",
        )
    )


