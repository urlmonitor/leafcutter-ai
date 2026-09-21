---
title: "KI-BO-20260831-1330 — The fast lane invokes `assemble-bundle` with two flags that were deliberately deleted, so its context-bundle gate can never be satisfied"
description: "KI-BO-20260831-1330 — The fast lane invokes `assemble-bundle` with two flags that were deliberately deleted, so its context-bundle gate can never be satisfied"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260831-1330 — The fast lane invokes `assemble-bundle` with two flags that were deliberately deleted, so its context-bundle gate can never be satisfied

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** **RESOLVED 2026-09-01** — the two flags are gone from the lane. Verified:
  `grep -c "conventions\|--acs" templates/workflows-js/fast-lane-ship.js` returns **0**, and a
  live run reached its coder phase with a 20,645-byte bundle. Fixed as part of the `BO-2400c-1-vi`
  bundle shrink (the layer set was reduced, which removed the two invocations along with the
  layers they passed), so it was closed incidentally rather than deliberately — which is why it
  sat here reading `blocker / open` after it had stopped being true.
  **Left as a warning:** a stale blocker is not harmless. This entry was the top of the severity
  list when the register was consulted on 2026-09-01 to decide what to build next, and it
  displaced two real ones. Re-verify a blocker before planning against it.
- **Occurrences:** 1
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `templates/workflows-js/fast-lane-ship.js`, the `context-bundle` phase's Step 2
  invocation; `injection_builders.py` `assemble-bundle` argparse surface

**Symptom.** `/fast-lane-build INF-700b-2` halts:

```
status: blocked
failing_phase: context-bundle
context_bundle_state: incomplete
"The context bundle was obtained but is incomplete: the cache breakpoint marker
 is absent, or one of its layers is empty."
```

`obtained: true`, `bytes: 10287`. The content came back — this is **not** the pointer-instead-of-content
failure in `KI-BO-20260826-1214`. The bundle is genuinely incomplete.

**Cause.** The workflow's Step 2 tells the phase agent to invoke `assemble-bundle` with
`--conventions` and `--acs`. Those flags **do not exist**. `BO-2400c-1-vi` removed them
deliberately — not made optional, *removed* — so a caller cannot reintroduce the two largest
duplicate layers the design retired (`conventions` duplicates the harness-injected
`CLAUDE.md`; `acs` duplicates AC records the receiving agent can read from its own
workspace). Passing either makes argparse reject the whole command.

The agent did the sensible thing: ran with the three flags that do exist
(`--architecture`, `--high-level`, `--prior-tests`) and folded a pointer to the AC store into
the `high_level` layer. The bundle assembled, exit 0, no stderr — and then failed the
completeness check, because the layer set no longer matches what the workflow validates.

**So the two halves of one feature disagree about their own interface.** `BO-2400c-1-vi`
narrowed the CLI; nothing updated the caller or the completeness contract it validates
against. Every fast-lane run for a `python-coder` AC hits this.

**Why it reads as something else.** The message says "incomplete", which invites you to
look at the layers' *content* — whether a doc was too big, whether a file was missing. The
actual fault is one directory away, in an argparse surface the workflow has no test against.
The phase agent's own report is what surfaced it, in prose, as an aside.

**Fix direction.** Reconcile the caller with the CLI, in one change, and add the test that
would have caught it: assert the workflow's invocation string only names flags
`assemble-bundle` actually accepts. Then decide whether the completeness contract should
still demand the two retired layers — it should not, and that is the substantive half.
A shared constant for the layer set, read by both the builder and the validator, removes
the class rather than this instance.

**Related.** `KI-BO-20260826-1214` (same phase, same halt, different cause: content returned
as a pointer rather than inlined — that one is about the size of the payload, this one about
the shape of the command). Both make the lane unable to ship; fixing either alone is not
enough.

---
