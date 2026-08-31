---
title: Build-Drift Pre-Commit Hooks (Direction A + Direction B)
type: how-to
status: active
created: 2026-05-13
last_updated: 2026-08-31
components:
- commit_guardian
- infrastructure
description: Overview of Build-Drift Pre-Commit Hooks (Direction A + Direction B).
---
# Build-Drift Pre-Commit Hooks

This document explains why template-output drift is dangerous in the
`leafcutter` package, how the two build-drift pre-commit hooks
detect it, and what you must do to keep commits flowing cleanly.

There are two complementary hooks:

| Hook | Script | Direction | Trigger |
|---|---|---|---|
| `check-build-drift` | `check_build_drift.py` | A — template edited, build not re-run | Template file staged with hash different from manifest |
| `check-output-drift` | `check_output_drift.py` | B — output edited directly | Output file staged with hash different from what build.py would render |

---

## 1. Problem Statement

The `leafcutter/` package lives **inside** its consumer project's repository.
This means the compiled agent outputs (`.claude/agents/*.md`)
share the same working tree as the source-of-truth templates
(`leafcutter/templates/agents/*.md`).

This co-location creates two silent failure modes:

| Failure mode | What happens | Risk |
|---|---|---|
| Template edited, `build.py` not re-run (Direction A) | Installed agents diverge from their template source | Agents in production contradict what the template says |
| Compiled output edited directly (Direction B) | The file on disk lies about what `build.py` would produce | Re-running `build.py` silently overwrites the manual edit |

Neither failure produces a visible error at edit time. Without guardrails,
both modes accumulate undetected until a rebuild or a downstream breakage
surfaces the inconsistency.

Two hooks protect against these failures:

- **`check-build-drift`** (Direction A) — fires when a template file is staged
  and its hash differs from the last build-time record.
- **`check-output-drift`** (Direction B) — fires when a built output file is
  staged and its hash differs from the expected hash that `build.py` would produce
  from the current template.

---

## 2. Detection Strategy

### Why content hash, not mtime

An mtime comparison (`template.mtime > output.mtime`) is cheap but breaks in
multi-worktree git setups: `git checkout` resets file modification times, making
every file appear freshly modified even if its content is unchanged. This would
produce false-blocks on every branch switch.

The hook uses **SHA-256 content hashes** instead. Hashes are stable across
checkouts and unaffected by filesystem timestamp resets.

### The `.build_manifest.json` sidecar

Every successful run of `build.py` writes
`leafcutter/.build_manifest.json` — a flat JSON dictionary mapping
each template file's repo-root-relative path to its SHA-256 digest at build
time:

```json
{
  "leafcutter/templates/agents/commit.md": "a3f1...",
  "leafcutter/templates/agents/python-coder.md": "9c2b...",
  ...
}
```

At commit time, `check_build_drift.py`:

1. Reads `.build_manifest.json`.
2. Enumerates every `.md` file under `leafcutter/templates/agents/`.
3. Computes the SHA-256 of each template's current on-disk content.
4. Compares each current hash against the manifest hash.
5. Blocks the commit (exit 1) if any mismatch is found, and prints the names
   of the out-of-sync templates.
6. Exits 0 (passes) if all hashes match.

### Missing manifest — safe skip

If `.build_manifest.json` does not exist (fresh clone, first setup, or the file
was never committed), the hook exits 0 with a warning instead of blocking.
This prevents false-blocks on machines that have not yet run `build.py` once.

```
check-build-drift: WARNING — .build_manifest.json not found.
Run build.py to generate it. Skipping drift check.
```

### Scope

Direction A (`check-build-drift`) scans two template trees:
`leafcutter/templates/agents/*.md` and
`leafcutter/templates/scripts/commit_guardian/*.py` (the commit-guardian hook
scripts themselves). All other template directories are intentionally
excluded from Direction A.

`write_build_manifest()` mirrors this exact two-directory scan when it writes
the `templates` section of `.build_manifest.json` (BP-100k-1, 2026-08-18).
Before that fix, the manifest only recorded fingerprints for
`templates/agents/`, so every commit-guardian hook template was permanently
reported as "not in manifest" by the gate — drift in a hook script could
never be detected. If a future change adds a third tree to either side of
that pair, add it to both `check_build_drift.py`'s `_collect_py_template_files`
scan/registration and `write_build_manifest()`'s scan in the same commit, or
the same blind spot reappears.

---

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

---

## 3. Developer Workflow

The normal cycle for making any template change is:

```
1. Edit the template
   leafcutter/templates/agents/<agent>.md

2. Re-run the build script
   cd leafcutter
   python scripts/build.py

   This recompiles all templates and rewrites .build_manifest.json
   with fresh SHA-256 hashes.

3. Stage all changed files
   git add leafcutter/templates/agents/<agent>.md
   git add .claude/agents/<agent>.md          # compiled output
   git add leafcutter/.build_manifest.json

4. Commit
   git commit -m "feat(agents): <describe change>"

   The build-drift hook verifies that the template hash in
   .build_manifest.json matches the staged template content.
   If it does, the commit proceeds. If not, see §4 below.
```

**Rule of thumb**: always stage the manifest alongside the template and the
compiled output. The hook reads the manifest that is currently on disk, not
the one that would be staged, so the manifest must be current before you commit.

---

## 4. Fixing a Blocked Commit

When a commit is blocked by the build-drift hook you will see output similar
to the following:

```
[check-build-drift] BLOCKED — template(s) modified without re-running build.py:

  leafcutter/templates/agents/commit.md

Fix: re-run build.py to regenerate outputs and update the manifest,
then stage the updated outputs alongside your template change.
  cd leafcutter && python scripts/build.py
```

### Step-by-step fix

1. **Re-run the build script** from the repo root or the package directory:

   ```bash
   python leafcutter/scripts/build.py
   # or, from inside the package directory:
   cd leafcutter && python scripts/build.py
   ```

   By default `build.py` overwrites existing files, so a plain run is
   sufficient. If you want to skip files that already exist (legacy
   skip-existing behaviour), use `--no-overwrite`.

2. **Verify the manifest was updated.** After a successful run, the last-
   modified timestamp on `leafcutter/.build_manifest.json` should
   be the current time.

3. **Stage all changed files**, including the manifest and any compiled outputs
   that changed:

   ```bash
   git add leafcutter/.build_manifest.json
   git add .claude/agents/          # re-stage all compiled agents
   git add leafcutter/templates/agents/
   ```

4. **Retry the commit.** The hook will now see matching hashes and pass.

### If the block persists

- Confirm that `leafcutter/.build_manifest.json` contains an entry
  for the template that was flagged. New templates added after the last build
  will be absent from the manifest (the hook logs an INFO warning for these,
  not a blocking violation).
- Check that no other process has modified the template file after the build
  ran (e.g. a formatter or an auto-save hook).
- Run `python scripts/build.py` to perform a full rebuild and manifest
  refresh (overwrite is the default; add `--no-overwrite` only if you want
  to preserve local hand-edits in materialised outputs).

---

## 5. Extending the Hook

The hook is configured through two locations. Both must be updated together
when adding a new template directory to the drift scan.

### 5.1 Update `commit_guardian.json`

Open `scripts/commit_guardian/commit_guardian.json` and add the new directory
to the `build_drift.template_dirs` array:

```json
"build_drift": {
    "_comment": "check_build_drift.py — Blocks commit if a template was modified but build.py was not re-run",
    "enabled": true,
    "manifest_path": "leafcutter/.build_manifest.json",
    "template_dirs": [
        "leafcutter/templates/agents",
        "leafcutter/templates/<new-directory>"
    ]
}
```

### 5.2 Update `build.py` / `build_helpers.py`

Open `leafcutter/scripts/build_helpers.py` and ensure `write_build_manifest()`
hashes files from the new directory into the `templates` section. As of
BP-100k-1, `write_build_manifest()` hashes two explicit trees
(`templates/agents/*.md` and `templates/scripts/commit_guardian/*.py`),
mirroring `check_build_drift.py`'s own two-directory scan exactly — it does
not enumerate every template directory automatically. If a new directory
should be scanned by Direction A, add it to **both** places in the same
commit: `check_build_drift.py`'s scan/registration and
`write_build_manifest()`'s explicit list. Verify by running `build.py` and
checking that the new directory's files appear as keys in
`.build_manifest.json`.

### 5.3 Verify end-to-end

After both changes:

1. Run `build.py` to regenerate the manifest with the new directory included.
2. Modify a file in the new template directory without re-running `build.py`.
3. Attempt `git commit` — the hook should block and name the out-of-sync file.
4. Re-run `build.py`, re-stage, and confirm the commit passes.

---

### 5.4 Adding a New Template Category — Developer Checklist

When you add a new build phase that produces user-facing output (e.g. a new
`templates/my-category/` directory), you must update **all four** infrastructure
layers or the new category will be invisible to shims, drift detection, and
stale-artifact cleanup. The parity test (`tests/test_build_artifact_parity.py`)
enforces this requirement mechanically — a commit that adds a phase without
wiring all four layers will cause the parity test to fail with a message naming
the missing layer and category.

**Mandatory updates (all four must be done before committing):**

| Layer | File | Change required |
|---|---|---|
| 1. Shim map | `scripts/build_helpers.py` — module-level `shim_map` | Add `(".claude/<my-category>", "<output-rel>")` to the `shim_map` list. `install_shims()` and `_compute_output_mappings()` both read this same module-level list (BP-100k-2) — do not add a second copy in either function. |
| 2. Output mappings | `scripts/build_helpers.py` — `_compute_output_mappings()` | If the new category is a deploy phase enumerated by `build_phases._compute_phase_mappings()` (agents/commands/workflows/hooks-shaped), coverage is derived automatically once step 1 and `_render_phase_source()`'s family dispatch (compile vs. raw copy) handle it — extend `_render_phase_source()` if the category needs a new render step. Otherwise (skills/rules/workflow-js-shaped, i.e. not enumerated by `_compute_phase_mappings()`), add an explicit scanning block for the new template directory→output path pair, keyed at its canonical (post-shim) path. |
| 3. Managed artifact dirs | `scripts/build_phases.py` — `_MANAGED_ARTIFACT_DIRS` | Add `"<my-category>": "<output-subdir>"` to the dict |
| 4. Source manifests | `scripts/build.py` — `_build_source_manifests()` | Add a scanning block for the new template directory; include the key in the returned dict |

**Bonus: update the drift hook (Direction B):**

If the new category produces output files that should be scanned for
direct-edit drift, also add the new output directory to `_OUTPUT_DIRS` in
`templates/scripts/commit_guardian/check_output_drift.py`.

**Verification:**

After wiring all four layers, run `tests/test_build_artifact_parity.py` to
confirm all cross-validation assertions pass:

```bash
python -m pytest tests/test_build_artifact_parity.py -v
```

If any assertion fails, the error message names the specific category and the
missing layer so you can identify the gap immediately.

---

## 6. Hook Registration

The hook is registered in two places:

**`.pre-commit-config.yaml`** — defines the hook entry that `pre-commit`
invokes on every `git commit`:

```yaml
- id: check-build-drift
  name: check-build-drift
  language: python
  entry: python scripts/commit_guardian/check_build_drift.py
  pass_filenames: false
```

**`scripts/commit_guardian/commit_guardian.json`** — the commit guardian's
central configuration file. The `build_drift` section controls whether the
hook is enabled and which directories are scanned. Setting `"enabled": false`
disables the hook without removing it from `.pre-commit-config.yaml`.

---

## 7. References

- `Master_Plan.md §9` — Key Design Decision that mandates the build-drift
  hook: "A build-drift check hook ensures templates and generated output
  stay in sync — if a template is modified but `build.py` hasn't been
  re-run, the commit is blocked."
  File: `tickets/00_inbox/epics/EPIC-PortableDevWorkflow/Master_Plan.md`

- `scripts/commit_guardian/commit_guardian.json` — hook configuration,
  `hooks_manifest` section.

- `scripts/commit_guardian/check_build_drift.py` — Direction A hook implementation;
  contains the full ARCHITECTURE docstring and DECISION HISTORY.

- `scripts/commit_guardian/check_output_drift.py` — Direction B hook implementation;
  contains the full ARCHITECTURE docstring and DECISION HISTORY.

- `leafcutter/scripts/build.py` — build script that writes
  `.build_manifest.json` after each successful build. The `write_build_manifest()`
  function now records both template hashes (Direction A) and expected output hashes
  (Direction B via `output_mappings`).

- `scripts/build_helpers.py` — where `write_build_manifest()`,
  `_compute_output_mappings()`, and the module-level `shim_map` actually
  live (imported by `build.py`). Contains the full ARCHITECTURE docstring and
  DECISION HISTORY entry for BP-100k-1/-2 (2026-08-18): closing the blind
  spot where the commit-guardian template tree had no manifest fingerprint
  (Direction A) and where every deployed output was keyed by a pre-shim path
  that never matched a real file (Direction B).

- `docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/` —
  `BP-100k-1.yaml` and `BP-100k-2.yaml`, the acceptance criteria this
  manifest-coverage fix resolves.

- `unit_tests/build_guards/test_bp_100k_1.py` and
  `unit_tests/build_guards/test_bp_100k_2.py` — behavioral tests that run the
  real build, then execute `check_build_drift.py` / `check_output_drift.py`
  as subprocesses against real artifacts to assert match/drift verdicts
  instead of absent/unregistered notices.

- `unit_tests/portable_dev_workflow/test_output_drift_hook.py` — unit tests for
  Direction B (6 scenarios, < 5 s total).

- `leafcutter/docs/pre-commit-hooks.md` — overview of all
  pre-commit hooks and their execution sequence.

- `leafcutter/docs/build-pipeline.md` — architecture of the
  template compilation pipeline.

- `docs/known-issues/commit-guardian.md` `KI-CG-034` — the scanner/installer namespace
  mismatch and stale `files:` trigger that made Direction B report a false clean on every
  deployed output; records when and how the fix (`BP-100k-3`, `BP-100k-4`, `BP-100k-6`)
  landed, and what `ACD-2100d-2` added on top of it.

- `unit_tests/build_guards/test_acd_2100d_2.py` — behavioural tests that hand-edit a real
  deployed output file, confirm it is reported by name and blocks the commit, confirm the
  verdict is consumed where "delivered" is decided, and confirm re-running `build.py`
  removes the reported repair.
