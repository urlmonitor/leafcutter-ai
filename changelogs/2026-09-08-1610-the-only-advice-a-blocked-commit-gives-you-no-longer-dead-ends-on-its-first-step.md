---
title: "The only advice a blocked commit gives you no longer dead-ends on its first step"
date: "2026-09-08"
time: "16:10"
type: manual
components:
  - commit_guardian
  - ac_store
summary: "The file-size gate's single piece of remediation advice sent every blocked author to a slash command whose own first instruction ran a script that does not exist anywhere in the repository; the dead instruction is deleted rather than replaced, and a new acceptance criterion plus a test now resolve every tool path a refusal points at, so the next dead pointer is caught rather than shipped."
description: "check_file_size.py:234 prints 'Use the /code-refactoring-specialist slash command' as the only actionable line in a file-size refusal. That command exists and is deployed, but step 1 of templates/workflows/code-refactoring-specialist.md instructed running .agent/skills/code-analysis/scripts/analyze_structure.py, which exists nowhere in the workspace — so the advice dead-ended one hop down, on a gate that has been blocking commits repo-wide since 2026-09-07. The instruction is deleted, not replaced: GE-127e-3's fourth arm makes a refusal that offers nothing explicitly compliant, and GE-127e-1 already specifies the per-file description engine that would produce the same 'deterministic map of the file'. New L3 GE-127e-3-ii under GE-127e-3 pins the rule (every tool a refusal's named instructions invoke by path must exist), covered by unit_tests/commit_guardian/test_ge_127e_3_ii.py, which discovers paths from the file's text at run time rather than asserting one known-bad string is absent. KI-CG-20260908-file-size-refusal-advises-a-dead-command moves to RESOLVED; GE-127e-3 itself stays todo, its three other arms untouched."
commits:
  - e6979b62e
breaking: false
---

## Entry

### One hop too far to notice

The file-size gate went live on 2026-09-07 and has refused commits repo-wide since.
Every refusal carries exactly one actionable line: *use the `/code-refactoring-specialist`
slash command*. The command is real. It is deployed. Its first instruction was not — it
told the author to run `.agent/skills/code-analysis/scripts/analyze_structure.py`, and no
file of that name, nor the directory holding it, exists anywhere in the workspace.

The defect survived because the chain is one hop longer than a classic broken link. The
guard names a command; the command resolves; the command names a script; the script does
not exist. Any check that stopped at "does the slash command exist" reported healthy.

### Deleted, not replaced — and that is the correct fix

Step 1's tool invocation is gone. The command's remaining four steps — secure the
perimeter with characterization tests, plan, execute, clean up — are untouched and still
useful.

Two reasons deletion beats repair here. `GE-127e-3` makes a refusal that offers *nothing*
explicitly compliant, precisely so that removing a false promise is never blocked by a
requirement to promise something — a bare verdict beats advice that dead-ends. And
`GE-127e-1` already specifies a per-file description engine that produces exactly the
"deterministic map of the file" the dead instruction was reaching for; building a second
one now is the duplication `GE-127e`'s CR-100 and INF-800 fences exist to prevent.

### The test is the durable part

`GE-127e-3-ii` is a new L3 technical constraint under `GE-127e-3`: every tool named by an
instruction a refusal sends the author to must actually exist. Not a fifth L2 — `GE-127e`
had room, but the shape is a constraint on an already-specified behaviour, pinning *where*
"only help that actually arrives" reaches: one hop past the refusal's own text.

`unit_tests/commit_guardian/test_ge_127e_3_ii.py` **discovers** the invoked paths from the
command file's text at run time and resolves each against the repository. It never asserts
that this one known-bad string is absent — such a test would go green the instant the line
was deleted and be blind to the next dead pointer, which is the failure mode that produced
this record in the first place. A second descriptor injects a nonexistent path into a temp
copy and asserts the report names the command, the instruction and the path, so the first
cannot pass by extracting nothing.

Proven by mutation, all under `AC_ENFORCE_STRICT=1`: red baseline named the real
unresolved path, green after the fix, red again with the fix stashed, green on restore.

### What is still open

`KI-CG-20260908-file-size-refusal-advises-a-dead-command` moves to RESOLVED.
`GE-127e-3` does **not** — its three other arms (no future-tense promise, "already done"
claims checked against the run that produced the refusal, a bare verdict being compliant)
are untouched. One instance of a violation removed is not the criterion satisfied.

The same command's `@documentation-expert` branch for `.md` files is left alone
deliberately: `.md` is not in `file_size.checked_extensions`, so it is unreachable from
this gate — inert rather than broken, and an agent reference is not a tool invoked by path.
