---
title: Direction B — Output Drift Detection
type: how-to
status: active
created: 2026-09-22
last_updated: 2026-09-22
components:
- commit_guardian
- infrastructure
description: How the check-output-drift pre-commit hook detects directly-edited build outputs, its edge cases, and how to fix a Direction B block.
related_docs:
- docs/build-drift-hook.md
---

> **Parent document:** [build-drift-hook.md](build-drift-hook.md)

## 2B. Direction B: Output Drift Detection

Direction B catches the complementary failure: a developer (or agent) directly
edits a built output file instead of its source template.

### How it works

`build.py`'s `write_build_manifest()` now records, for each template→output
mapping, the SHA-256 of what `build.py` would write — i.e. after full template
compilation and config injection. This is stored in the `output_mappings` section
of `.build_manifest.json`:

```json
{
  "leafcutter/templates/agents/commit.md": "a3f1...",
  ...
  "output_mappings": {
    ".claude/agents/commit.md": {
      "template": "leafcutter/templates/agents/commit.md",
      "expected_output_hash": "7e2c..."
    },
    ".claude/skills/signoff/SKILL.md": {
      "template": "leafcutter/templates/skills/signoff/SKILL.md",
      "expected_output_hash": "b91a..."
    }
  }
}
```

At commit time, `check_output_drift.py`:

1. Reads `.build_manifest.json`.
2. Scans all files under `.claude/agents/`, `.claude/skills/`, `.claude/commands/`,
   and `.agents/rules/`.
3. For each file, looks up its `expected_output_hash` in `output_mappings`.
4. Computes the SHA-256 of the on-disk content.
5. If the hashes differ: records a violation.
6. After scanning all files: if any violations exist, prints a clear error message
   naming both the offending output file and its source template, then exits 1.

### Output directories covered

| Output directory | Corresponding template directory |
|---|---|
| `.claude/agents/` | `leafcutter/templates/agents/` |
| `.claude/skills/` | `leafcutter/templates/skills/` |
| `.claude/commands/` | `leafcutter/templates/commands/` and `leafcutter/templates/workflows/` |
| `.claude/hooks/` | `leafcutter/templates/hooks/` |
| `.claude/workflows/` | `leafcutter/templates/workflows-js/` |
| `.agents/rules/` | `leafcutter/templates/rules/` |

`_compute_output_mappings()` keys every entry in `output_mappings` by the
**canonical**, post-shim path shown in the left column above — the same path
`check_output_drift.py` scans — never by the pre-shim,
`output_root`-relative path (e.g. `agents/README.md`). Before BP-100k-2
(2026-08-18), the agents/commands/workflows/hooks families were keyed by the
pre-shim path, so no real deployed file ever matched an `output_mappings`
entry and the gate reported every deployed output as unregistered. The
agents/commands/workflows/hooks rows are now derived from
`build_phases._compute_phase_mappings()` — the same enumeration `build.py`'s
own deploy-collision guard uses — and translated to their canonical path via
the module-level `shim_map` in `scripts/build_helpers.py` (the same table
`install_shims()` uses to create the shims), so a new deploy phase or shim
entry extends `output_mappings` coverage without a second, independently
maintained list.

### Edge cases

| Situation | Behaviour |
|---|---|
| `.build_manifest.json` absent (fresh clone) | Warn on stderr, exit 0 |
| `output_mappings` section absent (old manifest format) | Warn on stderr, exit 0 |
| Output file on disk but NOT in `output_mappings`, with a grounded exemption declared | `UNCOMPARABLE: EXEMPT <key> ground=<ground>` on stderr, counted in the `exempt` field of the `RESULT` line, never blocks (exit 0) |
| Output file on disk but NOT in `output_mappings`, with no grounded exemption declared | `UNCOMPARABLE: GAP <key> action=run build.py to register it` on stderr, counted in the `gaps` field, drives a non-clean, non-zero exit |
| Output file in `output_mappings` but missing on disk | `UNCOMPARABLE: MISSING <key> reason=recorded but not found on disk` on stderr, counted in the `missing` field, always drives a non-zero exit — deletion is the most complete form of drift |
| Output file in `output_mappings`, present on disk, but unreadable (permission error, or not a regular file) | `UNCOMPARABLE: UNREADABLE <key> reason=<detail>` on stderr, counted in the `unreadable` field, always drives a non-zero exit |
| Template AND output both changed in same commit, output matches re-render | Exit 0 (hashes agree) |

**This table describes the current, verified behaviour as of `BP-100k-3` / `BP-100k-6`
(2026-08-18) plus the adversarial-review `UNREADABLE` case added afterward.** Before those
fixes, both "not in `output_mappings`" rows above collapsed into a single silent
`INFO warning on stderr, skip file, exit 0` path — which meant an unmapped file was reported
identically to a file that was checked and found clean, and a hardcoded (rather than
installer-derived) scan/key namespace meant *every* deployed output took that path, so the
hook never actually compared anything. That regression is recorded in full in
[`docs/known-issues/commit-guardian.md`](known-issues/commit-guardian.md) `KI-CG-034`, along
with the companion trigger defect below. Do not reintroduce a silent skip on the unmapped
path — every uncomparable case above must print a line and be counted in the `RESULT`
summary, whether or not it blocks the commit.

The `RESULT` line format is `RESULT verified=<N> uncomparable=<M> exempt=<E> gaps=<G>
drifted=<D> missing=<X> unreadable=<Y>`. Only `drifted`, `gaps`, `missing`, and `unreadable`
drive a non-zero exit; `exempt` entries are reported for visibility but never block, per the
grounded-exemption contract above.

**The hook's pre-commit trigger does not filter by staged path.** `check-output-drift`'s
entry in `scripts/commit_guardian/commit_guardian.json` carries `"always_run": true` rather
than a `files:` path-prefix filter (`BP-100k-4`). This is deliberate, not an oversight: the
hook scans the whole output tree by content hash and never consults the staged file list
(`pass_filenames: false`), so a `files:` filter would silently exclude any output deployed
under a differently-configured output root — precisely the second half of `KI-CG-034`.

### Fixing a Direction B block

When a commit is blocked by `check-output-drift` you will see:

```
[check-output-drift] BLOCKED — output file(s) were directly edited
instead of their source templates:

  output:   .claude/agents/commit.md
  template: leafcutter/templates/agents/commit.md

Fix: Edit the template at the path shown above, re-run
  build.py  (or: python leafcutter/scripts/build.py --force)
then stage both the template and the updated output.
```

**Step-by-step fix:**

1. Identify the source template named in the error.
2. Make your change to the **template**, not the output.
3. Re-run `build.py` to recompile outputs and update `.build_manifest.json`:
   ```bash
   python leafcutter/scripts/build.py --force
   ```
4. Stage both the template and the updated output:
   ```bash
   git add <template-path>
   git add <output-path>
   git add leafcutter/.build_manifest.json
   ```
5. Retry the commit.

### Adding new output directories

When `build.py` gains a new output phase (e.g. writing to a new directory),
update `_compute_output_mappings()` in `build.py` to include the new
template→output mapping, and add the new output directory to `_OUTPUT_DIRS`
in `check_output_drift.py`. Both changes must land in the same commit to keep
the manifest and hook in sync.
