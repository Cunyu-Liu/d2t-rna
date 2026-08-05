# D2T-RNA v7 — Confirmed Core Contribution (PAPER-1)

> 状态：贡献句已锁定（single core contribution）。本文件在 substantive manuscript
> writing 之前创建，作为主文与所有 claim 的唯一锚点。

## Core Contribution（唯一核心贡献句）

> 在预注册的有限 RNA state/action/observation model 下，D2T-RNA 对完整的
> target/rival cross-class difference set 提供可重放的 collision-or-separation
> certificates，将 robust action-level separation 转化为 fixed-horizon
> finite-sample decision/budget bounds，并给出 costed design 与 design-class
> no-go certificates；公开 RNA 数据仅用于固定已实现数据集内的 fail-closed
> retrospective evidence audit，不构成 prospective、held-out 或 independent
> validation。

## Why This Contribution Is Needed

Classical marginal-fiber identifiability (Markov-basis / kernel / rank arguments)
tells us *when* a fiber is connected but does not give a *replayable, checkable
certificate* over a specific finite registered RNA model, nor a decision-theoretic
consequence tied to a fixed RNA action geometry. Standard Test-Cover and
fixed-horizon active-testing bounds are not, by themselves, existence/separation
certificates over a complete difference set with registered nuisance coupling.

## How This Paper Responds

It pins the science to a finite registered model and delivers, for that model,
(1) an exact collision-or-separation certificate over the complete difference set,
(2) a finite-sample decision/budget consequence under fixed non-adaptive allocation,
and (3) a costed integer design with a design-class no-go certificate — all backed by
rational primal/dual and independent-checker evidence, and replayed reproducibly.

## Evidence Required

- exact certificate over complete registered D (primal + dual + independent checker)
- finite-sample bound cross-checked against exact oracle enumeration
- integer design + LP dual lower bound + integrality gap + no-go interpretation
- executed synthetic baselines (model-conditional)
- fail-closed retrospective evidence audit over add / SAM-III / RORC

## Evidence Available

- T2b/T2c/T2d manifests (status PASS, hashes verified in PAPER-0)
- §9 matrix (11 microcases, 8 executed baselines, model-conditional)
- §10 validation (assumption boundary, independence checker, claim lint)
- R2 fail-closed terminal outcomes (add / sam-iii / rorc) + S12 submission gate

## Evidence Missing

No qualified retrospective quantitative instance is available.
No new blinded/prospective RNA experiment was performed.
No independent library exists.
No population-level or future wet-lab risk/coverage claim is supported.

## Strong Claims Allowed

- exact collision-or-separation certificate within the registered finite model
- fixed-horizon finite-sample decision/budget bounds for the registered pair catalog
- costed integer design and design-class no-go certificate
- executed model-conditional synthetic evaluation
- complete fail-closed retrospective evidence audit

## Claims To Soften Or Avoid

- universal RNA identifiability / general RNA structure inference
- population generalization / independent-library / prospective validation
- actual future wet-lab cost saving
- any claim over unregistered continuous SHAPE/DMS channels or third-state discovery

## Novelty Risk

T2 geometry is a *use* of classical marginal-fiber / fixed-horizon-testing theory, not
a claim to a new universal theorem. Novelty must rest on the RNA-feasible composite
formulation: complete registered difference set, explicit cross-class nuisance coupling,
exact replayable certificate, and finite-sample/no-go consequences tied to RNA action
geometry. See `prior_art_novelty_matrix.md`.

## Significance Risk

Without a qualified retrospective quantitative instance, the paper is a
methods/theory contribution whose significance depends on the sharpness and
replayability of the certificate and design consequences, not on empirical
superiority or biological validation. This must be stated honestly.

---

## Contribution Gate (结构检查)

```text
PAPER_CONTRIBUTION_GATE:
  exactly_one_core_contribution: true
  falsifiable: true
  model_scope_explicit: true
  evidence_missing_explicit: true
  novelty_boundary_explicit: true
  no_prohibited_claim: true
```

Gate 判定：**PASS**。所有结构项为真，核心贡献为单一、可证伪、模型范围明确、
证据缺失如实声明、novelty 边界明确、无禁止词越权表述。
