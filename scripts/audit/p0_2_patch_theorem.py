"""P0-2 patch: make collision_or_separation DISCRETE_CATALOG path purely discrete.

The discrete path previously ran the convex-hull LP unconditionally and rejected
valid discrete certificates as COUNTEREXAMPLE when the convex hull overlapped.
Now DISCRETE_CATALOG certifies directly from exact enumeration and never calls
build_gamma_lp (which remains available only for explicit convex/diagnostic use).
enumeration_matches_lp is left as a cross-object diagnostic (False on discrete-only),
never a discrete certificate gate.
"""
from pathlib import Path

P = Path("/home/cunyuliu/d2t-rna/src/d2t_rna/t2/theorem.py")
src = P.read_text()

start_marker = "    # Enumeration results (exact, DISCRETE_CATALOG engine).\n"
end_marker = "    return _with_tv(cert)\n"

i_start = src.index(start_marker)
# find the LAST occurrence of the standalone return _with_tv(cert) after i_start
tail = src[i_start:]
last_pos = tail.rindex(end_marker)
i_end = i_start + last_pos + len(end_marker)

new_block = (
    "    # Enumeration results (exact, DISCRETE_CATALOG engine).\n"
    "    # P0-2 repair: the DISCRETE_CATALOG path certifies purely from exact\n"
    "    # enumeration and NEVER calls the convex-hull LP.  The convex LP solves\n"
    "    # a different problem (optimising over the convex hulls); invoking it on\n"
    "    # the discrete path wrongly rejected valid discrete certificates as\n"
    "    # COUNTEREXAMPLE whenever the hulls overlapped.  enumeration_matches_lp\n"
    "    # remains only a cross-object diagnostic and is not a discrete gate.\n"
    "    enum_collision = collision_witness(model, panel)\n"
    "    from .witness import panel_separation\n"
    "\n"
    "    sep = panel_separation(model, panel)\n"
    "    enum_gamma = sep.gamma\n"
    "\n"
    "    cert = T2bCertificate(panel=tuple(panel), enumeration_gamma=enum_gamma, spec=spec)\n"
    "    return _with_tv(\n"
    "        _certify_from_enumeration(cert, model, panel, enum_collision, enum_gamma)\n"
    "    )\n"
)

new_src = src[:i_start] + new_block + src[i_end:]
P.write_text(new_src)
print("PATCHED theorem.py")
print("old_len", len(src), "new_len", len(new_src))
