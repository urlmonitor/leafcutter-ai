---
title: "KI-CG-20260909-dormant-gate-registration-census — twelve commit-guardian scripts have never been registered, and a census of what each would actually do finds only one that both enforces and passes; four are non-enforcing because a config key is absent, one inspects nothing because of its `pass_filenames` wiring, and two would deadlock ordinary work"
description: "medium — nothing is broken today; every one of these gates is dormant. It is filed because the numbers below are the cost of turning any of them on, and that cost is currently invisible: a PR registering them goes green on all six required "
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

# KI-CG-20260909-dormant-gate-registration-census — twelve commit-guardian scripts have never been registered, and a census of what each would actually do finds only one that both enforces and passes; four are non-enforcing because a config key is absent, one inspects nothing because of its `pass_filenames` wiring, and two would deadlock ordinary work

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — nothing is broken today; every one of these gates is dormant. It is filed because the numbers below are the cost of turning any of them on, and that cost is currently invisible: a PR registering them goes green on all six required checks without a single one of the twelve ever executing against the repo it would gate.
- **Status:** open — no AC. Measured, not acted on. `BP-1600a-2` (formerly `BP-100n-4`, renamed by PR #740) proposes registering all twelve; this entry is the measurement that should scope it, and is filed independently of that PR's fate.
- **Occurrences:** 1 census.
- **First seen:** 2026-09-09 (census run at `df1f0cfb5`) · **Last seen:** 2026-09-09
- **Where:** `templates/scripts/commit_guardian/` — the twelve scripts named below, none present in `commit_guardian.json`'s `hooks_manifest.hooks`.

**Why the numbers were never known.** `ci.yml` runs six named AC hooks by name (`ci.yml:294-299`); it never runs `pre-commit run --all-files`. So the pre-commit gate population is not exercised by CI at all, and a PR that registers new gates is never tested against the code it will gate. The registration PR was green on all six required checks. The first thing that actually ran one of these gates was a developer's own commit.

**The census.** Tracked population at `df1f0cfb5`: 915 `.py`, **0 `.sql`**, 1,291 `tickets/**/*.md`, 597 test files, 12 root-level files. Limits read from `commit_guardian.json`, not from docstrings — several docstrings disagree with the shipped values (SQL complexity is 75, not the 15 its comment implies).

| gate | would it block today? | count |
|---|---|---|
| `check-complexity` | **YES** | **49** of 915 `.py` hold an over-limit function |
| `check-root-files` | **YES** | **5** of 12 root files |
| `check-ticket-ac-limits` | no — passes and genuinely enforces | max 10 ACs vs limit 20 |
| `check-pytest-style` | no — population empty | 0 (no `unit_tests/live_trader/`) |
| `check-sql-complexity` | no — population empty | 0 (no `.sql` tracked) |
| `check-sql-dependencies` | no — population empty | 0 |
| `check-doc-links` | no — `main()` returns 0 unconditionally | 13 warnings in 9 files |
| `check-folder-density` | no — blocking branch unreachable | 107 dirs over limit, all warned |
| `check-test-ac-tags` | no — mode resolves to `warn`, key absent | **5,566** untagged test functions in 595 of 597 files |
| `check-test-fixture-bloat` | no — section absent, defaults disabled | **499** violations in 266 files |
| `check-ticket-test-requirements` | no — **inspects nothing** | **252** of 370 code tickets would fail if wired |
| `check-ac-done-on-merge` | no — always returns 0, but **writes** | 354 tickets would invoke `mark_ac_done.py` |

**The two that would deadlock, and they need different remedies.**

`check-complexity` recomputes each function's score from staged content and refuses on any over 15. It compares nothing to `HEAD`, so all 49 files are hard-blocked on any edit — including an edit that *reduces* complexity, and including an unrelated docstring fix in a file whose offending function is elsewhere. Worst offenders: `scripts/ac_store/generate_ticket_from_ac.py` (75), `scripts/build_helpers.py` (65), `scripts/build.py` (44), `scripts/build_referential_integrity.py` (41), `scripts/build_orchestration/fast_lane.py` (26). Since `build.py` and `fast_lane.py` are among the most-edited files in the repo, registering this flat stops routine work. A ratchet here is not the same shape as `check-file-size`'s: line count is one scalar per file, complexity is a score *per function*, so the comparison must be per-function against `HEAD` (or, more cheaply, "count of over-limit functions in this file must not increase").

`check-root-files` does **not** need a ratchet — it needs a corrected allowlist. Its five violations are `ruff.toml`, `requirements-dev.txt`, `build-self.sh`, `SETUP.md`, `LEAFCUTTER_VERSION`, all legitimate root files of this repo. The shipped allowlist encodes a different project's conventions: it permits `poetry.lock` and `pyproject.toml`, but this repo uses `requirements-dev.txt`, and its only allowed extension is `.json`. Critically, `check_root_files.py:51` matches `A`, `M` **and** `R`, so this is not "you may not add a new root file" — it is "you may never again edit `ruff.toml` or bump `LEAFCUTTER_VERSION`." Version bumps and lint-config edits are routine. Fix by adding the five names to `root_files.allowed_files`, or grandfather on "the path existed at `HEAD`" so only genuinely new unauthorized root files are refused. There is no scalar to ratchet — it is set membership.

**Four gates are registered-shaped but non-enforcing, and that is the part worth remembering.** `check-doc-links` returns 0 whatever it finds. `check-folder-density` computes `before_counts` from `git ls-files`, which already lists staged-but-uncommitted additions, so `before == after` in every real pre-commit run and the blocking branch is unreachable — it will print a "PRE-EXISTING DENSITY" block on most commits (107 folders qualify, up to 174 files in `docs/acceptance-criteria/ac-driven-dev`) while never refusing anything. `check-test-ac-tags` and `check-test-fixture-bloat` are one absent config key each away from blocking on 5,566 and 499 items respectively. Registering these four is safe, and it is also close to meaningless: the registry would then list four gates that cannot fail. **Anyone later enabling `test_ac_tag_enforcement` or `test_fixture_bloat` should read those two counts first** — that is the single most useful thing in this entry.

**One gate inspects nothing, which is the same defect one level up.** `check-ticket-test-requirements` is registered with `pass_filenames: false`, so `run_hook.py` forwards no arguments and its `main()` falls back to `sys.stdin.readlines()`; with empty stdin it checks 0 files and exits 0. Registering it would put a gate in the manifest that examines nothing while reporting success — precisely the false-assurance shape the census AC exists to eliminate. Fix the wiring before registering, not after; correctly wired it fails **252** of 370 code tickets, so it also then needs a grandfather (a per-file boolean: did this ticket have a populated `## Test Requirements` at `HEAD`?).

**One gate blocks nothing but mutates the AC store.** `check-ac-done-on-merge` is post-merge and always returns 0, so it carries zero blocking risk — and for every merged `.md` with `status: done` plus `source_ac` it shells out to `mark_ac_done.py`. 354 tracked tickets match. It has never run here. Dry-run it against that population before registering; a write hook's first execution should not be against 354 live records.

**Deployed-layout caveat on the one clean result.** `check-ticket-ac-limits`'s "0 violations" was obtained by forcing the repo root. Run from the deployed path in this workspace it is a silent no-op: `leafcutter-ai/scripts/commit_guardian` symlinks to `../.leafcutter/scripts/commit_guardian`, `.leafcutter/` contains its own `.git`, and the hook's `_find_project_root()` walks up from `__file__` rather than CWD — so it stops at `/home/henzeh/projects/leafcutter/.leafcutter` and finds **1,295 of 1,295 tickets unreadable → all skipped → exit 0 having read nothing**. The rule genuinely passes when pointed at the real tree, but a green run of the deployed hook proves nothing. Same family as the `.security-allowlist` symlink hazard already in `CLAUDE.md`.

**Confidence.** The `check-complexity` (49) and `check-root-files` (5) counts, and the `A`/`M`/`R` behaviour, were derived twice independently and agree. The remaining counts come from a single measurement pass and are unverified by a second method. One is explicitly uncertain: the `check-ticket-test-requirements` stdin fallback was confirmed to check 0 files with empty stdin, but `pre_commit` is not importable in this environment, so what pre-commit actually attaches to a hook's stdin was not observed — the gate receives no filenames either way, but if stdin were attached to something unexpected the failure mode would be a hang rather than a clean pass.

**Related.**
- `BP-1600a-2` / `-2-i` / `-2-ii` (PR #744, open) — the census AC that proposes registering all twelve. This entry is the measurement that should scope it.
- `KI-CG-20260908-ratchet-reads-pre-merge-head` (above) — `check-file-size`'s registration is the worked example of what registering a dormant gate costs when nobody measured first; it went live on 2026-09-07 and blocked merges repo-wide within a day.
- `GE-127b-1` — the ratchet pattern `check-complexity` lacks and `check-file-size` has.
- `docs/reference/false-green-mechanisms.md` — the `pass_filenames` no-op and the deployed-layout no-op are both instances of "a check that examined nothing must not look like a check that found nothing."

**Pattern:** a gate's registration is a decision about the existing repo, not about the gate — and the population it will judge is exactly the thing no CI check measures, because CI does not run pre-commit.

**Per-gate entries follow.** The census above is the shared context; each gate below is a separate unit of work with its own numbers, its own ratchet shape, and its own definition of done. The governing rule for all of them, set 2026-09-09: **grandfather what exists, enforce on everything new.** A gate that refuses today's repo is not ready; a gate that lets new debt in is not worth registering. Both halves are required.

---
