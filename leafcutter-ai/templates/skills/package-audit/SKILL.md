---
name: package-audit
description: >
  Surface the leafcutter package gap as an invocable skill.
  Runs package_audit.py, parses the JSON output, and presents a structured
  human-readable Markdown report with recommended actions per file.
  Optionally dispatches add-agent-to-package / add-skill-to-package /
  create-hook for items the user approves.
allowed-tools: Read, Bash(python *)
---

# package-audit

Surface the leafcutter package gap as a structured decision report.
Run read-only by default; only dispatch promotion sub-skills when the user
explicitly approves individual items.

## Inputs

| Field | Required | Description |
|-------|----------|-------------|
| `project_root` | no | Absolute path to consumer project root. Defaults to the parent-parent of `package_audit.py` (i.e., the project root when the script lives at `leafcutter/scripts/package_audit.py`). |
| `package_root` | no | Absolute path to `leafcutter/`. Defaults to the parent of the scripts dir. |
| `boundary_config` | no | Override path to `package_boundary.json`. Defaults to `<package_root>/config/package_boundary.json`. |
| `promote` | no | When `true`, after presenting the report, ask the user which `move` items to promote and dispatch the appropriate sub-skill per item. Default: `false` (report only). |

## Step 1 — Run the audit script

Locate `package_audit.py`:

```bash
python leafcutter/scripts/package_audit.py \
  [--project-root <project_root>] \
  [--package-root <package_root>] \
  [--boundary-config <boundary_config>] \
  --json
```

Capture the JSON output. If the script returns a non-zero exit code, surface
the stderr and stop — do not attempt to parse partial output.

## Step 2 — Parse JSON output

The JSON root has this shape:

```json
{
  "project_root": "...",
  "package_root": "...",
  "total_missing": N,
  "sections": [
    {
      "name": "commit-guardian",
      "live_dir": "...",
      "template_dir": "...",
      "missing_count": M,
      "items": [
        {
          "filename": "check_build_drift.py",
          "classification": "portable",
          "in_template": false,
          "action": "move"
        }
      ]
    }
  ]
}
```

Group items by section. Within each section, separate into three buckets:
- `action == "move"`: portable, not yet in package template
- `action == "mark-boundary"`: project-specific, not yet classified in config
- `action == "none"`: already handled (in template or unknown-but-present)

## Step 3 — Present the report

Print the following Markdown structure to the user.

**Zero-gap case** (`total_missing == 0`):

```
## Package Audit — No Gap Detected

All portable artifacts are already present in the package template.
Nothing to promote.
```

**Non-zero gap** — one table per section that has at least one item with
`action != "none"`:

```markdown
## Package Audit Report

**Total portable files missing from package**: N

### commit-guardian

| File | Classification | In Template | Recommended Action |
|------|----------------|-------------|-------------------|
| `check_build_drift.py` | portable | no | move into package |
| `apply_sql_changes.py` | project-specific | no | mark-boundary |

### agents

| File | Classification | In Template | Recommended Action |
|------|----------------|-------------|-------------------|
| `database-agent.md` | project-specific | no | mark-boundary |

### skills

| File | Classification | In Template | Recommended Action |
|------|----------------|-------------|-------------------|
| `build-feature` | portable | no | move into package |
```

Only show sections that have at least one `action != "none"` item.
For `action == "none"` items, omit them from the table entirely.

**Recommended Action values**:
- `move into package` — file is portable and absent from the template; needs promotion
- `mark-boundary` — file is project-specific but not yet listed in `package_boundary.json`; add it
- (omitted) — file is already in template or fully handled

## Step 4 — Dispatch promotions (when `promote == true`)

After presenting the report, ask the user:

> "Which items would you like to promote now? List filenames, or say 'none' to skip."

For each approved item, determine the dispatch skill based on section:

| Section | Sub-skill to invoke |
|---------|---------------------|
| `commit-guardian` | `create-hook` |
| `agents` | `add-agent-to-package` |
| `skills` | `add-skill-to-package` |

Invoke the appropriate skill for each approved item. Pass:
- For `create-hook`: `hook_name` = filename without `.py` suffix
- For `add-agent-to-package`: `agent_id` = filename without `.md` suffix
- For `add-skill-to-package`: `skill_name` = directory name (filename as-is for skills)

After all promotions complete, re-run Step 1 to refresh the report and confirm
the gap has decreased.

## Step 5 — Mark-boundary items

For items the user wants to mark as project-specific (action `mark-boundary`),
edit `leafcutter/config/package_boundary.json` to add the filename
with classification `"project-specific"` in the appropriate section's `items`
map.

Do NOT run `build.py` after editing `package_boundary.json` alone — the
boundary config is consumed directly by `package_audit.py` and is not part of
the build pipeline.

## Invariants

- NEVER promote an item without explicit user approval (unless `promote == true`
  AND the user has listed the item).
- NEVER modify `package_boundary.json` for items the user has not explicitly
  approved for `mark-boundary`.
- Report-only mode (`promote == false`) makes no filesystem changes.
- If `package_audit.py` does not exist at the expected path, surface the error
  and instruct the user to run the T01 implementation task first.
- The Markdown report is printed to the conversation, never written to disk.
