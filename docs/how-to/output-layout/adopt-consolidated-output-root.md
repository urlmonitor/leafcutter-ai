# How to: Adopt the Consolidated Output Root (.leafcutter/)

## Prerequisites

- leafcutter-ai is cloned into your project (e.g. `my-project/leafcutter-ai/`)
- `.claude/skills_config.json` exists (run `/onboard` if not)

## What happens on upgrade

When you pull the latest leafcutter-ai and run `build.py`:

1. All build outputs are written into `.leafcutter/`
2. Old stale files at `scripts/commit_guardian/`, `.claude/agents/`, etc. are
   **automatically removed**
3. Symlinks are created at `.claude/agents/`, `.claude/skills/`, `.gemini/`, etc.
   pointing into `.leafcutter/`
4. Pre-commit hook entries reference `.leafcutter/scripts/commit_guardian/...`

The upgrade is seamless — just run `build.py` and everything migrates.

## Steps

### 1. Update skills_config.json (optional)

The defaults work out of the box. Only add these if you want non-default values:

```json
{
  "output_root": ".leafcutter",
  "shim_strategy": "auto"
}
```

### 2. Run build.py

```bash
python leafcutter-ai/scripts/build.py
```

This will:
- Write all artifacts to `.leafcutter/`
- Auto-remove stale files at old locations (`scripts/commit_guardian/`, etc.)
- Create symlinks at `.claude/agents/`, `.gemini/`, `.pre-commit-config.yaml`

After this run:
- `.leafcutter/` contains all leafcutter artifacts
- Symlinks at `.claude/agents/`, `.gemini/`, `.pre-commit-config.yaml` point into `.leafcutter/`
- `scripts/` and `config/` are clean (no leafcutter files)
- Pre-commit hooks still work (entry paths updated to `.leafcutter/scripts/...`)

### 3. Update .gitignore

```gitignore
# leafcutter build output — regenerate with: python leafcutter-ai/scripts/build.py
.leafcutter/
```

### 4. Verify

- Run Claude Code — agents should load normally
- Run `git commit --allow-empty -m "test"` — pre-commit hooks should fire
- Run `git status` — no leafcutter noise outside `.leafcutter/`

## Troubleshooting

**Symlinks fail on Windows:**
Set `"shim_strategy": "copy"` in skills_config.json, or enable Developer Mode.

**Pre-commit hooks fail with "file not found":**
The hook entries now reference `.leafcutter/scripts/commit_guardian/...`. If you
see the old paths in `.pre-commit-config.yaml`, delete it and rebuild — the shim
will recreate it with the correct paths.

**Claude Code can't find agents:**
Check that `.claude/agents/` exists as a symlink: `ls -la .claude/agents/`.
If not, run `build.py` again — the shim step recreates it.
