---
title: "KI-CG-20260826-1334 — RETRACTED: \"a missing schema makes `check-ac-schema` fail open\" — tested and disproved; the real cause is the `KI-CG-012` at line 800"
description: "KI-CG-20260826-1334 — RETRACTED: \"a missing schema makes `check-ac-schema` fail open\" — tested and disproved; the real cause is the `KI-CG-012` at line 800"
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

# KI-CG-20260826-1334 — RETRACTED: "a missing schema makes `check-ac-schema` fail open" — tested and disproved; the real cause is the `KI-CG-012` at line 800

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

> **Timestamped id** — `KI-<COMPONENT>-<YYYYMMDD>-<HHMM>`, minted at authoring time. Authored
> as `KI-CG-016`, renumbered to `KI-CG-021` when 016 was taken mid-review, then 021 was taken
> too. Sequential numbering has been abandoned for new entries in this register; see the
> convention note on `KI-BP-20260826-1331` in `build-pipeline.md`.
>
> This register is the worst affected: `KI-CG-012`, `KI-CG-016` and `KI-CG-017` each currently
> resolve to **two unrelated defects** on `main`. Those are not renumbered here — they are
> cited elsewhere and picking a winner is the owner's call — but they are the reason a
> retracted entry landing on a live id would have been actively harmful. Before this change,
> `KI-CG-021` on `main` is an open defect ("the whole-collection uniqueness pass is registered
> in no hook config and has never run"); merging a **RETRACTED** entry onto that number would
> have told every reader the real defect had been withdrawn.

- **Severity:** n/a — retracted before merge
- **Status:** **closed — hypothesis disproved by experiment.** Kept as a record so the same
  wrong diagnosis is not filed again; the observation that prompted it is real and is logged
  as an occurrence on `KI-CG-012` (line 800).
- **First seen:** 2026-08-25 · **Retracted:** 2026-08-26

**What was originally claimed.** That `check-ac-schema`, unable to locate
`config/ac_store_schema.json`, printed a WARNING, silently downgraded to "manual field
validation", and exited 0 — a weaker check reporting as a passing one (M5).

**Why it is wrong.** A controlled A/B with `ACS-1100b-2` staged, run by an independent
reviewer:

```text
schema present  -> exit 1, catches the declares_side_effect error
schema REMOVED  -> exit 1, catches that error PLUS an id-format error
```

**The degraded mode is stricter, not weaker.** It cannot be the cause of a false pass, and the
central claim of the retracted entry is the opposite of the measured behaviour.

Two supporting claims were also wrong. The **Where** field cited root resolution via
`_resolve_root.py`; `check_ac_schema.py` never imports that module. And the fallback
explanation offered — that stale deployed validators were missing `declares_side_effect` —
cannot produce this outcome either, because the import of `validate_declares_side_effect` is
unguarded and a missing symbol would raise `ImportError` rather than skip a rule.

**The real mechanism, already filed.** `_get_staged_ac_paths` shells out `git diff --cached`
with **no `cwd=root`**, so the resolved root and the staged set can come from different
repositories. The root in the observed run, `/home/henzeh/projects/leafcutter`, contains a
`CLAUDE.md` but no `.git` — so the staged set came back empty, Phase 1 was skipped, and the
hook exited 0 having examined nothing. That is exactly `KI-CG-012` at line 800 ("reports a
clean pass on a file it never validated, because Phase 1 fails open on an empty staged set"),
and the sighting is recorded there.

**Worth keeping rather than deleting.** The WARNING line is a genuine red herring: it appears
at the moment of the false pass, names a real missing file, and points at the wrong cause. The
next person to see it will reach for the same explanation. The A/B above is the two-minute
experiment that rules it out.

**How this got filed wrong.** The WARNING and the `exit: 0` were observed in the same output
and a causal link between them was assumed rather than tested — while the actual discriminating
experiment (remove the schema, re-run) takes about a minute. The entry then asserted a `Where`
field naming a module the script does not import, which a single `grep` would have caught. It
is the same failure mode this register documents: a plausible mechanism, written up with real
evidence attached to it, where the evidence supports the *observation* and not the *diagnosis*.

**Pattern:** a correlation in one output stream promoted to a mechanism without the
experiment that would separate them.

<!-- Superseded body removed on retraction; the original text is in PR #568's history. -->

**Symptom (retained for searchability).** Running the deployed hook against 16 staged AC
records in a worktree:

```text
WARNING: config/ac_store_schema.json not found at /home/henzeh/projects/leafcutter;
         falling back to manual field validation.
exit: 0
```

The `exit: 0` is real and so is the missing file. What does not follow is that the second
caused the first — see the A/B above.

**Still true, and worth keeping from the retracted analysis.** The observed run's staged set
contained two records that `validate_declares_side_effect` errors on when called directly
(see `KI-CG-014`), and the hook passed them. CI, which builds fresh, would have failed the
required `AC store valid` check. So the local green was not merely weak — it was **wrong about
the specific change in front of it**. That remains the strongest available demonstration of
`KI-CG-012`@800's real-world cost, which is why the sighting is logged there.

Also still true: `KI-CG-018` (`check_ac_governance` exiting 0 without inspecting anything)
landed on `main` independently. With `KI-CG-012`@800 and `KI-CG-012`@380 that makes three
distinct routes to "exit 0 having checked nothing" in one hook family — which suggests the
family needs one audited "I did not actually check anything" path rather than several ad-hoc
ones. That recommendation survives the retraction; only the fourth route claimed here does not.

**Register hygiene note.** `KI-CG-012` is used twice in this file, at lines 380 and 800, for
two unrelated defects; PR #575 has since duplicated `KI-CG-016` and `KI-CG-017` the same way.
That is the collision `KI-BO-024` predicts for append-the-next-free-number under concurrent
agents, landed here three times over. Not renumbered in this change because the ids are cited
elsewhere and picking a winner is the owner's call — flagged so it is fixed deliberately rather
than by whoever notices next.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5 (a validator that validates
nothing and reports success).

---
