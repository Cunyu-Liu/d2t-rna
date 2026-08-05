"""RNA secondary-structure state space and marginal scaffold (T2e candidate).

This module is a *research scaffold*, not a claimed theorem.  Its purpose is to
give the contract's T2e candidate (RNA-feasible scoped alternating-cycle lemma)
an exact, checkable substrate so the conjecture can be *tested* on small
sequence lengths before any formal novelty claim is made.

State space: the set of valid RNA secondary structures on ``L`` positions ---
noncrossing base pairs with no base-pair crossings (pseudoknot-free).  A
structure is a set of base pairs ``(i,j)`` with ``i < j`` such that no two pairs
cross, i.e. there are no ``(i,j),(k,l)`` with ``i<k<j<l``.

Marginal maps we study:
  * ``paired_profile``  length-``L`` binary vector: 1 at a position iff it is
    base-paired.
  * ``base_pair_count`` scalar: total number of base pairs.

Given a marginal value ``m``, the *fiber* ``F(m)`` is the set of valid
structures with that marginal.  The candidate structural lemma asks whether
``F(m)`` is connected under the *local alternating swap* moves (replace two
base pairs ``(a,b),(c,d)`` with ``(a,c),(b,d)`` or ``(a,d),(b,c)`` whenever the
result is still a valid noncrossing structure covering the same paired
positions), and whether the fiber diameter is polynomial in ``L``.

Until the lemma is actually proven on the exact enumeration below (and the
enumerated evidence is consistent for all small ``L``), the status is
``NOT_ESTABLISHED``.  No novelty claim is made here.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from typing import Iterator, Sequence

NOT_ESTABLISHED = "NOT_ESTABLISHED"


# --------------------------------------------------------------------------
# RNA secondary structure state space
# --------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _all_structures(L: int) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Exhaustively enumerate all valid noncrossing base-pair structures on L.

    Standard Motzkin recursion: position 0 is either unpaired (recurse on the
    tail) or paired with some ``j`` (recurse inside ``(1..j-1)`` and outside
    ``(j+1..L-1)``).  Returns a tuple of structures, each a sorted tuple of
    base pairs ``(i, j)``.
    """
    if L < 2:
        return ((),)
    out: set[tuple[tuple[int, int], ...]] = set()
    # --- position 0 unpaired: substructure on positions 1..L-1 (shifted +1)
    for tail in _all_structures(L - 1):
        shifted = tuple((a + 1, b + 1) for a, b in tail)
        out.add(tuple(shifted))
    # --- position 0 paired with j (0 < j < L)
    for j in range(1, L):
        inner = _all_structures(j - 1)      # positions 1..j-1
        outer = _all_structures(L - j - 1)  # positions j+1..L-1
        for ins in inner:
            shifted_ins = tuple((a + 1, b + 1) for a, b in ins)
            for outs in outer:
                shifted_outs = tuple((a + j + 1, b + j + 1) for a, b in outs)
                out.add(tuple(sorted(((0, j),) + shifted_ins + shifted_outs)))
    return tuple(sorted(out))


def structures(L: int) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Return all valid secondary structures on ``L`` positions."""
    return _all_structures(L)


def is_valid_structure(pairs: Sequence[tuple[int, int]]) -> bool:
    """Check that ``pairs`` is a valid noncrossing structure (no crossing)."""
    ps = sorted((min(a, b), max(a, b)) for a, b in pairs)
    for i in range(len(ps)):
        if ps[i][0] == ps[i][1]:
            return False
        for j in range(i + 1, len(ps)):
            a, b = ps[i]
            c, d = ps[j]
            if a < c < b < d:
                return False
    return True


def paired_profile(pairs: Sequence[tuple[int, int]], L: int) -> tuple[int, ...]:
    """Length-``L`` binary vector: 1 iff position is base-paired."""
    prof = [0] * L
    for a, b in pairs:
        prof[a] = 1
        prof[b] = 1
    return tuple(prof)


def base_pair_count(pairs: Sequence[tuple[int, int]]) -> int:
    """Number of base pairs in a structure."""
    return len(pairs)


# --------------------------------------------------------------------------
# Fiber computation
# --------------------------------------------------------------------------

def fiber_by_profile(L: int, target: tuple[int, ...]) -> tuple[tuple[tuple[int, int], ...], ...]:
    """All structures on ``L`` with the given ``paired_profile``."""
    return tuple(
        s for s in structures(L) if paired_profile(s, L) == target
    )


def fiber_by_pair_count(L: int, count: int) -> tuple[tuple[tuple[int, int], ...], ...]:
    """All structures on ``L`` with exactly ``count`` base pairs."""
    return tuple(s for s in structures(L) if base_pair_count(s) == count)


# --------------------------------------------------------------------------
# Local alternating swap moves
# --------------------------------------------------------------------------

def _swap2(s: tuple[tuple[int, int], ...], i: int, j: int) -> tuple[tuple[int, int], ...] | None:
    """Swap the endpoints of base pairs ``i`` and ``j``.

    Given pairs ``(a,b)=s[i]``, ``(c,d)=s[j]`` with ``a<b``, ``c<d``, the two
    candidate re-pairings that keep the same four positions paired are
    ``(a,c),(b,d)`` and ``(a,d),(b,c)``.  Return the one that is a valid
    noncrossing structure, or ``None`` if neither is valid.
    """
    rest = [p for k, p in enumerate(s) if k not in (i, j)]
    a, b = s[i]
    c, d = s[j]
    cands = [
        tuple([(a, c), (b, d)] if a < c else [(c, a), (b, d)]),
        tuple([(a, d), (b, c)] if a < d else [(d, a), (b, c)]),
    ]
    for cand in cands:
        full = tuple(sorted(rest + list(cand)))
        if is_valid_structure(full):
            return full
    return None


def swap_neighbors(s: tuple[tuple[int, int], ...]) -> tuple[tuple[tuple[int, int], ...], ...]:
    """All distinct structures reachable by one local alternating swap."""
    out: set[tuple[tuple[int, int], ...]] = set()
    n = len(s)
    for i in range(n):
        for j in range(i + 1, n):
            r = _swap2(s, i, j)
            if r is not None:
                out.add(r)
    return tuple(sorted(out))


def fiber_adjacency(
    L: int, target: tuple[int, ...]
) -> tuple[tuple[tuple[tuple[int, int], ...], ...], list[tuple[int, int]]]:
    """Adjacency (swap moves) restricted to the fiber ``F(target)``.

    Returns ``(fiber, edges)`` where ``edges`` index into ``fiber`` across the
    local swap moves.  Only swaps that stay inside the fiber are retained.
    """
    fb = fiber_by_profile(L, target)
    idx = {s: i for i, s in enumerate(fb)}
    edges: list[tuple[int, int]] = []
    for i, s in enumerate(fb):
        for t in swap_neighbors(s):
            if t in idx and idx[t] > i:
                edges.append((i, idx[t]))
    return fb, edges


def fiber_connected_and_diameter(
    L: int, target: tuple[int, ...]
) -> tuple[bool, int | None, int]:
    """BFS over the swap-move graph on ``F(target)``.

    Returns ``(connected, diameter, fiber_size)``.  ``diameter`` is ``None``
    when the fiber has ``< 2`` structures.
    """
    fb, edges = fiber_adjacency(L, target)
    n = len(fb)
    if n < 2:
        return True, None, n
    adj: list[list[int]] = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    # BFS from every node to find the diameter.
    diam = 0
    for start in range(n):
        dist = [-1] * n
        from collections import deque

        dq = deque([start])
        dist[start] = 0
        while dq:
            u = dq.popleft()
            for v in adj[u]:
                if dist[v] < 0:
                    dist[v] = dist[u] + 1
                    dq.append(v)
        if any(d < 0 for d in dist):
            return False, None, n
        diam = max(diam, max(dist))
    return True, diam, n


@dataclass(frozen=True)
class RnaFiberEvidence:
    """Empirical evidence about one marginal fiber (NOT a theorem)."""

    L: int
    marginal: str
    marginal_value: object
    fiber_size: int
    swap_connected: bool
    fiber_diameter: int | None
    status: str = NOT_ESTABLISHED

    def as_dict(self) -> dict:
        return {
            "L": self.L,
            "marginal": self.marginal,
            "marginal_value": self.marginal_value,
            "fiber_size": self.fiber_size,
            "swap_connected": self.swap_connected,
            "fiber_diameter": self.fiber_diameter,
            "status": self.status,
        }


def scan_profile_fibers(L: int) -> tuple[RnaFiberEvidence, ...]:
    """Scan all nonempty ``paired_profile`` fibers on ``L`` positions."""
    seen: set[tuple[int, ...]] = set()
    out: list[RnaFiberEvidence] = []
    for s in structures(L):
        prof = paired_profile(s, L)
        if prof in seen:
            continue
        seen.add(prof)
        conn, diam, size = fiber_connected_and_diameter(L, prof)
        out.append(
            RnaFiberEvidence(
                L=L,
                marginal="paired_profile",
                marginal_value=list(prof),
                fiber_size=size,
                swap_connected=conn,
                fiber_diameter=diam,
            )
        )
    return tuple(out)