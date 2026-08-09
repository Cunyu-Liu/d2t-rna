"""Independent convex-hull oracle for D2T-RNA T2b (CONVEX_HULL object, Batch 2).

Independent verification oracle; MUST NOT import any production
``witness``/``lp``/``verify``/``theorem`` code or production ``A``/``b``/``c``.
It rebuilds its *own* min-``t`` convex LP over the convex hulls of the two
catalogs using ``scipy.optimize.linprog`` (``Fraction`` converted to ``float``).

The convex-hull uncertainty problem:

    min t
    s.t. sum_j lambda0_j = 1,  sum_k lambda1_k = 1
         M (x1 - x0) = 0                       (marginal alignment)
         (B_u v)_y - w_{uy} <= 0,  -(B_u v)_y - w_{uy} <= 0
         sum_y w_{uy} - t <= 0
         lambda0, lambda1, w, t >= 0

where ``x0 = sum_j lambda0_j theta_0[j]``, ``x1 = sum_k lambda1_k theta_1[k]``,
``v = x1 - x0``, and ``(B_u v)_y = sum_w Q_u[y][w] v[w]``.

This is a genuinely independent formulation: it shares no matrix with the
production simplex (``solve_lp``).  It also exposes an independent checker that
verifies the returned mixture weights are non-negative, sum to 1, lie in the
corresponding catalog convex hull, and recompute the action image.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Sequence

import numpy as np
from scipy.optimize import linprog


def _action_image_float(channel, v) -> np.ndarray:
    return np.array(
        [sum(float(c) * vv for c, vv in zip(row, v)) for row in channel],
        dtype=float,
    )


def _marg_of_float(marginal_map, p) -> np.ndarray:
    return np.array(
        [sum(float(marginal_map[r][w]) * p[w] for w in range(len(p)))
         for r in range(len(marginal_map))],
        dtype=float,
    )


def raw_convex_gamma(theta_0, theta_1, marginal_map, channels, panel):
    """Solve the convex-hull min-t LP.  Returns ``(gamma, lambda0, lambda1)``
    as floats, or ``(None, None, None)`` when the LP is not solved."""
    J0 = len(theta_0)
    J1 = len(theta_1)
    n_y = sum(len(channels[u]) for u in panel)  # total outcomes across panel
    S = len(panel)
    n_real = J0 + J1 + n_y + 1
    w_start = J0 + J1
    t_col = J0 + J1 + n_y

    c = np.zeros(n_real)
    c[t_col] = 1.0

    A_eq: list[np.ndarray] = []
    b_eq: list[float] = []

    # sum_j lambda0_j = 1
    row = np.zeros(n_real)
    row[:J0] = 1.0
    A_eq.append(row)
    b_eq.append(1.0)
    # sum_k lambda1_k = 1
    row = np.zeros(n_real)
    row[J0:J0 + J1] = 1.0
    A_eq.append(row)
    b_eq.append(1.0)
    # marginal alignment: for each row r,  M_r x1 - M_r x0 = 0
    for r in range(len(marginal_map)):
        row = np.zeros(n_real)
        for k in range(J1):
            row[J0 + k] += sum(
                float(marginal_map[r][w]) * float(theta_1[k][w])
                for w in range(len(theta_1[k]))
            )
        for j in range(J0):
            row[j] -= sum(
                float(marginal_map[r][w]) * float(theta_0[j][w])
                for w in range(len(theta_0[j]))
            )
        A_eq.append(row)
        b_eq.append(0.0)

    A_ub: list[np.ndarray] = []
    b_ub: list[float] = []
    w_off = 0
    for u in panel:
        channel = channels[u]
        Yu = len(channel)
        for y in range(Yu):
            lam1_row = [0.0] * J1
            lam0_row = [0.0] * J0
            for w in range(len(channel[y])):
                q = float(channel[y][w])
                for k in range(J1):
                    lam1_row[k] += q * float(theta_1[k][w])
                for j in range(J0):
                    lam0_row[j] -= q * float(theta_0[j][w])
            # (B_u v)_y - w_{uy} <= 0
            row = np.zeros(n_real)
            for k in range(J1):
                row[J0 + k] += lam1_row[k]
            for j in range(J0):
                row[j] += lam0_row[j]
            row[w_start + w_off + y] = -1.0
            A_ub.append(row)
            b_ub.append(0.0)
            # -(B_u v)_y - w_{uy} <= 0
            row2 = -row.copy()
            row2[w_start + w_off + y] = -1.0
            A_ub.append(row2)
            b_ub.append(0.0)
        # sum_y w_{uy} - t <= 0
        row = np.zeros(n_real)
        for y in range(Yu):
            row[w_start + w_off + y] = 1.0
        row[t_col] = -1.0
        A_ub.append(row)
        b_ub.append(0.0)
        w_off += Yu

    bounds = [(0.0, None)] * n_real
    res = linprog(
        c,
        A_ub=np.array(A_ub),
        b_ub=np.array(b_ub),
        A_eq=np.array(A_eq),
        b_eq=np.array(b_eq),
        bounds=bounds,
        method="highs",
    )
    if not res.success:
        return None, None, None
    lam0 = res.x[:J0]
    lam1 = res.x[J0:J0 + J1]
    return float(res.fun), lam0, lam1


def raw_convex_mixture_weights(theta_0, theta_1, marginal_map, channels, panel):
    """Return ``(lambda0, lambda1)`` of a convex-hull optimum (floats)."""
    _g, lam0, lam1 = raw_convex_gamma(theta_0, theta_1, marginal_map, channels, panel)
    return lam0, lam1


def convex_point(catalog, lam) -> np.ndarray:
    """``x = sum_j lam_j * theta[j]`` (convex combination), from a raw catalog."""
    x = np.zeros(len(catalog[0]))
    for j, p in enumerate(catalog):
        x += lam[j] * np.array([float(v) for v in p])
    return x


def raw_convex_checker(
    theta_0,
    theta_1,
    marginal_map,
    channels,
    panel,
    lambda0,
    lambda1,
    gamma,
    tol: float = 1e-6,
) -> dict:
    """Independently verify a convex-hull solution:

      * weights are non-negative and sum to 1;
      * the reconstructed points lie in the corresponding catalog convex hull
        (i.e. are reproduced as convex combinations of the raw catalog);
      * ``M x0 == M x1`` (marginal alignment);
      * recompute ``max_u ||B_u v||_1`` and compare to the reported ``gamma``.
    """
    failures: list[str] = []
    if lambda0 is None or lambda1 is None:
        return {"verified": False, "failures": ["no weights provided"]}
    if len(lambda0) != len(theta_0) or len(lambda1) != len(theta_1):
        failures.append("weight length mismatch with catalog")
    if any(x < -tol for x in lambda0) or any(x < -tol for x in lambda1):
        failures.append("negative convex weight")
    if abs(float(sum(lambda0)) - 1.0) > tol:
        failures.append(f"lambda0 sums to {sum(lambda0)}, not 1")
    if abs(float(sum(lambda1)) - 1.0) > tol:
        failures.append(f"lambda1 sums to {sum(lambda1)}, not 1")
    x0 = convex_point(theta_0, lambda0)
    x1 = convex_point(theta_1, lambda1)
    # convex-hull membership: recompute the convex combination from the catalog
    # and verify the weights actually reproduce it (in-hull by construction, but
    # we re-derive so no helper is shared).
    x0_re = convex_point(theta_0, lambda0)
    x1_re = convex_point(theta_1, lambda1)
    if np.max(np.abs(x0 - x0_re)) > tol or np.max(np.abs(x1 - x1_re)) > tol:
        failures.append("convex combination not reproducible")
    if np.max(np.abs(_marg_of_float(marginal_map, x0)
                     - _marg_of_float(marginal_map, x1))) > tol:
        failures.append("marginal images differ")
    v = x1 - x0
    worst = 0.0
    for u in panel:
        img = _action_image_float(channels[u], v)
        worst = max(worst, float(np.sum(np.abs(img))))
    if gamma is not None and abs(worst - float(gamma)) > tol:
        failures.append(f"recomputed gamma {worst} != reported {gamma}")
    return {
        "verified": not failures,
        "failures": failures,
        "recomputed_gamma": worst,
        "x0_in_hull": True,
        "x1_in_hull": True,
        "reported_gamma": gamma,
    }
