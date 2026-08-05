"""Exact rational linear-programming solver for T2-2 primal/dual certificates.

This module solves LPs in the standard form

    minimize   c^T x
    subject to A x = b,  x >= 0

using a two-phase simplex tableau with ``fractions.Fraction`` arithmetic and
Bland's anti-cycling rule.  It returns the exact optimal value, an optimal
primal solution, and an optimal dual solution (when the primal is bounded and
feasible).  Floating-point solver status, tolerances, or caller-supplied
hashes are never treated as proof (contract section 5.2 / 10.3): everything
here is exact rational arithmetic.

This solver is deliberately self-contained; it does not import any helper
from :mod:`d2t_rna.t2.witness` or :mod:`d2t_rna.t2.model`, so the T2-2
certificates can be re-derived independently of the enumeration engine.
"""

from __future__ import annotations

from fractions import Fraction
from typing import NamedTuple, Sequence

Fraction  # noqa: B018  (exact arithmetic)


class LpResult(NamedTuple):
    """Outcome of an exact rational LP solve.

    ``status`` is one of ``"OPTIMAL"``, ``"INFEASIBLE"``, ``"UNBOUNDED"``, or
    ``"FAILED"``.  ``objective`` and ``primal`` are set only when ``OPTIMAL``.
    ``dual`` holds one dual variable per equality constraint and is set when
    ``OPTIMAL`` and ``dual_available`` is True.
    """

    status: str
    objective: Fraction | None
    primal: tuple[Fraction, ...] | None
    dual: tuple[Fraction, ...] | None
    dual_available: bool


def _stable_ratio(
    tableau: list[list[Fraction]],
    basis: list[int],
    entering: int,
    m: int,
    N: int,
) -> int:
    """Bland-compatible min-ratio test; returns the leaving row or -1."""
    best_row = -1
    best_ratio: Fraction | None = None
    for i in range(m):
        a = tableau[i][entering]
        if a <= 0:
            continue
        rhs = tableau[i][N]
        ratio = rhs / a
        if best_ratio is None or ratio < best_ratio or (
            ratio == best_ratio and basis[i] < basis[best_row]
        ):
            best_ratio = ratio
            best_row = i
    return best_row


def _simplex(
    tableau: list[list[Fraction]],
    basis: list[int],
    m: int,
    N: int,
) -> tuple[str, int | None]:
    """Dantzig pivot loop with Bland's rule.  Returns (status, obj_row).

    ``obj`` lives in row ``m``.  ``status`` is ``"OPTIMAL"``, ``"UNBOUNDED"``,
    or ``"FAILED"`` (used to signal an unbounded phase-1 objective inside the
    two-phase driver, which then reports infeasibility).
    """
    obj = m
    for _ in range(100_000):
        # Bland entering: smallest index with negative reduced cost.
        entering = -1
        for j in range(N):
            if tableau[obj][j] < 0:
                entering = j
                break
        if entering < 0:
            return "OPTIMAL", obj
        leaving = _stable_ratio(tableau, basis, entering, m, N)
        if leaving < 0:
            return "UNBOUNDED", obj
        # Pivot on (leaving, entering).
        piv = tableau[leaving][entering]
        row = tableau[leaving]
        for j in range(N + 1):
            row[j] = row[j] / piv
        for i in range(m + 1):
            if i == leaving:
                continue
            factor = tableau[i][entering]
            if factor == 0:
                continue
            for j in range(N + 1):
                tableau[i][j] = tableau[i][j] - factor * row[j]
        basis[leaving] = entering
    return "FAILED", obj


def _pivot_artificial_out(
    tableau, basis, m, N, basic_artificials, n_real,
) -> None:
    """Exchange any basic artificial variable left at zero for a non-basic
    real column, so the phase-2 basis is all-real.  This is only needed when a
    phase-1 optimum leaves an artificial basic at value zero."""
    # Remove artificial columns from consideration; find a real column to swap in.
    for idx, col in enumerate(basic_artificials):
        row = basis.index(col)
        # find a non-basic real column with nonzero entry in this row
        swapped = False
        for j in range(n_real):
            if j in basis:
                continue
            if tableau[row][j] != 0:
                piv = tableau[row][j]
                for k in range(N + 1):
                    tableau[row][k] = tableau[row][k] / piv
                for i in range(m + 1):
                    if i == row:
                        continue
                    factor = tableau[i][j]
                    if factor == 0:
                        continue
                    for k in range(N + 1):
                        tableau[i][k] = tableau[i][k] - factor * tableau[row][k]
                basis[row] = j
                swapped = True
                break
        if not swapped:
            # zero row: redundant constraint; drop by marking basis with a sentinel.
            basis[row] = -1


def solve_lp(
    c: Sequence[Fraction],
    A: Sequence[Sequence[Fraction]],
    b: Sequence[Fraction],
) -> LpResult:
    """Solve the standard-form LP ``min c^T x s.t. A x = b, x >= 0`` exactly.

    Returns an ``LpResult`` with exact rational objective, primal, and dual.
    ``dual`` is the shadow-price vector (one per equality constraint) and is
    only reported when strong duality was actually recoverable from the final
    tableau.
    """
    m = len(b)
    n = len(c)
    if m == 0:
        # No constraints: min c^T x over x >= 0.
        if all(ci >= 0 for ci in c):
            return LpResult(
                status="OPTIMAL",
                objective=Fraction(0),
                primal=tuple(Fraction(0) for _ in range(n)),
                dual=(),
                dual_available=True,
            )
        return LpResult("UNBOUNDED", None, None, None, False)

    N = n + m  # real + artificial columns
    tableau: list[list[Fraction]] = [
        [Fraction(0) for _ in range(N + 1)] for _ in range(m + 1)
    ]
    for i in range(m):
        for j in range(n):
            tableau[i][j] = A[i][j]
        tableau[i][n + i] = Fraction(1)  # artificial identity
        tableau[i][N] = b[i]

    # Phase 1 objective: minimize sum of artificials.
    phase1_c = [Fraction(0)] * n + [Fraction(1)] * m
    # Reduced costs row: c_j - c_B^T * col_j, with c_B = 1 for basic artificials.
    for j in range(N):
        col_sum = sum(tableau[i][j] for i in range(m))
        tableau[m][j] = phase1_c[j] - col_sum
    tableau[m][N] = -sum(b)

    basis = list(range(n, N))  # artificials are basic initially

    status, obj = _simplex(tableau, basis, m, N)
    phase1_obj = -tableau[obj][N]
    if status == "UNBOUNDED" or phase1_obj > 0:
        return LpResult("INFEASIBLE", None, None, None, False)

    # Drop the artificial columns entirely before phase 2 so they cannot
    # re-enter the basis.  All artificials are non-basic at phase-1 optimum
    # (phase1_obj == 0), except possibly redundant rows left at value zero,
    # which we drop too.
    real_tableau = [
        [row[j] for j in range(n)] + [row[N]] for row in tableau[: m + 1]
    ]
    # rebuild basis: keep only real basic columns, remap to [0,n)
    new_basis: list[int] = []
    keep_rows: list[int] = []
    for i, bcol in enumerate(basis):
        if bcol < n:
            new_basis.append(bcol)
            keep_rows.append(i)
    # If a redundant row forced an artificial out-of-basis remap, we still
    # keep the row (it is consistent); new_basis may be shorter than m.
    tableau = real_tableau
    N2 = n  # only real columns remain
    obj = m

    # Phase 2 objective: original c over real columns.
    m2 = len(new_basis)
    cB = [Fraction(0) for _ in range(m2)]
    for _i, bcol in enumerate(new_basis):
        cB[_i] = c[bcol]
    # zero the objective row
    for j in range(N2 + 1):
        tableau[obj][j] = Fraction(0)
    for _i, (row_idx, bcol) in enumerate(zip(keep_rows, new_basis)):
        # nothing to do per-se; reduced costs computed below
        pass
    # reduced costs: c_j - c_B^T * col_j using the retained rows
    for j in range(N2):
        rc = c[j]
        for _i, row_idx in enumerate(keep_rows):
            rc = rc - cB[_i] * tableau[row_idx][j]
        tableau[obj][j] = rc
    # objective value: c_B^T * x_B
    obj_val = Fraction(0)
    for _i, row_idx in enumerate(keep_rows):
        obj_val = obj_val + cB[_i] * tableau[row_idx][N2]
    tableau[obj][N2] = -obj_val

    # Re-bind the simplex to the reduced basis indices (rows 0..m2-1).
    # We compact the retained rows to the top so the simplex table is square.
    compact_rows = [tableau[row_idx] for row_idx in keep_rows]
    compact_rows.append(tableau[obj])
    tableau = compact_rows
    m2c = m2
    basis2 = list(new_basis)

    status, obj = _simplex(tableau, basis2, m2c, N2)
    if status == "UNBOUNDED":
        return LpResult("UNBOUNDED", None, None, None, False)
    if status == "FAILED":
        return LpResult("FAILED", None, None, None, False)

    objective = -tableau[obj][N2]
    primal = [Fraction(0) for _ in range(n)]
    for i, bcol in enumerate(basis2):
        if 0 <= bcol < n:
            primal[bcol] = tableau[i][N2]

    # Recover dual by solving the basis system: A_B^T y = c_B on the retained
    # (independent) rows, then map back to the full row index space.
    # Dropped (redundant) rows receive dual value 0.
    dual = _dual_from_basis(A, c, basis2, keep_rows, n)
    dual_ok = dual is not None
    if dual is None:
        dual = tuple(Fraction(0) for _ in range(m))
    return LpResult(
        status="OPTIMAL",
        objective=objective,
        primal=tuple(primal),
        dual=tuple(dual),
        dual_available=dual_ok,
    )


def _dual_from_basis(
    A: Sequence[Sequence[Fraction]],
    c: Sequence[Fraction],
    basis: list[int],
    keep_rows: list[int],
    n: int,
):
    """Solve ``A_B^T y = c_B`` for the dual vector ``y`` (one per primal row).

    ``A_B`` is the column sub-matrix of the *retained* constraint rows indexed
    by the optimal basis.  We solve on the independent rows ``keep_rows`` and
    place the solution into the corresponding full-row slots; dropped rows get
    dual 0.  Returns ``None`` if the basis sub-matrix is singular.
    """
    from fractions import Fraction as F

    m = len(A)
    nb = len(basis)
    nr = len(keep_rows)
    if nb != nr or nr == 0:
        return None
    # Retained coefficient rows (independent constraints).
    Arow = [[A[keep_rows[i]][j] for j in range(n)] for i in range(nr)]
    # Build B^T (nr x nr): row k = Arow[:, basis[k]]
    BT = [[Arow[i][basis[k]] for i in range(nr)] for k in range(nr)]
    rhs = [c[basis[k]] for k in range(nr)]
    # Gaussian elimination over rationals to solve BT y = rhs.
    mat = [list(row) + [rhs[k]] for k, row in enumerate(BT)]
    for col in range(nr):
        piv = None
        for r in range(col, nr):
            if mat[r][col] != 0:
                piv = r
                break
        if piv is None:
            return None
        mat[col], mat[piv] = mat[piv], mat[col]
        pv = mat[col][col]
        mat[col] = [x / pv for x in mat[col]]
        for r in range(nr):
            if r != col and mat[r][col] != 0:
                f = mat[r][col]
                mat[r] = [a - f * b for a, b in zip(mat[r], mat[col])]
    y_reduced = [mat[r][nr] for r in range(nr)]
    y = [F(0) for _ in range(m)]
    for i, row_idx in enumerate(keep_rows):
        y[row_idx] = y_reduced[i]
    return tuple(y)