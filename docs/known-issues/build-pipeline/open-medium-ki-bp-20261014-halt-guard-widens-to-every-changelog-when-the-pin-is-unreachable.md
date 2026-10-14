---
title: "KI-BP-20261014-halt-guard-widens-to-every-changelog-when-the-pin-is-unreachable — when `git log <pin>..HEAD` fails, build_halt_guard silently treats every changelog entry ever written as new, so an already-applied breaking migration halts the build again instead of the guard saying it could not tell"
description: "medium — _find_breaking_entries_since() in scripts/build_halt_guard.py reads the pinned SHA from the target's .leafcutter.lock and runs `git log <pin>..HEAD -- changelogs/`. On CalledProcessError (for example a pin that is not in the package's object store) it falls back, with no message, to every *.md in changelogs/. Any breaking: true entry in the whole history then halts the build with BREAKING CHANGES DETECTED, indistinguishable from a real new migration, and the only way past is --force-breaking, which also waves through a genuine one. Code verified on origin/main 95961b718. The 2026-10-14 GE-127g-5 lane halted on INF-500d-4, an already-merged migration; this fallback is the likely cause (inferred, not reproduced)."
type: reference
category: reference
status: active
created: '2026-10-14'
last_updated: '2026-10-14'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
  - docs/known-issues/build-pipeline/open-blocker-ki-bp-018.md
---

# KI-BP-20261014-halt-guard-widens-to-every-changelog-when-the-pin-is-unreachable — an unanswerable "what changed since the pin?" is answered "everything"

> Filed 2026-10-14 from the GE-127g-5 lane. Index: [build-pipeline.md](../build-pipeline.md).

- **Severity:** medium. It fails towards halting, not towards passing, so no migration is skipped by
  it. But the halt names migrations that were applied long ago, gives no sign that the range could
  not be computed, and leaves `--force-breaking` as the only way on. An operator or agent who learns
  to pass that flag also passes the next real breaking change.
- **Status:** open, no AC.
- **Occurrences:** 1 suspected (GE-127g-5 fast lane, 2026-10-14). See "Observed" for what is and is
  not established.
- **First seen:** 2026-10-14 · **Last seen:** 2026-10-14
- **Where:** `scripts/build_halt_guard.py`
  - `:55-69` `read_lock_file`: the pin comes from `<target_root>/.leafcutter.lock`.
  - `:157-192` `_find_breaking_entries_since`: runs
    `git log <pin>..HEAD --name-only --pretty=format: -- <changelogs_dir>` in the **package** root
    (`:166-174`). On `subprocess.CalledProcessError` it does this (`:175-176`):

    ```python
    except subprocess.CalledProcessError:
        files = {str(p.relative_to(package_root)) for p in changelogs_dir.glob("*.md")}
    ```

    No warning is printed or logged, and the result carries no flag saying the range was not
    resolved.
  - `:200-220` `check_halt_guard`: any breaking entry in that set gives `should_halt=True`.
  - `scripts/build_main_helpers.py:239-260` `_run_halt_guard`: prints the migration notice and returns
    exit 1 unless `--dry-run` or `--force-breaking`.

## Mechanism

The pin is read from the target, but the range is resolved in the package. Whenever the pinned SHA
is unknown to the package's repository, `git log` fails: a lock written by a build from a different
clone, a pin from a branch that was squash-merged and then pruned, or a shallow clone. Then the guard
does not say "could not determine what is new". It answers as if every changelog entry were new. On a
repository whose history holds any `breaking: true` entry, that means a halt on every such build. The
notice it prints is the same one a real new migration gets.

Whether a given build halts therefore depends on which lock the target holds, not on what changed.
That matches the symptom below.

## Observed (2026-10-14)

The GE-127g-5 lane halted at commit when `build.py` reported `BREAKING CHANGES DETECTED` over
INF-500d-4, an unrelated migration already merged to main. In the lane's worktree the same build
passed with no override, because that worktree's `.leafcutter.lock` pins current main, which is
after that entry. The commit that recorded this (`8d9aea24e`) names the fallback above as the likely
cause. **The failing `git log` was not captured**, so it is not proven that this branch, rather than a
genuinely older pin, produced that halt. The code path is verified. The causal link is inferred.

## Related

`KI-BP-018` lists `build_halt_guard.py:61-69, 89-101` (a corrupt lock or no git disarms the gate,
unlogged). That is the opposite direction, failing open, on different lines. This entry is the
`:175-176` fallback, which widens instead.

## Detection

A `BREAKING CHANGES DETECTED` notice that lists entries older than the target's pin. Check the pin by
hand:

```bash
git -C <package-root> cat-file -e <sha-from-.leafcutter.lock>^{commit}
```

A non-zero exit means the guard took the fallback.

## Workaround

Rebuild the lock: a successful build rewrites `.leafcutter.lock` with the package's current SHA
(`build.py:1899`). If the listed entries really are already applied, a single `--force-breaking` run
does that. Check the list by hand first, since the flag passes everything in it.

## Suggested fix

1. Replace the silent fallback with an explicit third outcome: "could not determine which changelog
   entries are new (pin `<sha>` not found in `<package_root>`)". Report it and halt with that wording,
   so nobody reads it as a new migration.
2. Say what to do: rebuild from a checkout that contains the pin, or confirm and re-pin.
3. Add a test that writes a lock with an unknown SHA and asserts the guard reports the undetermined
   range rather than listing historic breaking entries.

**Pattern:** a "since when?" query whose failure is answered with "since the beginning", and a result
that cannot tell a computed answer from a guessed one.
