---
title: "KI-CG-007 — The sanctioned way to add a component produces an entry the required gate rejects, and the gate's stated rule is weaker than the one it enforces"
description: "KI-CG-007 — The sanctioned way to add a component produces an entry the required gate rejects, and the gate's stated rule is weaker than the one it enforces"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-007 — The sanctioned way to add a component produces an entry the required gate rejects, and the gate's stated rule is weaker than the one it enforces

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `scripts/add_component.py` (writer) · `templates/scripts/commit_guardian/check_components_integrity.py:475-540` (gate) · `docs/components.json` (the registry)

**Symptom.** Registering a component the documented way blocks your commit, twice, for
reasons the tooling does not tell you in advance. Four separate defects compound:

**1. The writer and the gate disagree.** `scripts/add_component.py` — wrapped by the
`add-component` skill precisely so "agents can add a new entry … without knowing the
script path or argument format" — has no flags for `agent_affinity` or
`exposed_interfaces` and writes neither. `check-components-integrity` requires **both** on
every new component and blocks the commit. The tool the project provides for this job
cannot produce output the project's own required gate accepts.

**2. The stated rule is weaker than the enforced rule.** The gate's failure output prints:

```
5. An 'agent_affinity' field that is a JSON array (use [] if none).
6. An 'exposed_interfaces' field that is a JSON array (use [] if none).
```

Following that exactly — a JSON array of strings — fails on the next attempt with
`exposed_interfaces[0] must be a JSON object`. The code additionally requires each element
to be an object carrying `name`, `type`, `path` and `shape`, with `type` drawn from a fixed
seven-value set (`VALID_INTERFACE_TYPES`, line 110). None of that appears in the message.
An author who reads the error and complies is still blocked, and only reading the hook
source resolves it.

**3. Grandfathering means there is no precedent to copy.** The gate checks only components
whose entry appears in the diff — *"Existing components (no diff) are not checked — legacy
state is accepted."* So **zero** of the 42 pre-existing entries carry `agent_affinity` or
`exposed_interfaces`. The first author to add a component cannot look at a neighbour to
learn the shape, and whatever they invent silently becomes the precedent for a validated
field. `security_scanner` (added 2026-08-19) is that first entry.

**4. The registry has no owning component.** No entry in `docs/components.json` claims
`docs/components.json` or `scripts/add_component.py` in its `primary_code`, and there is no
`component_registry` component. This issue is filed here because
`check_components_integrity.py` is a commit-guardian hook, but the writer half genuinely
has no home — which is why the two halves were free to drift apart in the first place.

**Evidence.** Adding `security_scanner` on 2026-08-19 took three commit attempts:

```
attempt 1  [x] 'agent_affinity' field is required (use [] if no agent affinity).
           [x] 'exposed_interfaces' field is required (use [] if ... no external interfaces).
attempt 2  [x] exposed_interfaces[0] must be a JSON object.
           [x] exposed_interfaces[1] must be a JSON object.
attempt 3  passed
```

Both blocks came from `add_component.py`'s own output, unmodified.

**Fix direction.** In descending order of payoff:

- **Teach the writer the full contract.** Give `add_component.py` `--agent-affinity` and
  `--exposed-interface` flags, and have it emit the required element shape. A generator
  that cannot satisfy the validator is worse than no generator, because it is trusted.
- **Make the printed rule the enforced rule.** The message must state the element schema
  and the valid `type` values, or point at them. A gate whose remedy does not resolve the
  failure trains people to bypass it.
- **Decide whether grandfathering is permanent.** Either backfill the 42 legacy entries so
  new authors have a pattern to copy, or say explicitly in the registry that these fields
  are new-entries-only. The current state reads as "everyone else omitted this", which is
  the opposite of the intended signal.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8, in its inverse form — not a
check that passes when it should fail, but a check whose documented contract and enforced
contract differ, so compliance with the message is not compliance with the gate.

---
