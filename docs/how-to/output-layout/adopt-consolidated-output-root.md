# How to: Adopt the Consolidated Output Root (.leafcutter/)

## Prerequisites

- leafcutter-ai is cloned into your project (e.g. `my-project/leafcutter-ai/`)
- `.claude/skills_config.json` exists (run `/onboard` if not)
- You have previously run `build.py` with the old scattered-output layout

## Steps

### 1. Update skills_config.json

Add the new fields to your `.claude/skills_config.json`:

```json
{
  "output_root": ".leafcutter",
  "shim_strategy": "auto"
}
```

- `output_root`: folder name where build.py writes all artifacts (default: `.leafcutter`)
- `shim_strategy`: `"auto"` (symlink with copy fallback), `"symlink"`, or `"copy"`

### 2. Run the migration report

```bash
python leafcutter-ai/scripts/build.py --migrate
```

This scans for stale files at old locations (`.claude/agents/`, `scripts/commit_guardian/`, etc.) and prints a removal guide. **No files are deleted automatically.**

### 3. Remove stale files

Follow the removal commands printed by `--migrate`. Example:

```bash
rm -rf .claude/agents/
rm -rf .claude/skills/
rm -rf .claude/commands/
rm -rf .claude/hooks/
rm -rf scripts/commit_guardian/
rm -rf scripts/doc_compliance/
rm -rf scripts/feedback/
rm .pre-commit-config.yaml
```

Only remove paths listed as `STALE` in the report.

### 4. Rebuild

```bash
python leafcutter-ai/scripts/build.py
```

After this run:
- All build artifacts live in `.leafcutter/`
- Shims at `.claude/agents/`, `.claude/skills/`, etc. point into `.leafcutter/`
- Claude Code, pre-commit, and Gemini continue working via the shims

### 5. Update .gitignore

If you want to treat `.leafcutter/` as a build artifact (recommended):

```gitignore
# leafcutter build output — regenerate with: python leafcutter-ai/scripts/build.py
.leafcutter/
```

### 6. Verify

- Run Claude Code and confirm agents load (try `/help` or invoke any agent)
- Run `git status` — only `.leafcutter/` should show (or nothing if git-ignored)
- Run pre-commit hooks to confirm they still execute

## Troubleshooting

**Symlink creation fails on Windows:**
Set `"shim_strategy": "copy"` in your skills_config.json, or enable Developer Mode in Windows Settings > Update & Security > For developers.

**Claude Code can't find agents after migration:**
Verify `.claude/agents/` exists (as a symlink or directory). Run `ls -la .claude/agents/` to confirm it points into `.leafcutter/agents/`.
