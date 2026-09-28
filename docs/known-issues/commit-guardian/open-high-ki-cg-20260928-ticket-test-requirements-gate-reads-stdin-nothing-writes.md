---
title: "KI-CG-20260928-ticket-test-requirements-gate-reads-stdin-nothing-writes — check-ticket-test-requirements takes its file list from stdin, the manifest sets pass_filenames:false, and run_hook pipes no stdin, so the gate reads an empty list and exits 0 on every commit"
description: "high — the gate that exists to stop a code ticket shipping without test requirements has never inspected a ticket. It is registered, it runs, it prints nothing, and it exits 0. Silent success is indistinguishable from a clean pass, which is the exact failure GE-120 exists to eliminate, occurring inside the guardrail family itself."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - commit_guardian
  - precommit_hooks
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260928-folder-density-blocking-branch-unreachable.md
---

# KI-CG-20260928-ticket-test-requirements-gate-reads-stdin-nothing-writes — the gate reads its file list from stdin, and nothing ever writes to it

- **Severity:** high. A registered `pre-commit` judgment-tier gate has never inspected a single
  ticket. It does not crash, does not warn, and does not skip loudly — it exits 0 in silence.
- **Status:** open — no AC.
- **Occurrences:** 1 (found by the `GE-120b-2-i` provoking-fixture sweep, 2026-09-28).
- **First seen:** 2026-09-28 · **Last seen:** 2026-09-28
- **Where:** `templates/scripts/commit_guardian/check_ticket_test_requirements.py:152`,
  against its own manifest entry in `templates/scripts/commit_guardian/commit_guardian.json`
  and the delegation call at `templates/scripts/commit_guardian/run_hook.py:409`.

## Mechanism — three pieces, each defensible alone

1. **The script falls back to stdin.** `main(ticket_files=None)` treats `None` as "read one path
   per line from stdin" (`:152`, `sys.stdin.readlines()`). Its own docstring calls that "the
   standard pre-commit hook calling convention".
2. **The manifest guarantees `ticket_files` is `None`.** The entry sets
   `"pass_filenames": false`, so no paths ever reach `argv`.
3. **Nothing pipes stdin.** `run_hook.py:409` is `subprocess.run(cmd, env=env)` — no `input=`,
   no `stdin=`. The child inherits the parent's stdin, which in a hook context is not a list of
   ticket paths.

So `ticket_files` resolves to `[]`, the loop body never executes, and the function returns 0.
Each piece is a reasonable local decision; the defect exists only in their composition, which is
why code review of any single file would pass it.

## Evidence — executed, not reasoned

Run the deployed copy the way the manifest runs it, with no stdin:

```
python scripts/commit_guardian/check_ticket_test_requirements.py < /dev/null
```

Result: **exit 0, and zero bytes on stdout and stderr.**

That output is byte-identical to a run that inspected twenty tickets and found every one
compliant. There is no signal anywhere distinguishing the two.

Independently, the `GE-120b-2-i` fixture staged a new ticket in exactly the shape this gate
exists to refuse — `agents:` naming `python-coder: needed`, `change_target: code`, and no
`## Test Requirements` section at all — and the gate reported **clean**.

## Why this matters more than one hook

`test-writer` is skipped when a ticket has no `## Test Requirements` block, and no authoring
surface has emitted that block since v2.0.0 (see the `test_requirements_missing_testwriter_skip`
note). This gate is the mechanical backstop for precisely that gap — and it has never fired. A
ticket can reach `done` with no tests, no test-writer phase, and a clean commit-time gate
reporting nothing wrong.

It is also the `GE-120` thesis in its purest observed form: **a check that could not look is
reporting the same thing as a check that looked and found nothing.** Here it is not even
could-not-look — it is was-never-given-anything-to-look-at, which produces the same green.

## Fix direction

1. **Stop using stdin.** Either set `pass_filenames: true` on the manifest entry and read `argv`,
   or have the script derive the staged ticket set itself from the index the way its sibling
   `check-ticket-ac-status-parity` does. The second is preferable: it removes the dependency on
   the caller's calling convention entirely.
2. **Make an empty input set loud, whichever route is chosen.** `files` on the entry is
   `^tickets/.*\.md$`, so the hook only runs when a ticket is staged — meaning an empty list is
   by construction a contradiction, not a quiet no-op. It should report that it was handed
   nothing and fail, per `check_outcome`'s could-not-check vocabulary (`GE-120a-1`). An empty
   required set is not a satisfied one.
3. **Add a negative control.** The gate needs a fixture ticket it must refuse, exercised in CI,
   or the next regression is equally invisible. `GE-120b-2-i`'s provoking fixture now stages such
   a ticket and can serve as the starting point.

## Related

`KI-CG-20260928-folder-density-blocking-branch-unreachable` — same family, same shape: a
registered gate whose blocking path cannot be reached. `KI-CG-20260928-mermaid-parent-link-dead-in-deployed-layout`
— a third, by a different mechanism (root resolution rather than input plumbing).

**Pattern:** a check whose input arrives by a channel its caller does not populate — so it runs,
inspects an empty set, and reports the same success as a check that inspected everything.
