---
title: "Why the BO-4100d-4 cwd regression escaped a suite that was run and reported green"
description: "Two independent misses let a cwd-dependent resolver change reach CI unseen: a test subset chosen for a reason that did not hold, and a verification run whose own working directory made the regression unobservable. Neither alone explains the escape. Places the incident in the repository's documented family of checks that examined nothing and reported clean, and evaluates candidate guards — including the one CLAUDE.md instruction whose recipe prescribes the fatal cwd."
type: explanation
status: active
created: 2026-09-28
last_updated: 2026-09-28
components:
  - build_orchestration
  - testing_quality
related_docs:
  - docs/analysis/2026-09-28-why-the-cwd-regression-escaped-verification-1-what-actually-happened-in-two-separable-parts.md
  - docs/analysis/2026-09-28-why-the-cwd-regression-escaped-verification-3-the-guard.md
  - docs/analysis/2026-09-28-why-the-cwd-regression-escaped-verification-4-blast-radius.md
---

# Why the BO-4100d-4 cwd regression escaped a suite that was run and reported green

AC BO-4100d-4 (PR #866, unmerged, commit `1dc5adfd`) changed `_git_toplevel()` in
`scripts/setup_ticket_worktree.py:139-183` and its template twin
`templates/scripts/setup_ticket_worktree.py:137-181`. Resolution order went from
*explicit anchor → the script's own directory* to *explicit anchor → `Path.cwd()` →
the script's own directory*. Fourteen tests in
`unit_tests/build_orchestration/test_bo2400f_13*.py` fail in CI as a result.

This page is not about what the resolution order should be — that contract is being
designed separately. It is about the verification: a suite was run, by a careful
operator, and reported green, over a change that CI rejects.

**The answer is not "insufficient testing."** Two independent things went wrong, and
the incident needs both. Removing either one leaves the regression undetected. A third
and a fourth fact, found while verifying the first two, make the account worse rather
than better: the exact hazard was written down in the file family that broke, and this
repository's own testing instruction prescribes the working directory that hid it.

## 1. What actually happened, in two separable parts

> See [2026-09-28-why-the-cwd-regression-escaped-verification-1-what-actually-happened-in-two-separable-parts.md](2026-09-28-why-the-cwd-regression-escaped-verification-1-what-actually-happened-in-two-separable-parts.md) for full details.

## 2. Where this sits in the documented family

This repository already catalogues, in `CLAUDE.md`, three checks that examined nothing
and reported clean, and one mirror-image family that reported failure for the same
reason. The relevant question is whether this is a fourth instance or something new.

| Incident | Mechanism | Direction |
|---|---|---|
| Stale-ref merge audit (`CLAUDE.md:681-686`, `:733-744`) | Diff run against an unfetched `origin/main`; the broken tree and the stale ref agreed | Clean-looking pass over a real defect |
| AC-store bare-directory glob (`CLAUDE.md:836-841`) | Directory argument matched zero files, printed `No YAML files to validate`, exited 0 for eight days | Clean-looking pass over zero inspection |
| `feedback_categories.yaml` wrong path (`CLAUDE.md:745-747`) | Reported "missing" on every worktree | Clean-looking pass |
| **Mirror image** — `verify_precommit_active.py` `git_hook:false`; `check_identifier_uniqueness` / `validate_ac_schema` `FAILED (0 inspected)` (`CLAUDE.md:756-768`, KI-CG-20260901) | Guard invoked from outside the worktree root; "could not look" collapsed to "false" | Failure-looking result from a tool that examined nothing |
| KI-BO-20260921 worktree-base resolver (`docs/known-issues/build-orchestration/open-high-ki-bo-20260921-worktree-base-resolver-defaults-to-cwd.md`) | `worktree_repo_facts.py base` called with no start path; positional default `"."`; workspace parent is not a repo | Loud abort, layout-conditional |
| **This incident** | Test *subject* resolves through cwd; verification run inherited a cwd where the new code path is unreachable | Clean-looking pass over a real defect |

**It is the same pattern, one level up.** The four `CLAUDE.md` entries are all about a
*check* whose scope was empty or whose reference was stale. Here the check — the test
— was correct, complete, and genuinely executed against the real code. What was empty
was the *code path*: the new branch the change introduced was unreachable from the
verification environment. The generalisation that covers all five is the one
`CLAUDE.md:749-753` already states and then under-applies:

> "A check that examined nothing must not look like a check that found nothing."

Extended: *a check that could not reach the changed code must not look like a check
that found the changed code correct.* Coverage tooling exists for exactly this
question, and nothing in this pipeline asks it.

**Relationship to KI-BO-20260921 is closer than family resemblance — it is the same
defect with the sign flipped.** That known issue is about a resolver defaulting to cwd
and *failing* because the dev-layout cwd is not a repository. BO-4100d-4 adds a cwd
candidate that *succeeds* because the CI cwd is a repository. KI-BO-20260921's own "Why
it was not caught" section names the shape precisely:

> "a default that is correct in one layout and silently wrong in another, where the
> wrong answer is indistinguishable from a legitimate 'not applicable'."

And its "Fix direction" already proposed the remedy that would have prevented this one:

> "`start` defaulting to `"."` is the thing that let a missing argument look like a
> working call. A required argument, or a default of the repository root rather than
> the process cwd, would have made this a loud failure at the call site."

That recommendation was filed on 2026-09-21 against `build_orchestration`. BO-4100d-4
landed on 2026-09-22, in `build_orchestration`, and added a cwd default to a resolver.
The register entry existed, named the pattern, and proposed the opposite of what was
built, one day apart. Registers that nothing reads are not guards.

**On the irony — it is substantive, not decorative.** The same repository that ships
`verify_precommit_active.py`, whose documented defect is that it mis-reports *because
it was run from the wrong directory* (KI-CG-20260901, whose reproduction command is
literally `env --chdir=/home/henzeh/projects/leafcutter …` — the very cwd at issue
here), shipped a resolver whose behaviour is decided by the directory it is run from.
It is substantive because it shows the knowledge is present and un-transferable in its
current form: written up in a known-issue file, filed under `commit_guardian`, invisible
to someone editing `build_orchestration`. Prose in a component-scoped register does not
protect a sibling component. Only an executable check crosses that boundary.

The counter-example in the same tree proves the knowledge *can* be encoded. Look at
`templates/scripts/commit_guardian/_ac_store_locator.py:30-53`: an ordered candidate
list that puts the file's own location first and explicitly refuses cwd —

> "…never `Path.cwd()`, which inside a pre-commit hook subprocess — or a unit test that
> `git init`s a scratch directory as its working directory … names an unrelated
> repository."

That is the correct pattern, written by someone who had met this hazard, in a resolver
that does strictly less damage than the one that broke.

## 3. The guard

> See [2026-09-28-why-the-cwd-regression-escaped-verification-3-the-guard.md](2026-09-28-why-the-cwd-regression-escaped-verification-3-the-guard.md) for full details.

## 4. Blast radius

> See [2026-09-28-why-the-cwd-regression-escaped-verification-4-blast-radius.md](2026-09-28-why-the-cwd-regression-escaped-verification-4-blast-radius.md) for full details.

## 5. Recommendations, by value for effort

**Do now:**

1. **G1 — repair the `CLAUDE.md:657-658` recipe** to `env --chdir=<worktree-root> python
   -m pytest unit_tests/ -q`. Surface: `CLAUDE.md`. One line; closes the instruction
   whose own command contradicts its own prose; fourth documented instance of a defence
   in this file that is a no-op.
2. **G3 — pass `cwd=` in `_bo2400f13_fixtures.py:129-143`.** Surface: test. One keyword
   argument; makes the family's isolation independent of the resolution contract and
   stops the suite from mutating the real repository. Do this *before* G2.
3. **G4 — add a cwd-invariance test** for `_git_toplevel`, reusing the relocated-copy
   harness already in `test_bo_4100d_4.py`. Surface: test. This is the deliberate
   detector that replaces the accidental one G3 removes. Do not land G3 without it.
4. **G2 — add a root `conftest.py` pinning cwd to `config.rootpath`.** Surface:
   conftest. Makes local and CI cwd identical by construction. Sequence after G3 so the
   first pinned run does not create worktrees in the developer's repo.

**Follow-ups:**

5. **G5 — a hook flagging `git rev-parse` without `-C`/`cwd=`, plus `Path.cwd()` /
   `os.getcwd()`, in resolution code.** Surface: pre-commit hook. Real value, but only
   if keyed on the call shape; a `Path.cwd()`-only rule is theatre over the ~25-site
   invisible surface. Pair with an AC `it_requirement` — *a resolver AC must assert
   invariance under cwd, not merely vary it* — on resolver ACs; that half cannot be
   mechanised.
6. **G7 — one short `CLAUDE.md` entry**: cwd is never a resolution candidate in code
   that mutates a repository; anchor on the subject or refuse. Surface: `CLAUDE.md`.
   Weak as prose, but it is the only surface every agent loads, and the knowledge
   currently sits in two component-scoped known-issue files that reached nobody.
7. **Process, not tooling — retire "another PR already covered that directory" as a
   reason to skip tests.** A green run on a branch without the change is evidence about
   the directory, not the change. Surface: `CLAUDE.md` or the phase-agent prompt. Note
   this is the miss with *zero* causal weight here; it is worth fixing on its own
   merits, not as this incident's lesson.
8. **G6 — a local runner mirroring CI** (build step, `AC_ENFORCE_STRICT=1`, cwd).
   Surface: CI config plus a script. Largely superseded by G1+G2 for this class.

**Deliberately not recommended:** randomising cwd in conftest. It would surface the
pre-existing cwd-dependent hook surface as flakiness unrelated to any change under test,
and non-reproducible failures are a worse guard than a pinned cwd plus one explicit
invariance assertion.

## 6. Two facts for whoever designs the resolution contract

Out of scope here, but established while verifying the above and worth handing over:

1. After BO-4100d-4, `cmd_create_only` resolves by opposite rules in the two copies —
   cwd-first in `scripts/setup_ticket_worktree.py:1801`, script-directory-authoritative
   via `_resolve_repository_with_search_fallback()` in
   `templates/scripts/setup_ticket_worktree.py:1843`. Whatever contract is chosen has to
   say which copy is right.
2. The new cwd candidate pre-empts ACD-2100a-2's bounded search fallback entirely:
   whenever cwd is inside any repository, `_git_toplevel` returns before the search can
   run. A separately-ACed resolver was disabled by a change that never mentioned it.

---

*Evidence for every claim above was read or executed in
`/home/henzeh/projects/leafcutter/worktrees/worktree-git-toplevel-anchor` on 2026-09-28,
on branch `feature/worktree-git-toplevel-anchor`. The two pytest runs in §1 were
executed; the seven worktrees and branches they created in the real repository were
removed and the tree verified clean. Where this page infers rather than observes — CI's
working directory, and the operator's reasoning at the time — it says so.*
