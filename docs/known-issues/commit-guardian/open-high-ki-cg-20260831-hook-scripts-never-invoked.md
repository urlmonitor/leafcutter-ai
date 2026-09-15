---
title: "KI-CG-20260831-hook-scripts-never-invoked — 24 hook scripts are named by no `entry:` line, and the guard that exists to find unreachable hooks iterates only the registered ones"
description: "KI-CG-20260831-hook-scripts-never-invoked — 24 hook scripts are named by no `entry:` line, and the guard that exists to find unreachable hooks iterates only the registered ones"
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

# KI-CG-20260831-hook-scripts-never-invoked — 24 hook scripts are named by no `entry:` line, and the guard that exists to find unreachable hooks iterates only the registered ones

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> Authored first as `KI-CG-035` — the next free sequential number — and renamed on merge
> after hitting the very problem the date-and-slug convention exists to prevent. Picking
> "the next free number" requires reading the file and appending before anyone else does;
> this entry collided with two concurrent additions in one afternoon. See
> `build-pipeline.md` → "Why not the next free number" and `KI-BO-024`.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `.pre-commit-config.yaml` (built from `templates/pre-commit-config.yaml`) — the
  set of `entry:` lines; `templates/scripts/commit_guardian/check_*.py` — the set of scripts;
  `templates/scripts/commit_guardian/check_hook_trigger_reachability.py` and its
  `hook_trigger_reachability_exemption_registry`; `templates/scripts/commit_guardian/README.md`
  — documents `check-ticket-signoff-parity` as a live hook id

**Symptom.** `check_ticket_signoff_parity.py` exists, is deployed, is documented in the
commit-guardian README as hook id `check-ticket-signoff-parity` with *"current config uses
`--enforce`"*, and **never runs**. It is not registered in `.pre-commit-config.yaml`, and it
is not exempted. It is simply absent from the only surface that would invoke it.

It is not alone:

```
registered hook ids in .pre-commit-config.yaml     54
check_*.py in templates/scripts/commit_guardian/   66
scripts named by NO entry: line                    24
```

`grep -c signoff .pre-commit-config.yaml` → `0`.

**Method, and the control that makes it trustworthy.** Comparing script *names* to hook *ids*
over-reports: `check_ac_limits.py` is registered but runs under the id
`check-ac-tree-limits`, so a kebab-case name match calls it unregistered when it is not. The
count above is therefore taken from `entry:` lines — the path pre-commit actually executes —
not from ids. The control: `check_done_proof.py` and `check_ac_limits.py` both appear on
`entry:` lines and were observed running in a live commit; `check_ticket_signoff_parity.py`,
`check_ticket_test_requirements.py` and `check_test_ac_tags.py` appear on none and were
observed not running.

**Not an alternative-dispatcher artefact.** `run_hook.py` takes the target script as an
argument and dispatches nothing on its own — its only mention of `check_docstrings` is inside
a docstring. Nothing in `.github/` invokes the two probed scripts either. So "no `entry:`
line" means "never runs", not "runs by another route".

**Cause — why the guard cannot see this.** `check_hook_parity` compares the four *directory*
copies of the hook tree (runtime, canonical template, legacy template, deployed output); it
answers "is this file present everywhere it should be", not "is this file ever invoked".
`check_hook_trigger_reachability` does ask a reachability question, but it iterates the
**registered** hooks and asks whether each one's triggers can fire. An unregistered script is
not in the set it walks. So the one guard built to find hooks that cannot fire is structurally
blind to the hook that was never wired up at all — the gap is in the enumeration, not the
predicate. Consistently, `check-ticket-signoff-parity` is *not* in the nine-entry
`hook_trigger_reachability_exemption_registry`: nobody exempted it, because nothing looked.

**Why high.** Three compounding reasons.

1. **A documented hook that does not run is worse than an absent one.** The README states it
   is live and configured with `--enforce`. Anyone reasoning about sign-off integrity —
   human or agent — will conclude the parity check is covered.
2. **It is load-bearing for scheduled work.** `BP-1100g-5-i` pins its entire mechanical
   reader onto `_signoff_parity_checks.py` "reached via `check_ticket_signoff_parity.py`",
   and its `doc_links` call that "the registered hook entry point". That is false today.
   Building it as specified would produce a reader reachable from nothing — the exact failure
   its own `it_requirements` warn about: *"A reader that is not reachable from a registered
   hook is inert."* Four `TQ-500` acceptance criteria now depend on the same host.
3. **The 24 are unaudited.** Only three were probed individually. The other 21 may include
   scripts that are deliberately library-only, superseded, or CI-invoked — but each is
   currently indistinguishable from a guard everyone believes is running. Until triaged, the
   commit-guardian surface's real coverage is unknown, and it is smaller than 66.

**Remediation.** Register `check-ticket-signoff-parity` (restoring the documented id rather
than minting a new one — `commit_guardian.json` is a package-surface registry, so a *new* id
trips `check-package-surface-declaration` and requires the structured five-field spec). Then
triage the remaining 23: register, delete, or add to the exemption registry with a stated
ground. Finally, close the enumeration gap — the reachability guard should walk the scripts on
disk and report any that no `entry:` names, rather than walking the registry and trusting it
to be complete.

**How it was found.** An `it-po` agent enriching the `TQ-500` tree checked whether the host
its ACs pin was actually registered, instead of accepting the README's claim that it was. The
brief it was given asserted the hook was registered; it was the brief that was wrong.

**Related.** `KI-CG-034`, `KI-CG-019`, `KI-CG-012` (sibling exit-0-having-checked-nothing
routes). `BP-1100g-5-i` and `TQ-500b-1` / `TQ-500c-2` / `TQ-500c-3` / `TQ-500e-2` (the
scheduled work that depends on this host).

**Pattern:** a completeness guard whose input is the registry it is meant to be checking —
so anything missing from the registry is invisible to the check for missing things.

> **Second observation, 2026-08-31 — independent, and it executes three of the 24.** Found again
> while auditing the hook fleet during the GE-120 drive, from the other registry surface: the
> `hooks_manifest` in `templates/scripts/commit_guardian/commit_guardian.json` (57 entries, 5
> `enabled: false`, 52 deployed ids) names 20 of the `check_*.py` on disk not at all. The count
> differs from the 24 above because the surfaces differ — `.pre-commit-config.yaml` `entry:`
> lines there, `hooks_manifest` here — and both are entry-path comparisons, not name matches.
> Treat 24 as the figure; this is corroboration, not a competing measurement.
>
> Three of the orphans were run directly, which the entry above did not do:
>
> - `check_ac_coverage.py` — **exit 0** after printing **178** `WARNING: AC <id> has no test
>   coverage` lines. It reads the whole AC store to produce findings nobody receives.
> - `check_doc_coverage.py` — **exit 1, unhandled traceback.** It is broken, and because nothing
>   invokes it, nothing has noticed.
> - `check_ticket_test_requirements.py` — **hung past a 45-second timeout** with two files staged.
>
> **The config-block trap, which the remediation above should cover.** Ten of the orphans carry
> live-looking blocks in `commit_guardian.json` — `file_size`, `complexity`, `sql_complexity`,
> `docstrings`, `documentation`, `root_files`, `folder_density`, `debug_scripts`, `doc_coverage`,
> `doc_links` — with thresholds and `enabled` flags. To anyone tuning a threshold there they read
> as active gates; changing one has no effect and produces no signal saying so. When triaging the
> 24, delete the config block of anything retired in the same change.
>
> **And a fifth registration leg.** `templates/scripts/precommit-autofix.json` carries autofix
> routing for `check_ticket_signoff_parity` — remediation wired to a gate that cannot fire. That
> is one beyond `KI-CG-020`'s fourth leg. `KI-CG-024`, which describes this same hook as live and
> skipping only check #6, is corrected in place above.

---
