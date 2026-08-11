"""T2CertificateV3: self-contained, verifiable T2b certificate (P0-4).

The production certificate type binds every input identity (model, spec,
catalog, action panel, allocation) and result so that an *independent*
verifier needs only the certificate and the registered raw model to replay the
result.  It deliberately does **not** trust the production solver.

Semantics (contract P0-4):

* V2 (``T2bCertificate``) is only readable through
  :func:`legacy_certificate_reader`, which returns ``LEGACY_UNVERIFIED``.
  New generators must emit V3; V2/V3 never silently alias.
* For the ``DISCRETE_CATALOG`` uncertainty kind the certificate is produced by
  pure exact enumeration (P0-2); there is no convex-hull LP, so
  ``convex_mixture_weights`` stays ``None`` and dual/production-LP receipts are
  not fabricated.
* Non-deterministic metadata (e.g. a timestamp) never enters the canonical
  payload hash.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Sequence

from .model import T2FiniteModel, canonicalize_model
from .spec import (
    MEASURE_ACTION_L1,
    MEASURE_ACTION_TV,
    MEASURE_PRODUCT_TV,
    UNCERTAINTY_CONVEX,
    UNCERTAINTY_DISCRETE,
    TheoremSpec,
    tv_from_l1,
)

SCHEMA_ID = "d2t_rna.t2_certificate.v3"
SCHEMA_VERSION = "3"
VERIFIER_VERSION = "3"

# Keys excluded from the canonical evidentiary payload hash because they are
# non-deterministic metadata or verification-time fields, not generator inputs.
_METADATA_EXCLUDED = frozenset({"timestamp", "verifier_receipt"})


def _hash(*parts: object) -> str:
    return hashlib.sha256(repr(parts).encode("utf-8")).hexdigest()


def _frac_repr(x: Fraction) -> tuple[int, int]:
    return (x.numerator, x.denominator)


def _frac_to_dict(x: Fraction | None):
    return None if x is None else {"numerator": x.numerator, "denominator": x.denominator}


def _frac_from_dict(d) -> Fraction | None:
    return None if d is None else Fraction(d["numerator"], d["denominator"])


def _vec_to_dict(v: Sequence[Fraction] | None):
    return None if v is None else [_frac_to_dict(x) for x in v]


def _vec_from_dict(d) -> tuple[Fraction, ...] | None:
    return None if d is None else tuple(_frac_from_dict(x) for x in d)


def spec_hash(spec: TheoremSpec) -> str:
    return _hash(spec.uncertainty_kind, spec.separation_measure)


def catalog_hash(model: T2FiniteModel) -> str:
    return _hash(
        tuple(_frac_repr(x) for p in model.theta_0 for x in p),
        tuple(_frac_repr(x) for p in model.theta_1 for x in p),
    )


def action_panel_hash(model: T2FiniteModel, panel: Sequence[str]) -> str:
    by_id = {a.action_id: a for a in model.actions}
    rows = []
    for aid in panel:
        a = by_id[aid]
        rows.append((aid, tuple(_frac_repr(x) for row in a.channel for x in row)))
    return _hash(tuple(rows))


def allocation_hash(allocation: Sequence[int] | None) -> str | None:
    return None if allocation is None else _hash(tuple(allocation))


def model_hash(model: T2FiniteModel) -> str:
    _canonical_form, digest = canonicalize_model(model)
    return digest


@dataclass(frozen=True)
class T2CertificateV3:
    """Self-contained, verifiable T2b certificate."""

    schema_id: str = SCHEMA_ID
    schema_version: str = SCHEMA_VERSION
    theorem: str = "T2b"
    status: str = "IFF"
    uncertainty_kind: str = UNCERTAINTY_DISCRETE
    separation_measure: str = MEASURE_ACTION_L1
    gamma_l1: Fraction | None = None
    gamma_tv: Fraction | None = None
    product_tv: Fraction | None = None
    model_hash: str = ""
    spec_hash: str = ""
    catalog_hash: str = ""
    action_panel_hash: str = ""
    allocation_hash: str | None = None
    panel: tuple[str, ...] = ()
    allocation: tuple[int, ...] | None = None
    p0: tuple[Fraction, ...] | None = None
    p1: tuple[Fraction, ...] | None = None
    difference_witness: tuple[Fraction, ...] | None = None
    convex_mixture_weights: dict | None = None
    primal_receipt: str = ""
    dual_receipt: str = ""
    generator_commit: str = ""
    generator_tree: str = ""
    verifier_version: str = VERIFIER_VERSION
    verifier_receipt: str = ""
    collapsed: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.schema_id != SCHEMA_ID:
            raise ValueError(f"schema_id must be {SCHEMA_ID!r}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        try:
            TheoremSpec(self.uncertainty_kind, self.separation_measure)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"invalid spec: {exc}") from exc
        if self.uncertainty_kind == UNCERTAINTY_DISCRETE:
            # discrete certificates never carry fabricated convex weights
            if self.convex_mixture_weights is not None:
                raise ValueError(
                    "DISCRETE certificate must not carry convex mixture weights"
                )
        if self.product_tv is not None and self.allocation is None:
            raise ValueError("product_tv requires an allocation to be registered")

    # -------- serialization -------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "theorem": self.theorem,
            "status": self.status,
            "uncertainty_kind": self.uncertainty_kind,
            "separation_measure": self.separation_measure,
            "gamma_l1": _frac_to_dict(self.gamma_l1),
            "gamma_tv": _frac_to_dict(self.gamma_tv),
            "product_tv": _frac_to_dict(self.product_tv),
            "model_hash": self.model_hash,
            "spec_hash": self.spec_hash,
            "catalog_hash": self.catalog_hash,
            "action_panel_hash": self.action_panel_hash,
            "allocation_hash": self.allocation_hash,
            "panel": list(self.panel),
            "allocation": None if self.allocation is None else list(self.allocation),
            "p0": _vec_to_dict(self.p0),
            "p1": _vec_to_dict(self.p1),
            "difference_witness": _vec_to_dict(self.difference_witness),
            "convex_mixture_weights": self.convex_mixture_weights,
            "primal_receipt": self.primal_receipt,
            "dual_receipt": self.dual_receipt,
            "generator_commit": self.generator_commit,
            "generator_tree": self.generator_tree,
            "verifier_version": self.verifier_version,
            "verifier_receipt": self.verifier_receipt,
            "collapsed": self.collapsed,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "T2CertificateV3":
        return cls(
            schema_id=d.get("schema_id", SCHEMA_ID),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            theorem=d.get("theorem", "T2b"),
            status=d["status"],
            uncertainty_kind=d["uncertainty_kind"],
            separation_measure=d["separation_measure"],
            gamma_l1=_frac_from_dict(d.get("gamma_l1")),
            gamma_tv=_frac_from_dict(d.get("gamma_tv")),
            product_tv=_frac_from_dict(d.get("product_tv")),
            model_hash=d["model_hash"],
            spec_hash=d["spec_hash"],
            catalog_hash=d["catalog_hash"],
            action_panel_hash=d["action_panel_hash"],
            allocation_hash=d.get("allocation_hash"),
            panel=tuple(d.get("panel", [])),
            allocation=None if d.get("allocation") is None else tuple(d["allocation"]),
            p0=_vec_from_dict(d.get("p0")),
            p1=_vec_from_dict(d.get("p1")),
            difference_witness=_vec_from_dict(d.get("difference_witness")),
            convex_mixture_weights=d.get("convex_mixture_weights"),
            primal_receipt=d["primal_receipt"],
            dual_receipt=d["dual_receipt"],
            generator_commit=d.get("generator_commit", ""),
            generator_tree=d.get("generator_tree", ""),
            verifier_version=d.get("verifier_version", VERIFIER_VERSION),
            verifier_receipt=d.get("verifier_receipt", ""),
            collapsed=d.get("collapsed", False),
            notes=tuple(d.get("notes", [])),
        )

    # -------- evidentiary payload & hash -----------------------------------
    def evidentiary_payload(self) -> dict:
        d = self.to_dict()
        return {k: v for k, v in d.items() if k not in _METADATA_EXCLUDED}

    def canonical_payload_hash(self) -> str:
        return hashlib.sha256(
            repr(self.evidentiary_payload()).encode("utf-8")
        ).hexdigest()


def _receipts(cert: T2CertificateV3) -> tuple[str, str]:
    """Recompute primal/dual receipts from the certificate's bound fields.

    The primal receipt binds the constructive data (witness / value / laws /
    allocation); the dual receipt binds the spec / measure semantics.  Because
    they are recomputed from the certificate + registered model, tampering any
    of those fields changes the receipt and is caught by the verifier.
    """
    primal = _hash(
        cert.model_hash,
        cert.gamma_l1,
        cert.status,
        cert.p0,
        cert.p1,
        cert.difference_witness,
        cert.allocation,
    )
    dual = _hash(
        cert.spec_hash,
        cert.separation_measure,
        cert.uncertainty_kind,
        cert.gamma_tv,
        cert.product_tv,
    )
    return primal, dual


def generate_certificate_v3(
    model: T2FiniteModel,
    panel: Sequence[str],
    gamma_l1: Fraction,
    status: str,
    p0: Sequence[Fraction] | None = None,
    p1: Sequence[Fraction] | None = None,
    difference_witness: Sequence[Fraction] | None = None,
    separation_measure: str = MEASURE_ACTION_L1,
    uncertainty_kind: str = UNCERTAINTY_DISCRETE,
    allocation: Sequence[int] | None = None,
    product_tv: Fraction | None = None,
    collapsed: bool = False,
    generator_commit: str = "",
    generator_tree: str = "",
    notes: Sequence[str] = (),
) -> T2CertificateV3:
    """Build a V3 certificate from a raw model and the discrete result.

    Computes and binds ``model_hash``, ``spec_hash``, ``catalog_hash``,
    ``action_panel_hash`` and ``allocation_hash``, plus the gamma_tv /
    product_tv semantics and the primal/dual receipts.
    """
    spec = TheoremSpec(uncertainty_kind, separation_measure)
    m_hash = model_hash(model)
    s_hash = spec_hash(spec)
    c_hash = catalog_hash(model)
    ap_hash = action_panel_hash(model, panel)
    al_hash = allocation_hash(allocation)
    alloc_tuple = None if allocation is None else tuple(allocation)

    gamma_tv: Fraction | None = None
    if separation_measure in (MEASURE_ACTION_TV, MEASURE_PRODUCT_TV):
        if gamma_l1 is not None:
            gamma_tv = tv_from_l1(gamma_l1)

    raw = T2CertificateV3(
        status=status,
        uncertainty_kind=uncertainty_kind,
        separation_measure=separation_measure,
        gamma_l1=gamma_l1,
        gamma_tv=gamma_tv,
        product_tv=product_tv,
        model_hash=m_hash,
        spec_hash=s_hash,
        catalog_hash=c_hash,
        action_panel_hash=ap_hash,
        allocation_hash=al_hash,
        panel=tuple(panel),
        allocation=alloc_tuple,
        p0=None if p0 is None else tuple(p0),
        p1=None if p1 is None else tuple(p1),
        difference_witness=None if difference_witness is None else tuple(difference_witness),
        convex_mixture_weights=None,  # discrete never fabricates convex weights
        primal_receipt="",
        dual_receipt="",
        generator_commit=generator_commit,
        generator_tree=generator_tree,
        collapsed=collapsed,
        notes=tuple(notes),
    )
    primal, dual = _receipts(raw)
    # Reconstruct with the same typed (Fraction) fields, only overriding the two
    # receipts.  Round-tripping through to_dict() would turn Fraction values into
    # {"numerator","denominator"} dicts, corrupting the in-memory certificate.
    return replace(raw, primal_receipt=primal, dual_receipt=dual)


class LegacyCertificateReadError(RuntimeError):
    """Raised when a legacy V2 certificate is read outside the legacy reader."""


def legacy_certificate_reader(cert) -> str:
    """Read a legacy (V2) certificate; V2 is never automatically verified.

    Returns the fixed status ``LEGACY_UNVERIFIED`` and never silently aliases
    to a V3 verification.  If the object is already a V3 certificate this
    raises, because V2/V3 must not be silently conflated.
    """
    if isinstance(cert, T2CertificateV3):
        raise LegacyCertificateReadError(
            "object is already a T2CertificateV3; no legacy read needed"
        )
    return "LEGACY_UNVERIFIED"
