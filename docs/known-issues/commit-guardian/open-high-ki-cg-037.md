---
title: "KI-CG-037 — `documentation_guard` signals its block with exit 1, which Claude Code does not treat as a block, and its path map names another project's folders"
description: "KI-CG-037 — `documentation_guard` signals its block with exit 1, which Claude Code does not treat as a block, and its path map names another project's folders"
type: reference
category: reference
status: active
created: '2026-09-17'
last_updated: '2026-09-17'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-037 — `documentation_guard` signals its block with exit 1, which Claude Code does not treat as a block, and its path map names another project's folders

> Index: [commit-guardian.md](../commit-guardian.md). Filename severity is the three-level
> index bucket (`high`); the original grading is the `**Severity:**` line below.
>
> **Id note.** Filed 2026-09-17 under the date-and-slug form and renamed to the sequential
> form the same day: `check-secrets` scored the long slug as a high-entropy string and refused
> the commit, six findings across three files, every one of them this id. No secret was
> involved; the id was shortened rather than allowlisted. The date form remains the preferred
> convention (see `README.md`) — this is an exception, not a reversal.

- **Severity:** high
- **Status:** open — owning AC `GE-130f` (repair a protection before widening it; `GE-130a`
  depends on it)
- **Occurrences:** 1 (found by reading the hook against its registration, 2026-09-17)
- **First seen:** 2026-09-17 · **Last seen:** 2026-09-17
- **Where:** `templates/hooks/documentation_guard.py` — `DOC_MAPPING` (`:51-150`) and the
  blocking exit in `main()` (`:407-409`); registered as a `PreToolUse` hook on `Edit|Write`
  in `templates/settings.json` (deployed copy `.claude/hooks/documentation_guard.py` is
  byte-identical)

**Symptom.** The hook describes itself as *"blocking for arch-tagged files"*: an Edit or
Write of a `.py`/`.sql` file mapped to an L1/L2/L3 architecture doc that was not updated
today is supposed to be refused. It refuses nothing, for two independent reasons, either of
which alone is enough.

**Mechanism 1 — the block is exit 1.** `main()` ends:

```python
if blocking:
    print(_format_blocking_message(rel_path, blocking), file=sys.stderr)
    sys.exit(1)
```

Claude Code's hooks reference (code.claude.com/docs/en/hooks, fetched 2026-09-17) states
for `PreToolUse`: exit 2 is a blocking error; any other non-zero exit "does NOT block on its
own", and *"Exit code 1 treated as non-blocking. Use exit 2 to enforce policy."* So the
"ARCHITECTURE DOC UPDATE REQUIRED" message is at most a non-blocking error notice and the
Edit/Write proceeds. The module docstring (`:20`, `:22`) and `main()`'s docstring both
promise a block that the exit code cannot deliver. Its siblings on the same matcher,
`inline_work_guard` (`:180`) and `readme_read_guard` (`:271`), both block with exit 2.

**Mechanism 2 — the map matches no path here.** Every `DOC_MAPPING` key names a folder from
the project this hook was extracted from: `live_trader/`, `collector/`, `models/`,
`sql_functions/`, `alembic/`, `dashboards/`, `ml_models/`, `trading_model/`,
`backtesting/`, plus `settings.py`, `docker-compose`, `.env`. Verified 2026-09-17 with
`git ls-files <prefix> | wc -l`: **0 tracked files** under every one of them. And
`get_related_docs` only returns docs that exist on disk; the three arch-tagged targets
(`docs/architecture/L3_database_phase_flows.md`, `collector_services.md`,
`L3_core_domain_erd.md`) do not exist either. So `related_docs` is empty for every file in
this repository and `main()` exits 0 at `:389-390` before exit code even matters.

**Why high.** A guard that is registered, runs on every Edit/Write, and cannot refuse
anything looks identical to one that is working. Its escape hatch `CLAUDE_NO_DOC_UPDATE=1`
is documented in `docs/reference/claude-code-hooks.md` as if it bypassed something. Fixing
only mechanism 1 changes nothing observable (the map still matches nothing); fixing only
mechanism 2 produces warnings that still do not block.

**Evidence.**

```text
$ for d in live_trader collector models sql_functions alembic dashboards ml_models \
    trading_model backtesting settings.py; do echo "$d: $(git ls-files "$d" | wc -l)"; done
live_trader: 0   collector: 0   models: 0   sql_functions: 0   alembic: 0
dashboards: 0    ml_models: 0   trading_model: 0   backtesting: 0   settings.py: 0
```

**Fix direction.** Per `GE-130f`: repair first, then widen.

- Signal the block the way Claude Code honours it: exit 2 with the reason on stderr, or
  exit 0 with `hookSpecificOutput.permissionDecision: "deny"`.
- Replace the hardcoded map with one derived from this repository (for example from
  `docs/components.json` / architecture doc frontmatter), or make it configurable. A map
  that matches nothing should say so, not exit 0 silently.
- Prove it with a test that hands the deployed hook a known-bad edit and asserts a refusal,
  which is the `GE-120f` standard for counting a guard as protection.

**Related.** `KI-CG-20260917-claude-code-hooks-reference-contradicts-exit-codes` (the
reference doc that gets the exit-code contract wrong),
`KI-CG-20260917-readme-read-guard-never-checks-a-write` (the sibling guard `GE-130f` also
repairs).

**Pattern:** `docs/reference/false-green-mechanisms.md`: a guard that reports enforcement it
does not perform.

---
