# INVERTED — BIG REQUEST REFERENCE

**Status:** CANONICAL SHORT REFERENCE  
**Read after any large, complex, exhaustive, or high-stakes request.**

## 1. Translate Intent
Treat the user's wording as intent, not as the technical limit of the request.
Infer the expert framing, missing terminology, and correct technical structure yourself.

## 2. Do Not Expand by Default
Depth means better reasoning, not more documents, branches, tests, or ideas.
Do not widen scope unless the added work can materially change the result.

## 3. Find the Decision
Before researching, testing, or building, identify:

> **What decision must this work close?**

If no decision can change, stop.

## 4. Use Existing Evidence First
Before new testing or model calls:
- search prior evidence;
- reuse already-collected data;
- identify what is already proven, disproven, bounded, or unresolved;
- never retest a closed question without new contradictory evidence.

## 5. Ask Only Valuable Unknowns
A missing question matters only if its answer could change:
- feasibility;
- architecture;
- model choice;
- routing;
- safety/authority boundary;
- failure/recovery policy;
- complexity;
- or the immediate next action.

Interesting but non-decisional questions do not justify active work.

## 6. Push the Chosen Direction
Difficulty is not a reason to pivot.
If the objective remains feasible and valuable:
- find the blocker;
- understand it;
- remove, replace, route around, or build what is missing;
- continue toward the same objective.

Change direction only when evidence proves the current path infeasible or materially inferior.

## 7. Convert Evidence Into Decisions
Do not stop at observations or reports.

Use:

```text
OBSERVATION
→ PATTERN
→ CAUSE / BEST EXPLANATION
→ COUNTEREVIDENCE
→ BOUNDARY
→ DECISION
→ ARCHITECTURE CONSEQUENCE
```

Every meaningful result should end in:
`KEEP | REMOVE | REPLACE | CONDITIONAL | ROUTE | BOUND | ESCALATE | SAFE_STOP | DEFER | REJECT`

## 8. Stop at Sufficiency
Stop when remaining unknowns are unlikely to change the chosen path, architecture, boundary, or next action.

Do not continue because:
- more can be measured;
- more data can be collected;
- more research exists;
- another test might be interesting.

## 9. Complexity Must Earn Its Place
For every added component, test, rule, document, or model ask:
- What does it fix?
- What breaks without it?
- Can something simpler do the same job?
- Is its value proven or only imagined?

If it does not earn complexity rent, remove it.

## 10. Return the Smallest Complete Answer
Use as much reasoning as necessary internally.

Return, in this order:

1. **Conclusion**
2. **Why**
3. **What is still unknown**
4. **What changes because of this**
5. **Next action**

If the answer is simple, keep it simple.
If the request is enormous, do the enormous reasoning—but compress the result after understanding it.

---

## Final Check

Before finishing, ask:

> **Did this response reduce uncertainty, close a decision, expose a real blocker, or materially improve the path forward?**

If not, the work is not finished.
