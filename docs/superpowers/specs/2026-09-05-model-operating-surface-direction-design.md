# INVERTED Model Operating Surface Direction Design

## Status

Owner-approved architectural direction for INVERTED testing, model uplift, and future optimization.

This design strengthens the existing constitutional requirement that INVERTED must improve both whole-system capability and effective model-in-system capability. It does not erase frozen historical experiments; it changes how their evidence is interpreted and how future experiments are designed.

## Core objective

INVERTED is not searching for one universal prompt, one static support bundle, or a way for a smaller model to imitate a larger model.

The objective is to discover, validate, and eventually operationalize the **model-specific operating surface** that produces the highest defensible practical capability from each model.

The eventual control policy is conditional rather than static:

`Support = f(model, task, difficulty, failure/state, context pressure, resource target, evidence state)`

Cross-model comparison is diagnostic. One model remaining stronger than another is not, by itself, a failure condition.
## Surface dimensions

Future discovery must be allowed to test, where causally relevant:

1. ingredient identity and information source;
2. amount/dose, including nonlinear dose-response curves;
3. order and sequencing;
4. timing and trigger conditions;
5. placement/context layer;
6. representation and encoding;
7. compression and specificity;
8. pairwise and higher-order interactions;
9. task family and task difficulty;
10. model state, uncertainty, failure signature, and tool state;
11. context position and context pressure;
12. persistence across turns or stages;
13. dynamic/adaptive support policies;
14. latency, tokens, memory, compute, and external-action cost;
15. robustness and transfer under fresh, neighboring, adversarial, and sealed cases.

The list is a floor, not a ceiling. New dimensions may be added when evidence shows they can materially move the operating frontier.
## Definition of "best"

No single accuracy score defines the optimum.

Each model must be evaluated on a Pareto frontier that can include:

- verified task correctness;
- catastrophic and silent failure rate;
- generalization and stability;
- latency and throughput;
- input/output token burden;
- memory and compute burden;
- external/model-call burden;
- recoverability;
- robustness to perturbation;
- architecture complexity required to obtain the gain.

A treatment that is 1% below peak correctness but 12% faster may be more valuable for a specific operating region than the absolute peak. The evidence must preserve both points rather than collapsing them into one winner.

## Discovery before compression

During surface discovery, do not prematurely optimize for the smallest model, minimum context, minimum support, or minimum machinery.

First locate the defensible performance frontier and the causal mechanisms that create it. Only then search for minimum-equivalent, cheaper, faster, smaller, or simpler variants that preserve the desired capability.

Compression is a later optimization phase, not a discovery gate.
## Model-specific treatment

Models must not be treated as scaled versions of one another.

Existing evidence already shows that the tested small model and Qwen respond differently to the same support. Therefore future experiments must permit:

- different ingredient sets by model;
- different doses by model;
- different ordering/timing/placement by model;
- different representations by model;
- different dynamic trigger policies by model;
- different Pareto-optimal operating points by model.

The scientific question is not whether Small-A can equal Qwen. The question is how far each model can be moved above its own raw baseline, under which conditions, and at what cost.

## Search strategy

Future testing should reduce the search space sequentially rather than throw arbitrary bundles at the models:

`ingredients -> interactions -> dose curves -> order -> timing -> placement -> representation -> higher-order combinations -> negative-transfer boundaries -> model-specific frontier -> minimum-equivalent variants -> fresh transfer -> sealed confirmation`

Each stage must preserve enough evidence to support deterministic post-hoc analysis and avoid unnecessary retesting.
## HD-NEXT-1 interpretation

HD-NEXT-1 remains valid historical evidence for the protocol it actually ran. Its 467-call stopping point and fresh-gate result must not be rewritten after the fact.

However, its `Q-MODEL-SUBSTITUTION` stopping logic does **not** define the project objective. The run is retained as early response-surface evidence showing, among other things, that:

- model response to support is materially different across models;
- a development-selected small-model treatment can fail to transfer;
- ingredients can change sign or value under fresh evidence;
- model-specific search and matched own-baseline controls are required;
- future gates must not terminate solely because one model remains stronger than another.

Future work may reuse HD-NEXT-1 evidence, frozen assignments, and zero-call analyses where scientifically valid, but must label any post-hoc continuation separately from the original experiment.

## Canonical alignment

The approved direction must be reflected in:

- `REPO_LAWS_AND_REGULATIONS.md` as canonical project/testing law;
- `TESTING.md` as the concrete experiment-policy contract;
- `MODEL_OPERATING_RULES.md` as the compact future-agent interpretation;
- `README.md` as the public project direction;
- `INVERTED_BIG_REQUEST_REFERENCE.md` as the large-request guard against premature compression.

`INVERTED_CONSTITUTION.md` Law 4 already supports this direction and remains authoritative.
