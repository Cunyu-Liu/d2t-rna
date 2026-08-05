# D2T-RNA v7 — Section Blueprint (PAPER-1)

> 主文结构与章节顺序，全部服务于 novelty delta 与 claim boundary。

## 4.1 Introduction（固定顺序）

1. field problem — 有限 RNA 观测系统下 target/rival 状态的可识别性与可验证设计
2. what existing methods already solve — Markov-basis / Test-Cover / fixed-horizon testing
3. specific identifiability/design gap — 缺少针对完整注册差集 D 的可重放证书 + 决策后果
4. why generic cycle or Test-Cover arguments are insufficient
5. research question
6. one-sentence core contribution（同 confirmed_contribution.md）
7. evidence and exact scope
8. claim boundary

## 4.2 Related work（四小节）

- Markov-basis and marginal-fiber identifiability
- controlled sensing and fixed-horizon testing
- costed experimental design
- RNA chemical-mapping and retrospective evidence boundaries

每一段服务于 novelty delta，不作泛泛综述。

## 4.3 Registered finite RNA model

明确写出：
```text
finite latent state space
two target/rival model classes
marginal map M
action maps B_u
complete difference set D
gamma(S)
finite categorical observation laws
nuisance coupling
fixed non-adaptive horizon
independence assumptions
abstention rule
```
明确不能覆盖：
```text
continuous infinite-dimensional nuisance
adaptive actions
randomized design
sequential stopping
arbitrary high-dimensional contingency tables
unregistered continuous SHAPE/DMS observation channel
unknown action-induced state change
unmodeled third state
```

## 4.4 T2b exact theorem

只声称：registered finite model 内，gamma(S)=0 → exact collision witness，
gamma(S)>0 → separation certificate，rational primal/dual + independent checker。
不写成 universal RNA identifiability / general inference / all high-dim models。

## 4.5 T2c finite-sample consequence

只声称：finite registered pair catalog，fixed-horizon deterministic non-adaptive
allocation，complete action-level likelihoods，product-law when registered，exact
TV/Hellinger/decision crosscheck。
必须说明：no composite-continuous covering theorem，no arbitrary continuous nuisance
guarantee，no real-data calibration guarantee。

## 4.6 T2d costed design/no-go

报告：integer design，LP relaxation，dual burden lower bound，integrality gap，
independent checker，design-class no-go。
不声称：globally optimal RNA experimental design，universal minimum cost，
wet-lab cost already saved。

## 4.7 §9 synthetic evaluation and baselines

11 微案例 + 8 baseline 作为 model-conditional synthetic evaluation。
明确：executed baseline ≠ biological superiority，oracle agreement ≠ population
generalization，runtime/memory 仅 computational evidence。

## 4.8 Task6-R retrospective evidence（evidence qualification，非 validation）

| Dataset | Registered role | R2 outcome | What can be reported | What cannot be claimed |
|---|---|---|---|---|
| add/RMDB | retrospective full-matrix compression if qualified | NOT_COMPARABLE_BY_REGISTERED_OBSERVATION_MODEL | modality limitation, raw provenance, fail-closed audit | categorical replay, quantitative T2 validation, future cost saving |
| SAM-III | modality-transfer diagnostic | NOT_COMPARABLE_BY_REGISTERED_ACTION_SPACE | action/modality incompatibility, diagnostic failure | unified benchmark, quantitative transfer |
| RORC | exposed misspecification stress | NOT_APPLICABLE | explicit terminal audit, boundary semantics | independent validation, unseen OOD, third-state discovery |

RORC 无正式 public accession，保留 NOT_APPLICABLE；不替换成同名基因或无关数据。

## 4.9 Misspecification and abstention

valid registered assumptions -> PROCEED；assumption violation -> NOT_ESTABLISHED / abstain。
作为理论边界与可信度证据，不写成 real-data validation。

## 4.10 Discussion

回答：What is genuinely new? What is inherited? Why is the RNA-feasible composite
formulation useful? What does the finite-sample consequence add? What can never be
claimed without a new library or prospective experiment?
