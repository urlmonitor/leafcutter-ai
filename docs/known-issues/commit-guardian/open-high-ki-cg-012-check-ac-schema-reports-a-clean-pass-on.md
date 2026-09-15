---
title: "KI-CG-012 — `check-ac-schema` reports a clean pass on a file it never validated, because Phase 1 fails open on an empty staged set"
description: "KI-CG-012 — `check-ac-schema` reports a clean pass on a file it never validated, because Phase 1 fails open on an empty staged set"
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

# KI-CG-012 — `check-ac-schema` reports a clean pass on a file it never validated, because Phase 1 fails open on an empty staged set

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **ID COLLISION — this entry and the one at `KI-CG-012` above share a number.** Two sessions
> minted `KI-CG-012` independently on 2026-08-25; the other entry ("the hooks' test seams
> disagree on both variable name and separator") was itself renumbered from `KI-CG-008` at
> merge, which is how the collision arose. Deliberately **not** renumbered here, because the
> inbound references do not disambiguate cleanly and a wrong renumber is worse than a flagged
> duplicate:
>
> - `commit-guardian.md:953` and `build-pipeline.md:1095` cite `KI-CG-012` for an
>   "invisible until touched" property — fits neither entry unambiguously.
> - `BP-600d-3.yaml:186` cites it as "a third" occurrence of index-scoping — that reads as
>   *this* entry.
> - The 2026-08-25 10:26 changelog describes `KI-CG-012` as the `_is_leaf_ac()` / leaf-definition
>   disagreement, which is the text now filed as **`KI-CG-013`** — so at least one inbound
>   reference is already pointing at the wrong entry independently of this collision.
>
> Whoever owns this file should pick the renumber and fix all four references in one commit.
>
> **Citation audit, 2026-08-26 — still not renumbered, and the reason is now stronger.** A
> repo-wide sweep done while resolving a different collision in this register found the
> inbound set has grown from four to **nine**, and it splits across *both* entries:
>
> | Citation | Resolves to |
> |---|---|
> | `GE-126a-3.yaml:43`, `:63`, `:96`, `:128` · `GE-126a.yaml:26`, `:85` · `GE-126.yaml:209` | the **test seams** entry (above) |
> | `GE-126.yaml:160` ("re-run with a deliberately invalid file") · `build-pipeline.md:1234` | **this** entry |
> | `GE-126e.yaml:28` ("all the same family") · `BP-600d-3.yaml:186` | ambiguous |
>
> So a renumber is now a nine-site change spanning six acceptance-criteria records, two of
> which cannot be resolved from their text alone. That is a deliberate, owner-sized piece of
> work and not a drive-by fix — attempting it as a side effect of unrelated work is how the
> `016`/`017` collision below was created in the first place.
>
> **Do not allocate a sequential id at all. New entries use `KI-CG-<YYYYMMDD>-<slug>`.**
> This line previously read `018`, then `034`, then `035`; each was true when written and
> overtaken shortly after — `034` was consumed by the very PR that wrote the line claiming
> it was free, and `035` by a PR that landed while another author was mid-draft against it.
> That author's entry is now `KI-CG-20260831-hook-scripts-never-invoked`; it was written as
> `KI-CG-035` and renamed at merge, which is the fourth recorded collision on this counter.
>
> The advice that replaced the number — "read the file on a fresh `origin/main` immediately
> before you land" — does not work either, and it is worth being precise about why: the read
> and the land are not atomic. Any gap between them is a window, and a parallel session only
> has to land inside it. The date-and-slug form removes the window rather than narrowing it.
> See `build-pipeline.md` → "Why not the next free number" and `KI-BO-024`. Existing
> `KI-CG-NNN` ids stay as they are — renumbering would break inbound references.

- **Severity:** high
- **Status:** open
- **Occurrences:** 5
- **First seen:** 2026-08-25 · **Last seen:** 2026-09-07
- **Where:** `templates/scripts/commit_guardian/check_ac_schema.py` — `main()` (`root = Path(os.environ.get("HOOK_ROOT", str(Path.cwd())))`, `:673`), `_get_staged_ac_paths()` (`:307`, fail-open documented in its own docstring), the `if not staged_files:` branch (`:685`), and `_find_project_root()` (`:99`)

**Fourth occurrence, 2026-08-26 — and it came wearing a disguise worth knowing about.** A run
against 16 staged AC records in a worktree exited 0 while printing:

```text
WARNING: config/ac_store_schema.json not found at /home/henzeh/projects/leafcutter;
         falling back to manual field validation.
exit: 0
```

This was initially filed as a **separate** defect — a missing schema causing a downgrade to a
weaker check. That diagnosis is wrong and was withdrawn; see the retracted
`KI-CG-20260826-1334` at the end of this file for the A/B that disproves it (with the schema
*removed* the hook is **stricter**, catching an extra id-format error).

The WARNING is a red herring that appears at exactly the moment of the false pass. The actual
mechanism is this entry's: `_get_staged_ac_paths` shells `git diff --cached` with **no
`cwd=root`**, so the resolved root and the staged set can come from different repositories.
The root here — `/home/henzeh/projects/leafcutter` — holds a `CLAUDE.md` but no `.git`, so the
root resolution settled on the workspace directory, the staged set came back empty, and
Phase 1 was skipped.

**Why this occurrence is the most valuable of the four:** it is the first with a demonstrated
cost. The 16 staged records included two that `validate_declares_side_effect` errors on when
called directly (`KI-CG-014`). The hook passed them; CI, which builds fresh, would have failed
the required `AC store valid` check. So this is not "the hook checked nothing" in the abstract
— it is the hook returning a green that was **wrong about the specific change in front of it**,
on a change that would have gone red in CI minutes later.

**Symptom.** The hook exits 0 having validated nothing, and its output is indistinguishable
from a run that validated everything and found it clean. There is no "checked 0 files"
line: a skipped Phase 1 and a passing Phase 1 look identical.

**Evidence — two independent observations on the same day.**

*Deliberate mutation.* `declares_side_effect: true` was removed from a staged
`BP-600b-3.yaml` whose criteria assert a durable effect — precisely the condition
`validate_declares_side_effect` exists to catch. Both the direct invocation and
`pre-commit run check-ac-schema` reported **Passed**. CI, on that same commit, failed the
required `AC store valid` check and named both the file and the rule. The local exit code
carried no information; only CI evaluated the record.

*Wrong-root run.* A separate agent, running the deployed hook against AC files in a
worktree, saw it print `WARNING: config/ac_store_schema.json not found at
/home/henzeh/projects/leafcutter; falling back to manual field validation` and exit 0. It
had resolved the project root to the **workspace parent** — the untracked directory above
the repository, which has no `config/` tree.

**Root cause, as far as the source states it.** Three mechanisms each independently make a
clean exit reachable without any file being checked:

1. `main()` derives its root from **CWD**: `root = Path(os.environ.get("HOOK_ROOT",
   str(Path.cwd())))`. Nothing constrains CWD to the repository whose index is being
   committed.
2. `_get_staged_ac_paths(root)` shells out to `git diff --cached` under that root, and its
   own docstring states it "returns an empty list when `HOOK_NO_GIT` is set or git is
   unavailable (**fail-open**)". `main()` then takes `if not staged_files:` and skips
   Phase 1 entirely. A wrong root and an absent git both land here.
3. `_find_project_root()` — used by Phase 2, **not** by `main()` — walks ancestors
   accepting `.git` **or `CLAUDE.md`**. The workspace parent has a `CLAUDE.md`, so that
   search can terminate at a directory that is not a repository. Two different root
   strategies in one file, and they disagree.

The schema fallback is **not** the whole story. `validate_declares_side_effect` is called
unconditionally at `:625`, independent of whether the schema loaded, so a missing schema
alone would still have caught the mutation. What silences the hook is Phase 1 not running.

**Fifth occurrence, 2026-09-07.** Invoking the deployed hook via `run_hook.py`
(`templates/scripts/commit_guardian/run_hook.py`, deployed to
`.leafcutter/scripts/commit_guardian/run_hook.py`) with cwd resolving to a directory
**outside** the worktree printed the identical WARNING seen in the fourth occurrence —
`WARNING: config/ac_store_schema.json not found at /home/henzeh/projects/leafcutter; falling
back to manual field validation` — and exited 0. Running the same invocation with cwd
**inside** the worktree, against the same staged files, validated properly. This reproduces
exactly the "wrong-root run" mechanism already described above in this same entry (mechanism
1 in "Root cause, as far as the source states it": `main()`'s CWD-derived root at `:673`) — a
fifth independent confirmation of the same failure mode, now via `run_hook.py` specifically
rather than a direct invocation of `check_ac_schema.py` or `pre-commit run check-ac-schema`.

**Honest limit of this report.** The `pre-commit run` invocation was not isolated to a
single mechanism — cwd was inside the worktree for that run, so (1) and (2) do not
obviously explain it, and the exact path taken was not pinned down. The three code facts
above are directly readable and each permits a silent pass; which one fired in that
specific invocation is still open. Do not close this on the strength of fixing only the
one that looks most likely.

**Third occurrence, 2026-08-25 — mechanism (2) isolated, and `HOOK_TEST_FILES` does not
rescue it.** CI's required `AC store valid` refused `BO-1500a-1.yaml` for a missing
`declares_side_effect`. Reproducing locally from inside the worktree, with the correct
root, the hook exited 0 three ways:

1. `HOOK_TEST_FILES` set to the 46 changed records — exit 0.
2. `HOOK_TEST_FILES` set to the single offending record, **before** the fix — exit 0.
3. The fix applied and staged — exit 0.

Run 2 is the control, and it is the informative one: the hook passed a record that CI
refused by name, on a rule that record genuinely violated. The common factor is that
`BO-1500a-1.yaml` was already at `HEAD` unmodified, so `git diff --cached` was empty and
`main()` took the `if not staged_files:` branch — **regardless of `HOOK_TEST_FILES`**.
Whatever that variable is honoured by, it is not the gate that decides whether Phase 1
runs, so it cannot be used to point the hook at a file for verification. The docstring's
fail-open note (mechanism 2) is therefore reachable with a correct root and a working
git, not only with a wrong root or an absent one.

This also explains why CI sees what local runs cannot: the `ac-store-valid` job does
`git reset --soft origin/main` before invoking the hooks, which stages the branch's entire
diff. Locally, only files differing from `HEAD` are ever examined — so a defect already
committed is structurally invisible to the local gate, and no amount of re-running it
proves anything about those records.

Add to the fix direction: whatever `HOOK_TEST_FILES` is for, it must either drive the
Phase 1 file set or be removed. A test seam that silently does nothing is how a
verification step becomes theatre.

**Fix direction.** Make "checked nothing" impossible to confuse with "checked and passed":

- **Never exit 0 on an empty file set.** If the hook was invoked and resolved zero files,
  say so on stderr and exit non-zero, or at minimum print the count. `KI-ACS-001` fixed
  exactly this shape in `validate_ac_schema.py` on 2026-08-19 — a bare directory printed
  `No YAML files to validate.` and exited 0 — and the same reasoning applies here.
- **Resolve the root once**, from `git rev-parse --show-toplevel`, and thread it to every
  consumer. Drop the CWD default and the `CLAUDE.md` ancestor heuristic: a `CLAUDE.md`
  marks a *workspace*, not a repository.
- **Do not fail open when git is unavailable.** A gate that cannot determine what is being
  committed has not passed; it has failed to run.

**Relationship to existing entries.** Same family as **KI-CG-009**
(`check-components-integrity` resolving the root to the main checkout rather than the
worktree) and **KI-CG-002** (a silent fallback to a second enum authority when a declaring
file is unreachable). It shares **KI-CG-001**'s index-scoping premise but is a distinct
failure: there the hook checks the wrong *set*; here it checks the *empty* set and says
nothing. Four entries now describe the same root-resolution surface, which argues for one
piece of work across the hook family rather than one hook at a time.

**Pattern:** a gate whose silence is structurally indistinguishable from a pass.

---
