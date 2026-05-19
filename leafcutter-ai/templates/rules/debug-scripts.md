---
trigger: always_on
---

# Debug Scripts — Rules

## 1. SEARCH BEFORE CREATE (Mandatory)
Before creating ANY new debug script, you MUST first search for existing ones using the `debug-script-manager` skill:

```bash
python .agents/skills/debug-script-manager/scripts/search_debug_scripts.py --search "<keyword>"
```

If a matching script exists:
- **In a categorized folder** → Reuse or modify it.
- **In `_legacy/`** → Migrate it first (add tags, move to correct subfolder), then modify.

## 2. Location & Structure
- **NEVER** create debug scripts in the project root.
- All debug scripts go in `debugging/scripts/<category>/` where category is one of:
  `check`, `fix`, `deploy`, `benchmark`, `export`, `verify`, `analyze`, `backfill`, `cleanup`, `misc`
- All debug output/logs go in `debugging/logs/`.
- Test/evaluation scripts go in `/unit_tests/` (for automated tests) or `debugging/scripts/` (for manual tests).

## 3. Metadata Tags (Required)
Every new debug script MUST include metadata tags in its header. The `check-debug-scripts` pre-commit hook will **block** commits without them.

**Required tags:**
- `DEBUG SCRIPT:` — Name of the script
- `CATEGORY:` — Must match the subfolder
- `DESCRIPTION:` — What the script does

**At least one context tag:**
- `TABLES:` — DB tables touched
- `FUNCTIONS:` — SQL functions/procedures
- `WORKERS:` — Python workers
- `SYMBOLS:` — Trading symbols

See `debugging/scripts/README.md` for format examples per language (Python, SQL, Bash).

## 4. Legacy Migration
When reusing a script from `_legacy/`:
1. Add the metadata header to it.
2. Move it to the correct `debugging/scripts/<category>/` subfolder.
3. Update any hardcoded paths if needed.

## 5. Scaffold New Scripts
Use the skill's scaffold command to create properly tagged scripts:
```bash
python .agents/skills/debug-script-manager/scripts/search_debug_scripts.py \
  --scaffold --name <name> --category <cat> --type <py|sql|sh> \
  --description "<description>" --tables "<tables>"
```

**AI Self-Enforcement Pledge:**
- **I will ALWAYS search before creating a new debug script.**
- **I will NEVER create debug scripts in the project root.**
- **I will ALWAYS include metadata tags in debug script headers.**
- **When reusing a `_legacy/` script, I will migrate it first.**
