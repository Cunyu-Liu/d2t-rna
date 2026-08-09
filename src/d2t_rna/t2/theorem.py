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

This module builds the separation ``gamma(S)`` as an exact rational LP,
solves it (primal and dual), extracts the witness, and cross-checks the LP
value against the exhaustive enumeration engine.  Floating-point status or
caller hashes are never treated as proof.

**P0-3 fail-closed gate.**  The enumerated (discrete-catalog) engine and the
LP (convex-hull) engine solve two *different* problems.  When they disagree
(``enumeration_matches_lp == False``) the certifier must NOT emit a formal
``IFF`` collision-or-separation certificate: it returns status
``COUNTEREXAMPLE`` with ``gamma=None`` and preserves both values for evidence.
The raw separation is reported as action-level L1 (``gamma``) and, when the
declared ``TheoremSpec`` measure is a TV, as ``gamma_tv = gamma / 2 in [0,1]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Sequence

from .lp import LpResult, solve_lp
from .model import Action, T2FiniteModel, marginal_apply
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
    (gamma > 0), the exact LP primal/dual certificates, and the enumeration
    cross-check.

    **P0-3 gate.**  When the discrete enumeration and the convex-hull LP
    disagree, no formal certificate is issued: ``status`` is
    ``COUNTEREXAMPLE``, ``gamma`` is ``None``, and both values are preserved.
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
    enum_collision = collision_witness(model, panel)
    from .witness import panel_separation

    sep = panel_separation(model, panel)
    enum_gamma = sep.gamma

    # D empty -> vacuous separation (no admissible cross-class difference).
    # This is a certified IFF with gamma=None and never a collision certificate.
    if enum_gamma is None:
        return T2bCertificate(
            panel=tuple(panel),
            enumeration_gamma=None,
            collapsed=True,
            status="IFF",
            gamma=None,
            spec=spec,
            notes=("D empty: vacuous separation.",),
        )

    # LP solves gamma(S) over the CONVEX_HULL engine.
    n_real, c, A, b, layout = build_gamma_lp(model, panel)
    res: LpResult = solve_lp(c, A, b)

    cert = T2bCertificate(panel=tuple(panel), enumeration_gamma=enum_gamma, spec=spec)
    if res.status != "OPTIMAL":
        cert = replace(
            cert,
            notes=(f"LP status {res.status!r}; falling back to enumeration.",),
        )
        return _with_tv(_certify_from_enumeration(cert, model, panel, enum_collision, enum_gamma))

    lp_opt = res.objective
    cert = replace(cert, lp_optimal=lp_opt)
    matches = enum_gamma is not None and lp_opt == enum_gamma
    cert = replace(cert, enumeration_matches_lp=matches)

    # P0-3 fail-closed: the two engines disagree -> no formal certificate.
    if enum_gamma is not None and not matches:
        return replace(
            cert,
            status="COUNTEREXAMPLE",
            gamma=None,
            notes=cert.notes + (
                "enumeration_gamma != lp_optimal: discrete catalog and convex "
                "relaxation disagree; the certificate is not well-posed and no "
                "formal collision-or-separation certificate is issued.",
            ),
        )

    # Recover the witness from the LP primal (x_1 - x_0).
    J0, J1 = layout["J0"], layout["J1"]
    n_states = model.n_states
    x0 = [Fraction(0) for _ in range(n_states)]
    x1 = [Fraction(0) for _ in range(n_states)]
    for j in range(J0):
        lam = res.primal[j]
        for w in range(n_states):
            x0[w] += lam * model.theta_0[j][w]
    for k in range(J1):
        lam = res.primal[J0 + k]
        for w in range(n_states):
            x1[w] += lam * model.theta_1[k][w]
    v = tuple(x1[w] - x0[w] for w in range(n_states))

    # Marginal collision check on the LP witness.
    m0 = marginal_apply(model, x0)
    m1 = marginal_apply(model, x1)
    cert = replace(cert, lp_primal_feasible=(res.status == "OPTIMAL" and m0 == m1))

    # Strong duality: dual objective should equal primal optimum.
    # dual[i] is the shadow price for row i; b^T dual == c^T x at optimum.
    dual_obj = sum((b[i] * res.dual[i] for i in range(len(b))), Fraction(0))
    strong = res.dual_available and dual_obj == lp_opt and lp_opt >= 0
    cert = replace(
        cert,
        lp_dual_feasible=res.dual_available,
        lp_strong_duality=strong,
    )

    if lp_opt == 0:
        # Collision branch: witness must be nonzero and blind to the panel.
        if any(x != 0 for x in v):
            cert = replace(
                cert, collision_witness=v, gamma=Fraction(0), status="IFF"
            )
        elif enum_collision is not None:
            cert = replace(
                cert,
                collision_witness=enum_collision,
                gamma=Fraction(0),
                status="IFF",
                lp_strong_duality=strong,
            )
        else:
            cert = replace(
                cert,
                status="NECESSARY_ONLY",
                notes=cert.notes
                + ("LP optimum 0 but no nonzero witness recovered; infimum-only.",),
            )
    else:
        # Separation branch.
        cert = replace(
            cert,
            separation_witness=v,
            gamma=lp_opt,
            status="IFF",
            lp_strong_duality=strong and lp_opt > 0,
        )

    return _with_tv(cert)


def _certify_from_enumeration(
    cert: T2bCertificate,
    model: T2FiniteModel,
    panel: Sequence[str],
    enum_collision,
    enum_gamma,
) -> T2bCertificate:
    """Fallback certificate built purely from the exact enumeration engine.

    This certifies the ``DISCRETE_CATALOG`` problem only; it never claims
    agreement with the convex-hull LP (``enumeration_matches_lp`` stays
    ``False`` here).
    """
    cert = replace(cert, enumeration_gamma=enum_gamma)
    if enum_collision is not None:
        return replace(
            cert,
            collision_witness=enum_collision,
            gamma=Fraction(0),
            status="IFF",
            enumeration_matches_lp=False,
        )
    if enum_gamma is None:
        return replace(
            cert,
            collapsed=True,
            status="IFF",
            gamma=None,
            notes=cert.notes + ("D empty: vacuous separation.",),
        )
    return replace(
        cert,
        separation_witness=enum_collision,
        gamma=enum_gamma,
        status="IFF",
        enumeration_matches_lp=False,
    )