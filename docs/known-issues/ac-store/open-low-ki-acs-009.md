---
title: "KI-ACS-009 — The documented AC-store pre-flight runs a weaker validator than the required CI gate, so a clean local check does not predict CI"
description: "KI-ACS-009 — The documented AC-store pre-flight runs a weaker validator than the required CI gate, so a clean local check does not predict CI"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-009 — The documented AC-store pre-flight runs a weaker validator than the required CI gate, so a clean local check does not predict CI

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 2
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26
- **Where:** `CLAUDE.md` → "AC-store hygiene — bulk pre-flight", against the
  `check-ac-schema` pre-commit hook that the required `AC store valid` job runs

**2026-08-26 — reproduced exactly, on the same rule this entry's retraction story is about.**
Generating the `BP-1100g-4` ticket, `validate_ac_schema.py` over the whole `BP-1100`
feature folder reported `OK: all 58 AC YAML files are valid`. The very next `git commit`
was blocked by `check-ac-schema` on one of those 58:

```
BP-1100g-4.yaml: declares_side_effect is authored as True but this AC's own Then
clause derives False — the two disagree ... (BO-2900g-2)
```

Same store, same moment, two validators, opposite verdicts — and the weaker one is the
command `CLAUDE.md` still prescribes. Two details worth adding to the record. First, the
disagreement was **pre-existing since 2026-08-17** and surfaced only because that record
happened to be staged: the hook reads the git index, so a store-wide violation is
structurally invisible until something touches the file (the forward-ratchet property this
register keeps rediscovering). Second, the resolution direction is not symmetric —
`criteria` is the authored requirement and the fixed point, so the derived boolean yields
to it, never the reverse.

**Symptom.** There are two AC validators and they enforce different rules.
`scripts/ac_store/validate_ac_schema.py` checks the record against the schema. The
required CI job runs `pre-commit run check-ac-schema`, which additionally enforces
binding completeness, field preservation (ACS-500f-1), test-contract rules, and
derived-field rules such as `declares_side_effect` (BO-2900g-2). `CLAUDE.md`'s pre-flight
section prescribes only the former.

**A retracted correction, 2026-08-25 — and the retraction is the useful part.** On
2026-08-24 this paragraph was edited to say the `declares_side_effect` (BO-2900g-2) example
was fabricated and that no gate enforces the field. **That edit was wrong. The original
text was right, and has been restored.** `check-ac-schema` does enforce it: CI failed PR
#529 with *"declares_side_effect is authored as True but this AC's own Then clause derives
False — the two disagree … (BO-2900g-2)"*.

The mistake is worth keeping because it is this entry's own subject, one layer down. Two
agents independently grepped `scripts/commit_guardian/` and `.leafcutter/scripts/
commit_guardian/`, found nothing, and concluded the rule did not exist. The rule lives in
**`templates/scripts/commit_guardian/_ac_schema_validators.py`** — `templates/` is the
source the build deploys *from*; `scripts/commit_guardian/` in a worktree is a build output
frozen at whenever that worktree was last built (KI-BP-004). Running the hook locally
passed for exactly the same reason: the local hook was the stale copy, without the rule.

So the sequence was: entry states a true fact → two agents check it against the deployed
tree and get a false negative → entry is "corrected" into an untruth → CI, which builds
before running the hooks, contradicts all of it. Local hook agreement is not evidence the
rule is absent; it is evidence about the age of your deploy. Grep `templates/scripts/` when
asking what a hook enforces, and treat a passing local hook as unverified until CI agrees.

Running the weaker validator and seeing `OK: all N AC YAML files are valid` therefore establishes
much less than it appears to, and the gap is invisible because both are called "the
schema validator" in conversation.

**Evidence.** PR #510, 2026-08-19. `find ... -exec validate_ac_schema.py {} +` reported
all 82 files in the touched folder valid, and every folder-level run during authoring was
clean. CI then failed `AC store valid` on two of those same files —
`BO-2400c-1-v.yaml` and `BO-2600b-2.yaml` — both missing `declares_side_effect: true`,
a rule that had merged from main mid-branch and that the prescribed command does not
implement. Running `env --chdir=<repo> pre-commit run check-ac-schema --all-files`
reproduced the failure locally in one command, and confirmed the fix.

**Why it is worth recording rather than just remembering.** The pre-flight exists
specifically so store violations surface in a batch instead of as a per-commit cascade.
A pre-flight that runs a strictly weaker check than the gate it is meant to anticipate
does not do that job, and it is the second defect found in this same CLAUDE.md section —
the first being the bare-directory no-op now recorded as KI-ACS-001. Both share a shape:
the documented defence was believed to be equivalent to the enforced one.

**Fix direction.** Change the prescribed pre-flight command to the hook the gate actually
runs — `env --chdir=<repo-root> pre-commit run check-ac-schema --all-files` — and keep
`validate_ac_schema.py` only for single-file spot checks where its narrower scope is
understood. Longer term the two should not diverge silently: either the hook calls the
script, or the script grows the hook's rules, so there is one answer to "is this store
valid". Note the hook reads the git **index**, so files must be staged before it can see
them — an unstaged fix will appear not to work.

---
