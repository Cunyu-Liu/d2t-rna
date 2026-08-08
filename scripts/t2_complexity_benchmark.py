"""Phase 3 complexity benchmark for the corrected T2 semantic kernel.

Phase 3 (``D2T-RNA_v7_严格科研与工程审计_2026-08-07.md``) requires a *complexity
benchmark* artifact that records how the corrected semantic kernel scales:
per-instance wall time, peak resident memory, the discrete-enumeration vs
convex-LP objective gap, and solver status over a pre-registered small scale
grid.  It does **not** claim SOTA: it is an engineering scaling record on
synthetic finite models (model-conditional only).

The grid varies:

* number of latent states ``n_states``;
* catalog cardinality ``|Theta_0| x |Theta_1|``;
* panel size ``|S|`` (number of actions).

For each instance we record:

* ``collision_or_separation`` wall time (s) and the resulting certificate;
* peak resident set delta during the solve (``resource.ru_maxrss``);
* ``enumeration_gamma`` vs ``lp_optimal`` and the ``enumeration_matches_lp``
  flag (the P0-3 / Phase-3 fail-closed agreement gate);
* certificate ``status`` and ``gamma`` (plus TV range check).

Output is written as a canonical JSON manifest (with ``canonical_json_bytes``)
to the artifact root so it can be hash-bound.  This script is deliberately
small / deterministic and completes in well under a minute on the target
CPython 3.11 environment.
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from fractions import Fraction
from pathlib import Path

from d2t_rna.t2.model import Action, T2FiniteModel
from d2t_rna.t2.spec import tv_from_l1
from d2t_rna.t2.theorem import collision_or_separation


def _simp_2d(den: int) -> list[tuple[Fraction, Fraction]]:
    """All 2-state distributions with a common denominator ``den``."""
    out: list[tuple[Fraction, Fraction]] = []
    for a in range(den + 1):
        out.append((Fraction(a, den), Fraction(den - a, den)))
    return out


def _simp_3d(den: int) -> list[tuple[Fraction, Fraction, Fraction]]:
    """All 3-state distributions with a common denominator ``den``."""
    out: list[tuple[Fraction, Fraction, Fraction]] = []
    for a in range(den + 1):
        for b in range(den - a + 1):
            out.append((Fraction(a, den), Fraction(b, den), Fraction(den - a - b, den)))
    return out


def _identity_channel(n: int) -> tuple[tuple[Fraction, ...], ...]:
    return tuple(tuple(Fraction(1 if y == w else 0) for w in range(n)) for y in range(n))


def _merge_channel(n: int) -> tuple[tuple[Fraction, ...], ...]:
    """Merge all latent states into a single outcome (degenerate / collapsing)."""
    return ((Fraction(1),) * n,)


def _pair_channel(n: int) -> tuple[tuple[Fraction, ...], ...]:
    """Merge states in adjacent pairs (each outcome sums over two latent states)."""
    rows = []
    w = 0
    while w < n:
        row = [Fraction(0)] * n
        row[w] = Fraction(1)
        if w + 1 < n:
            row[w + 1] = Fraction(1)
        rows.append(tuple(row))
        w += 2
    return tuple(rows)


def _models() -> list[tuple[str, T2FiniteModel, tuple[str, ...]]]:
    """Deterministic pre-registered small scale grid (name, model, panel)."""
    grid: list[tuple[str, T2FiniteModel, tuple[str, ...]]] = []

    # 2-state, single identity action, growing catalogs.
    for j0 in (1, 2, 3):
        for j1 in (1, 2, 3):
            d2 = _simp_2d(3)
            model = T2FiniteModel(
                name=f"s2_c{j0}x{j1}_id",
                n_states=2,
                theta_0=tuple(d2[:j0]),
                theta_1=tuple(d2[3:3 + j1]),
                marginal_map=((Fraction(1), Fraction(1)),),
                actions=(Action(action_id="id", channel=_identity_channel(2)),),
            )
            grid.append((f"s2_c{j0}x{j1}_id", model, ("id",)))

    # 3-state, growing catalogs, identity + pair panel.
    for j0 in (1, 2, 3):
        for j1 in (1, 2, 3):
            d3 = _simp_3d(2)
            model = T2FiniteModel(
                name=f"s3_c{j0}x{j1}",
                n_states=3,
                theta_0=tuple(d3[:j0]),
                theta_1=tuple(d3[3:3 + j1]),
                marginal_map=((Fraction(1), Fraction(1), Fraction(1)),),
                actions=(
                    Action(action_id="id", channel=_identity_channel(3)),
                    Action(action_id="pair", channel=_pair_channel(3)),
                ),
            )
            # single-action panel and two-action panel
            grid.append((f"s3_c{j0}x{j1}_p1", model, ("id",)))
            grid.append((f"s3_c{j0}x{j1}_p2", model, ("id", "pair")))

    # A small collapsing-channel sanity row (degenerate -> full difference set).
    d2 = _simp_2d(4)
    model = T2FiniteModel(
        name="s2_c2x2_merge",
        n_states=2,
        theta_0=tuple(d2[:2]),
        theta_1=tuple(d2[2:4]),
        marginal_map=((Fraction(1), Fraction(1)),),
        actions=(Action(action_id="merge", channel=_merge_channel(2)),),
    )
    grid.append(("s2_c2x2_merge", model, ("merge",)))
    return grid


def _peak_rss_kb() -> int:
    """Current peak resident set size in KiB (Linux ``ru_maxrss`` is KiB)."""
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def run_one(name: str, model: T2FiniteModel, panel: tuple[str, ...]) -> dict:
    base_rss = _peak_rss_kb()
    t0 = time.perf_counter()
    cert = collision_or_separation(model, list(panel))
    elapsed = time.perf_counter() - t0
    peak = _peak_rss_kb() - base_rss
    tv = tv_from_l1(cert.gamma) if cert.gamma is not None else None
    row = {
        "name": name,
        "n_states": model.n_states,
        "catalog": f"{len(model.theta_0)}x{len(model.theta_1)}",
        "panel": list(panel),
        "status": cert.status,
        "gamma": str(cert.gamma) if cert.gamma is not None else None,
        "gamma_tv": str(tv) if tv is not None else None,
        "enumeration_gamma": (
            str(cert.enumeration_gamma) if cert.enumeration_gamma is not None else None
        ),
        "lp_optimal": str(cert.lp_optimal) if cert.lp_optimal is not None else None,
        "enumeration_matches_lp": bool(cert.enumeration_matches_lp),
        "tv_in_unit_interval": bool(tv is not None and 0 <= tv <= 1),
        "elapsed_s": round(elapsed, 6),
        "peak_rss_delta_kb": peak,
    }
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        default="/mnt/cunyuliu/d2t-rna/artifacts/phase3/complexity_benchmark.json",
    )
    args = ap.parse_args(argv)

    rows = [run_one(name, model, panel) for name, model, panel in _models()]

    # Summary statistics over the grid.
    statuses: dict[str, int] = {}
    agree = 0
    for r in rows:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
        if r["enumeration_matches_lp"]:
            agree += 1
    summary = {
        "instances": len(rows),
        "status_counts": statuses,
        "engines_agree": agree,
        "total_elapsed_s": round(sum(r["elapsed_s"] for r in rows), 6),
        "max_peak_rss_delta_kb": max(r["peak_rss_delta_kb"] for r in rows),
        "tv_range_violations": sum(
            1 for r in rows if r["tv_in_unit_interval"] is False
        ),
        "scale_note": "synthetic model-conditional scaling record; not SOTA",
    }

    payload = {
        "schema": "d2t_rna.v7_phase3_complexity_benchmark.v1",
        "python": sys.version.split()[0],
        "rows": rows,
        "summary": summary,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # canonical JSON (sorted keys, compact separators) for stable hashing
    out.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
