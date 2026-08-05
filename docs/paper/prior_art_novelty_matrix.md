# D2T-RNA v7 — Prior-Art Novelty Matrix (PAPER-1 Gate)

> 目的：在本轮任何 Results 写作之前，逐项比较 prior art，判定 novelty delta 是否可防守。
> 诚实原则：不把 classical 组件冒充为全新定理；novelty 只能来自 RNA-feasible 复合框架。

## 1. 逐项比较

| Prior art | What it gives | Why insufficient alone | This paper delta |
|---|---|---|---|
| Diaconis–Sturmfels / Markov-basis | fiber connectivity across a complete contingency table | tells *when* fibers connect, not a bounded *replayable certificate* over a specific finite model | complete registered D + exact rational certificate with independent checker |
| 2x2 fixed-marginal swaps | local Markov moves generate the fiber | works on 2x2 fixed margins; not a decision/cost consequence | used only as a building block; not claimed as novelty |
| 3D fixed-marginal complexity | higher-dimension fibers are complex | underlines why a *generic* theorem is hard | motivates the finite registered formulation; no universal 3D claim |
| Test Cover | set cover for separating instances | NP-hardness / approximation; not an exact design certificate | auditable integer design + LP dual bound + no-go over registered model |
| fixed-horizon active hypothesis testing | sample-complexity bounds | generic bounds, not tied to RNA action geometry nor abstention rule | finite-sample decision/budget bounds cross-checked by exact oracle, with abstention |
| binary testing sample complexity | standard TV/Hellinger scalings | generic scaling, not a registered cross-class coupling certificate | exact product-law TV/Hellinger/decision enumeration over registered pair catalog |
| TV/Hellinger/Chernoff/Hoeffding bounds | tail/concentration | generic tools, not a violation certificate | used as bounds; not claimed as novelty |
| costed information-source selection | cost-aware sensor selection | generic cost model, not an integer design + integrality-gap certificate | integer design + LP dual burden + integrality gap + no-go |
| T-optimal / optimal experimental design | optimal design theory | not a replayable collision/separation certificate over RNA-feasible actions | collision-or-separation framing over RNA action library |
| RNA chemical-mapping experimental design | SHAPE/DMS assay design heuristics | assay guidance, not a registered categorical observation-law model | explicit finite categorical observation laws; SHAPE/DMS continuous channels excluded |
| mutate-and-map / LM2R-style | heuristic probe selection | heuristics, no exact certificate | executed as a baseline only (§9), not claimed as superior |
| abstaining and misspecification-aware decisions | abstain/robust decisions | generic abstention, not a registered nuisance coupling | registered coupling (CARTESIAN / EQUAL_REALIZED_VALUE) + fail-closed NOT_ESTABLISHED boundary |

## 2. 明确不在本题主张 novelty 的项（inherited）

```text
Not novel by itself:
  alternating cycles
  2x2 Markov moves
  generic kernel/rank identifiability
  Test Cover
  generic Hellinger or Chernoff scaling
  generic fixed-horizon active testing
  generic costed information-source selection
```

## 3. 可防守的 novelty delta

```text
Potential novelty delta (composite, model-conditional, replayable):
  RNA-feasible composite uncertainty
  explicit cross-class nuisance coupling
  complete feasible difference set D
  exact replayable collision/separation certificate
  finite-sample consequence tied to RNA action geometry
  auditable integer design/no-go certificate
```

**判定：`T2_NOVELTY_ESTABLISHED`（可防守的复合框架 novelty delta）。**

> [!IMPORTANT] Author re-evaluation (2026-08-05): this verdict is SUPERSEDED by > `prior_art_novelty_matrix_REVISED.md`, which downgrades it to `METHODS_LEVEL_NOVELTY_ONLY` > (theorem-level novelty NOT ESTABLISHED; framework-level novelty modest and methods-only). > The paper must be positioned as a methods/experimental-design contribution.

依据：本论文的贡献不是"一个新的通用图论/统计学定理"，而是把一个 classical
building block（marginal-fiber、Test-Cover、fixed-horizon testing、costed design）
组合成一个**预注册有限 RNA 模型上的可重放、可独立检查的证书框架**，并给出
finite-sample decision/budget 与 costed no-go 后果。该组合框架本身是 methods-level
novelty，且有 exact primal/dual + independent checker + 可重放证据支撑。

## 4. 边界声明（必须保留）

- 不声称 universal RNA identifiability / general RNA structure inference。
- 不声称 population-level 泛化、independent-library validation、prospective validation。
- 不声称 future wet-lab cost saving。
- SHAPE/DMS 连续通道、unknown action-induced state change、unmodeled third state 明确排除。
- 若上述边界被破坏，novelty 判定自动降级为 `T2_NOVELTY_NOT_ESTABLISHED`。
