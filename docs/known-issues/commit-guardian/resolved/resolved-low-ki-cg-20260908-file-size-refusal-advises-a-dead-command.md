---
title: "KI-CG-20260908-file-size-refusal-advises-a-dead-command — the only remediation the live file-size gate offers points at a slash command whose own first step runs a script that does not exist"
description: "medium — the verdict is correct and the commit is refused for a real reason; what fails is the single piece of advice attached to it. No wrong belief about the code, but every author blocked by this gate is sent down a path that dead-ends o"
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

# KI-CG-20260908-file-size-refusal-advises-a-dead-command — the only remediation the live file-size gate offers points at a slash command whose own first step runs a script that does not exist

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — the verdict is correct and the commit is refused for a real reason; what fails is the single piece of advice attached to it. No wrong belief about the code, but every author blocked by this gate is sent down a path that dead-ends one step in, and the gate has been blocking commits repo-wide since 2026-09-07.
- **Status:** RESOLVED 2026-09-08 — the dead instruction is deleted rather than replaced. `templates/workflows/code-refactoring-specialist.md` step 1 no longer invokes any tool; its remaining four steps (characterization tests, plan, execute, clean up) are untouched and still useful. Deletion is the correct fix, not a workaround: `GE-127e-3`'s fourth arm explicitly makes a refusal that offers nothing compliant, precisely so removing a false promise is never blocked by a requirement to promise something. Creating the missing `analyze_structure.py` was considered and rejected — `GE-127e-1` specifies a per-file description engine producing exactly the "deterministic map of the file" that instruction asked for, and building a second one now is the duplication `GE-127e`'s CR-100/INF-800 fences exist to prevent.
- **Covered by:** `GE-127e-3-ii` ("Every tool named by an instruction a refusal sends the author to actually exists"), an L3 technical constraint under `GE-127e-3`, with `unit_tests/commit_guardian/test_ge_127e_3_ii.py`. The test **discovers** invoked paths from the command file's text at run time and resolves each against the repository — it does not assert this one known-bad string is absent, so it keeps working against the next dead pointer. Proven by mutation: red with the fix reverted, green with it applied.
- **Does NOT close `GE-127e-3`.** That criterion has three further arms — no future-tense promise, "already done" claims checked against the run that produced the refusal, and a bare verdict being explicitly compliant. One instance of a violation removed is not the criterion satisfied; `GE-127e-3` stays `work_status: todo`.
- **Still open, deliberately out of scope:** the same command routes to `@documentation-expert` for `.md` files, and `.md` is not in `file_size.checked_extensions` (`['.py', '.sql']`), so that branch is unreachable for anyone arriving from this gate. It is inert rather than broken, and an agent reference is not a tool invoked by path — `GE-127e-3-ii` constrains its population to path invocations explicitly.
- **Occurrences:** 1 (structural — it is true of every refusal the gate has ever emitted)
- **First seen:** 2026-09-08, found while enriching `GE-127e-3` · **Last seen:** 2026-09-08
- **Where:** `templates/scripts/commit_guardian/check_file_size.py:234` and `:236` — both refusal branches print "Use the `/code-refactoring-specialist` slash command" · `templates/workflows/code-refactoring-specialist.md:12` — that command's step 1 instructs `python .agent/skills/code-analysis/scripts/analyze_structure.py <file>`

**Symptom.** A commit refused for file length prints, as its only actionable line:

```text
   Use the `/code-refactoring-specialist` slash command to intelligently split this Python file.
```

The command is real and is deployed. Its step 1 is not: `find` across the whole workspace returns nothing for `analyze_structure.py`, and no directory named `.agent/skills/code-analysis/` exists. So an author who follows the advice reaches a dead end on the first instruction.

**Second, quieter half of the same defect.** The same command file routes to `@documentation-expert` for `.md` files. `.md` is not in `file_size.checked_extensions`, so that branch is unreachable from this gate at every commit. It is not wrong, it is inert — and it pads the command with a path no reader arriving from here can ever take.

**Mechanism.** Two artifacts maintained independently, with a pointer between them and nothing checking the pointer resolves. The guard's message names a command; the command names a script; nothing anywhere asserts the script exists. This is one hop longer than the classic broken-link case, which is why it survived: the command itself resolves, so any check that stopped at "does the slash command exist" would pass. `GE-127e-3`'s descriptor is deliberately written to follow the chain all the way down and carry the action out, rather than assert the text is present.

**Why medium and not high.** It cannot produce a wrong verdict — the file genuinely is over its limit and the refusal is correct. The cost is an author's time and the credibility of the gate's advice. But note the direction of travel: `GE-127e`'s notes argue that the pressure that destroys a size standard is the cost of complying with it at the moment you are blocked, and that the cheap responses are to strip content, raise the limit, or switch the gate off. Advice that dead-ends raises exactly that cost. That is the reason this is filed rather than left as a cosmetic nit.

**Fix direction.** Two options, and the smaller one is legitimate. Either repair the command's step 1 to name a tool that exists, or delete the pointer and let the refusal be a bare verdict — `GE-127e-3`'s fourth arm explicitly makes "a refusal offering nothing" compliant, precisely so that removing a false promise is never blocked by the requirement to promise something. Do NOT satisfy this by rewording the sentence while leaving the chain broken. The durable fix is `GE-127e-1`/`GE-127e-2`, which replace the fixed pointer with guidance derived from the file in hand.

**Related.**
- `GE-127e-3` and `GE-127e-3-i` — the criteria written against this shape; this entry is their first real instance and should be closed by their implementation, not separately.
- `GE-122c-1` — the recorded anti-precedent this repeats: a gate documented as automatically dispatching a triage agent that does not do so. Same failure, different gate, and it is the scar `GE-127e`'s notes cite as load-bearing.
- `KI-CG-20260908-covers-tag-must-be-inside-a-test-function` (above) — unrelated mechanism, same day, same investigation.

**Pattern:** a pointer chain where every hop but the last resolves, so any check short of carrying the action out reports it healthy.

---
