# Harvest D → Test 5 Handoff Schema

Harvest D does not authorize Test 5 optimization until D7 can populate every required section below.

## Required sections

### Responsibility contract
For each material responsibility:
- responsibility
- owner: `KERNEL | SYSTEM | MODEL | HYBRID | VERIFIER | RECOVERY`
- evidence state
- supporting causal cases
- counterevidence
- remaining boundary

### Mechanism map
For each tested mechanism:
- mechanism ID
- classification: `REQUIRED | CONDITIONAL | REDUNDANT | HARMFUL | UNRESOLVED`
- applicable capability/family region
- matched intervention/sham effect
- system-involvement burden
- regression status

### Model capability envelope
For each model × capability × family:
- raw boundary
- assisted boundary
- maximum-proven-assisted boundary
- state: `RELIABLE | CONDITIONAL | UNSTABLE | FAILS`
- uncertainty / sequential decision

### Architecture substitution
- raw model-size gap
- assisted model-size gap
- SDI
- frontier shift
- substitution efficiency
- minimum required scaffolding

### Qwen call policy
- observable route features
- missed escalation
- false escalation
- Qwen precision/recall
- Qwen call fraction
- routing regret
- regions for `ROUTINE_LOCAL`, `SCAFFOLDED_LOCAL`, `QWEN_STANDARD`, `QWEN_MAX`, `NOVELTY_INVESTIGATION`, `ACQUIRE_EVIDENCE`, `SAFE_STOP`

### Capability ratchet
For each promoted knowledge object:
- originating novel failure
- Qwen Explorer hypothesis
- targeted/sham causal evidence
- neighbor/fresh generalization
- regression result
- prior model/scaffold requirement
- post-promotion minimum model/scaffold requirement
- Qwen retirement result
- negative-transfer result
- rollback target

### Closure ledger
Every P0/P1 question must be one of:
- `FREEZE`
- `TUNE`
- `REJECT`
- `DEFER`
- `UNRESOLVED_BUT_IDENTIFIED`

Forbidden handoff states: UNKNOWN WHY, UNKNOWN WHETHER IT MATTERS, UNKNOWN WHAT TO TEST, MAYBE USEFUL.

## Test 5 authorization rule

Test 5 receives only causally live mechanisms, known harmful mechanisms, interaction candidates, threshold regions, model capability envelopes, Qwen routing policy, and explicit residual unknowns. Test 5 is optimization/compression, not broad architecture rediscovery.