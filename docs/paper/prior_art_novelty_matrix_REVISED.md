# D2T-RNA v7 — Revised Prior-Art Novelty Assessment

> **Status: `METHODS_LEVEL_NOVELTY_ONLY`** (revised from `T2_NOVELTY_ESTABLISHED`)
> This is a deliberate, critical re-assessment requested by the author. It downgrades
> the novelty claim from "established composite-framework novelty" to a more
> conservative, honestly-scoped position. It does not retract the executable work;
> it re-frames how novelty may be claimed.

## 1. Why the earlier verdict was too strong

The prior `T2_NOVELTY_ESTABLISHED` framing called the "composite framework" a defensible
novelty delta. That is only partially defensible. A critical reviewer can correctly argue:

1. **Exact collision-or-separation over a finite difference set** is essentially
   kernel/rank identifiability (and, for the two-class categorical case, a finite
   linear-algebra separation) restated for a toy finite model. Not a new theorem.
2. **The finite-sample decision/budget consequence** is standard fixed-horizon
   testing with Hellinger/Chernoff bounds, cross-checked by enumeration. The bound
   itself is not new.
3. **The costed integer design + LP dual + integrality gap** is Test-Cover (or generic
   costed information-source selection) with an LP relaxation. The formulation is not new.
4. **The abstraction decision** (abstain / NOT_ESTABLISHED) is standard
   misspecification-aware decision theory.

Every *mathematical component* is classical. Calling the combination "established novelty"
overstates the case and invites a strong rejection.

## 2. What is genuinely new (and only this may be claimed)

The only defensible novelty is at the **methods/framework** level, and it is narrow:

```
RNA-feasible composite registration:
  - complete registered cross-class difference set D (not a hand-picked cycle subset),
  - explicit pre-registered nuisance coupling (CARTESIAN / EQUAL_REALIZED_VALUE),
  - an exact, replayable, independently-checked certificate over that D,
  - finite-sample and costed no-go consequences tied to the RNA action geometry,
  - fail-closed retrospective data qualification (no fabricated quantitative instance).
```

This is a **methods contribution, not a theorem contribution**. It is defensible only if
the paper (a) explicitly states every building block is inherited, and (b) does not
headline any single mathematical component as novel.

## 3. Honest risk assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Reviewer: "restatement of known results on a toy finite model" | Medium-High | Own it up front; position as methods/framework; scope the claim to the registered model |
| Reviewer: "no empirical/biological validation, so why is this a paper?" | Medium | Emphasize the replayable certificate + fail-closed audit as the contribution; state no validation claim |
| Reviewer: "finite model is too small / toy" | Medium | The model scope is the point: a *pre-registered finite* model is what makes the certificate exact and checkable |
| Novelty gate at a top venue | High | Target a methods/experimental-design venue, not a broad-theory venue |

## 4. Revised claim policy

- **Must claim**: replayable, checked, model-conditional certificate framework over a complete
  registered difference set; exact auditability; fail-closed data qualification.
- **Must NOT headline as novel**: any single mathematical component (fiber connectivity,
  finite-horizon bounds, Test-Cover, LP duality).
- **Must NOT claim**: universal RNA identifiability, a new universal theorem, population
  generalization, or future wet-lab cost saving.

## 5. Revised verdict

```text
THEOREM-LEVEL NOVELTY:   NOT ESTABLISHED (all components classical; no new universal theorem)
FRAMEWORK-LEVEL NOVELTY: MODEST, DEFENSIBLE AS METHODS (RNA-feasible composite registration +
                         exact replayable certificate + fail-closed audit)
PAPER NOVELTY GATE:      PASS ONLY IF positioned as methods/framework with all building blocks
                         explicitly inherited and the claim scoped to the registered finite model
```

The paper is publishable as a **methods/experimental-design contribution** with a modest,
clearly-scoped novelty claim, at a methods venue. It is **not** defensible as a novel
theorem paper. The `submission_readiness` status and abstract are consistent with this
(the abstract already claims "a certified design method whose scope is bounded by the
registered finite model", not a theorem).