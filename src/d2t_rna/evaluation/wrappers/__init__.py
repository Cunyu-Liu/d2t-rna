"""d2t_rna.evaluation.wrappers -- faithful external-method wrappers (P0-9).

A wrapper re-implements an external comparator method faithfully on the D2T
task.  A wrapper is headline-eligible only when its original-paper toy case is
reproduced (toy parity) before the D2T task is run; wrappers without a verified
published toy value are marked ``UNKNOWN_FULL_TEXT_OR_REDUCTION_MISSING`` and
are NOT headline-eligible.

See ``toy_parity_runner.run_all_toy_parity`` for the parity report.
"""

from .base import (
    UNKNOWN,
    FaithfulWrapper,
    ToyParityResult,
    greedy_allocate,
)
from .toy_parity_runner import (
    registered_wrappers,
    run_all_toy_parity,
    write_toy_parity_report,
)

__all__ = [
    "UNKNOWN",
    "FaithfulWrapper",
    "ToyParityResult",
    "greedy_allocate",
    "registered_wrappers",
    "run_all_toy_parity",
    "write_toy_parity_report",
]
