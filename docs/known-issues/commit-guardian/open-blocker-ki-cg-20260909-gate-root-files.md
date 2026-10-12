---
title: "KI-CG-20260909-gate-root-files — `check-root-files` refuses 5 legitimate root files and matches `M`, so registering it makes `ruff.toml` and `LEAFCUTTER_VERSION` permanently uneditable"
description: "high (as a blocker to registration); trivial to fix."
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

# KI-CG-20260909-gate-root-files — `check-root-files` refuses 5 legitimate root files and matches `M`, so registering it makes `ruff.toml` and `LEAFCUTTER_VERSION` permanently uneditable

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high (as a blocker to registration); trivial to fix.
- **Status:** open — no AC. Smallest of the set; likely a single short session.
- **Occurrences:** measured once, `df1f0cfb5`. · **First seen:** 2026-09-09 · **Last seen:** 2026-09-09
- **Where:** `templates/scripts/commit_guardian/check_root_files.py:34` (`git diff --cached --name-status`), `:51` (the status filter); allowlist at `commit_guardian.json` → `root_files.allowed_files` / `allowed_extensions`.

> **PARTIALLY RESOLVED 2026-09-28 — the `M` half is fixed; the allowlist half is not.**
> `check_root_files.py:51` now matches `A` and `R` only (GE-120e-1-ii, PR #857). The
> "these five may never be modified again" consequence below is therefore **gone**:
> `LEAFCUTTER_VERSION` can be bumped and `ruff.toml` edited, because a modification to a
> path already tracked at the root is no longer treated as an addition. That was found the
> hard way — a one-line addition of `pytest-xdist` to `requirements-dev.txt` was refused,
> which is this entry's `requirements-dev.txt` row reaching someone in practice.
>
> **What remains open is the allowlist itself.** The five names are still absent from
> `root_files.allowed_files`, and `.toml` is still not in `allowed_extensions`. With
> `A`-only matching that now bites in a narrower set of cases — adding one of the five to a
> fresh checkout, or deleting and re-adding one — rather than on every edit. Severity of the
> remaining half is correspondingly lower than the `blocker` in this filename, which is kept
> unchanged per the split convention.
>
> The deliberate scope call: PR #857 fixed the status filter and explicitly did **not**
> bundle the allowlist, because the allowlist ships to adopters and each of the five needs
> the one-line defensible-as-a-general-default rationale this entry's Definition of Done
> already asks for. That reasoning is unchanged and still the right shape for the rest.

**The numbers.** 5 of 12 tracked root files violate: `ruff.toml`, `requirements-dev.txt`, `build-self.sh`, `SETUP.md`, `LEAFCUTTER_VERSION`. The shipped allowlist permits `poetry.lock` and `pyproject.toml` but this repo uses `requirements-dev.txt`; permits `setup.sh` and `init-db.sh` but not `build-self.sh`; permits `README.md`/`BOOTSTRAP.md`/`CLAUDE.md` but not `SETUP.md`; and its only allowed extension is `.json`, so `.toml` and the extensionless `LEAFCUTTER_VERSION` both fall through.

**Why this was worse than it sounds — the half that PR #857 fixed.** The filter used to match `A`, `M` **and** `R`. So it was not "no new root files" — it was "these five may never be modified again." Bumping `LEAFCUTTER_VERSION` is part of every release; editing `ruff.toml` is routine lint maintenance. As of PR #857 the filter is `A` or `R` only (`check_root_files.py:55`), so a plain modification to an already-tracked root file no longer trips the gate. The allowlist half below is unchanged and still open.

**This one needs no ratchet — the allowlist is simply wrong for this repo.** It encodes another project's conventions. Fix by adding the five names to `root_files.allowed_files` (and consider `.toml` in `allowed_extensions`). A `HEAD`-existence grandfather is the fallback if some of the five are judged genuinely unwanted, but the straightforward reading is that all five belong at the root of this repo and the config is stale.

**Definition of done.** The five are allowlisted deliberately, one line of rationale each; a genuinely new unauthorized root file is still refused; the gate is registered. Watch the consumer case — the allowlist ships to adopters, so anything added must be defensible as a general default, not just as this repo's convenience.

**Re-verified 2026-09-23: STILL TRUE, and WORSE than filed — the gate is now actually
registered and live, kept open.** This entry was filed 2026-09-09 warning what registration
*would* do. As of `commit_guardian.json`'s `hooks_manifest.hooks` (id `check-root-files`,
`commit_guardian.json:1349-1360`, no `enabled: false`) and the generated
`.pre-commit-config.yaml:501` (`- id: check-root-files`, no `always_run`/skip), the hook is now
**registered and wired into the live pre-commit config** — confirmed via
`git log -S'"id": "check-root-files"'`, landed in `89e8cb33` (2026-09-15, "BP-100n-4") among
13 gates "verified exit 0 under real invocation." The allowlist gap this entry names is
unfixed:

```
$ grep -n "allowed_files\|allowed_extensions" -A35 templates/scripts/commit_guardian/commit_guardian.json | head -40
    "allowed_files": [ ... 30 entries, still none of: ruff.toml, requirements-dev.txt,
                        build-self.sh, SETUP.md, LEAFCUTTER_VERSION ... ]
    "allowed_extensions": [ ".json" ]        # still no ".toml"

$ git ls-files ruff.toml requirements-dev.txt build-self.sh SETUP.md LEAFCUTTER_VERSION
LEAFCUTTER_VERSION
SETUP.md
build-self.sh
requirements-dev.txt
ruff.toml
```

All five files are still tracked at the repo root and still absent from the allowlist.

The status filter is no longer part of this: PR #857 narrowed it to `A` or `R`
(`check_root_files.py:55`), so modifying one of the five — bumping `LEAFCUTTER_VERSION` for a
release, editing `ruff.toml` — is no longer refused. That was the urgent half and it is closed.

What remains is the allowlist itself, and it bites in a narrower set of cases: adding one of
the five to a fresh checkout, or deleting and re-adding one. Mechanism confirmed present;
kept open at reduced practical urgency, with the filename severity unchanged per the split
convention.

---

## 2026-09-30 — a THIRD trigger: any merge of main into a branch that predates the file

The two narrow cases listed above — fresh checkout, delete-and-re-add — are not the whole
remaining surface. **A merge commit is also an addition.**

Observed while merging current `origin/main` into `fast-lane/inf-700a-2` (PR #877). The
commit was refused:

```text
🚫 Root Directory Check Failed
You are trying to commit unauthorized files to the root directory:
  ❌ requirements-dev.txt
```

Nothing in that commit put a new file at the root. `requirements-dev.txt` is **main's own**,
added in `e2d9cd0d` (TQ-600a-1) — verified before skipping with
`git log origin/main -- requirements-dev.txt`, not assumed. The branch simply predated it,
so `git diff --cached --name-status` on the merge reports it as `A`, and an `A`-matching
gate cannot tell "the committer added this" from "the merge brought this across".

**Why this is broader than the two cases above.** Those require a deliberate act on one of
the five files. This one requires nothing: every branch that forked before `e2d9cd0d` trips
it on its next merge from main, whatever that branch is about. In a repo with ~19 open PRs
and a main that moves several times an hour, that is close to every branch. The practical
urgency of the remaining half is therefore higher than the "narrower set of cases" reading
above, without the allowlist having changed at all.

**It also manufactures exactly the habit this register exists to discourage.** The only way
past is `SKIP=check-root-files` on the merge commit, and a gate that must be skipped
routinely stops being read as a gate. Each skip then has to be justified individually to
stay honest, which is cost paid on every branch for a config that is simply stale for this
repo.

**No change to the fix.** Adding the five to `root_files.allowed_files` closes this trigger
along with the other two — the diagnosis in this entry was already right, it is the blast
radius that was understated. Nothing new is needed beyond what the Definition of Done above
already asks for.

**Distinguish from the `M`-filter bug PR #857 fixed.** That one was "an already-tracked root
file may never be modified". This one is "an already-tracked root file arrives via merge and
is read as new". Same allowlist gap, different diff status, and `A`-only matching does not
help because a merge genuinely presents the path as `A`.

---
