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

**The numbers.** 5 of 12 tracked root files violate: `ruff.toml`, `requirements-dev.txt`, `build-self.sh`, `SETUP.md`, `LEAFCUTTER_VERSION`. The shipped allowlist permits `poetry.lock` and `pyproject.toml` but this repo uses `requirements-dev.txt`; permits `setup.sh` and `init-db.sh` but not `build-self.sh`; permits `README.md`/`BOOTSTRAP.md`/`CLAUDE.md` but not `SETUP.md`; and its only allowed extension is `.json`, so `.toml` and the extensionless `LEAFCUTTER_VERSION` both fall through.

**Why this is worse than it sounds.** Line 51 matches `A`, `M` **and** `R`. So it is not "no new root files" — it is "these five may never be modified again." Bumping `LEAFCUTTER_VERSION` is part of every release; editing `ruff.toml` is routine lint maintenance.

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

All five files are still tracked at the repo root and still absent from the allowlist; the
status filter in `check_root_files.py:51` still matches `A`, `M`, **and** `R`. Since the gate
is now live rather than hypothetical, staging a modification to any of the five (e.g. bumping
`LEAFCUTTER_VERSION` for a release, or editing `ruff.toml`) would be refused today. This raises
the entry's practical urgency; it does not change the verdict. Mechanism confirmed present and
now demonstrably live; kept open.

---
