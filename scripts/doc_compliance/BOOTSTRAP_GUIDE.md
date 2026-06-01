# Documentation Compliance — Bootstrap Guide

> **Purpose:** This guide walks an AI agent or developer through adopting the
> `scripts/doc_compliance/` package in a new project. It covers both the
> portability configuration (`scripts/doc_compliance/doc_compliance.json`) and
> the two foundational JSON files that power the compliance scanner
> (`docs/doc_compliance.json` and `docs/components.json`).
> Follow each step in order. The output should be 80–100% accurate after a single pass.

## Portability Configuration

`scripts/doc_compliance/` is a portable package. All project-specific values
(scan paths, component discovery patterns, project name) are stored in a single
JSON config file: **`scripts/doc_compliance/doc_compliance.json`**.

When this file is absent or a key is missing, the package falls back to
Bybit-Trader defaults — existing Bybit-Trader behaviour is fully preserved without
any changes to the Python source.

### Configuration Keys

| Key | What it controls | Bybit-Trader default |
|-----|-----------------|---------------------|
| `config_file` | Path (relative to project root) of the per-project scanner config | `docs/doc_compliance.json` |
| `components_file` | Path (relative to project root) of the component registry | `docs/components.json` |
| `bootstrap_project_name` | `project` field written by `--bootstrap` | `bybit-trader` |
| `bootstrap_scan_paths` | `scan_paths` dict written by `--bootstrap` | `{"python": ["collector/", "models/", ...], "sql": ["sql_functions/"], "docs": ["docs/"]}` |
| `bootstrap_component_sources` | `component_sources` array written by `--bootstrap` | Bybit-specific glob patterns |
| `bootstrap_standalone_components` | `standalone_components` array written by `--bootstrap` | `[{"file": "database_manager.py", ...}]` |
| `bootstrap_ignore` | `ignore` list written by `--bootstrap` | `["__pycache__", "alembic/", "unit_tests/", ...]` |

### Adopting in a new project

1. Copy `scripts/doc_compliance/` into your repo.
2. Create `scripts/doc_compliance/doc_compliance.json` with your project values:

```json
{
  "bootstrap_project_name": "my-project",
  "bootstrap_scan_paths": {
    "python": ["src/"],
    "sql": [],
    "docs": ["docs/"]
  },
  "bootstrap_component_sources": [],
  "bootstrap_standalone_components": [],
  "bootstrap_ignore": ["__pycache__", "venv/", ".venv/"]
}
```

3. Run `python scripts/doc_compliance/cli.py --bootstrap` — the output will use your project values.
4. Proceed with the scanner config creation steps below.

---

> **Original guide content below.** The original creation steps for the scanner config
> and component registry remain unchanged.

---
>
> **Design rationale:** This guide separates two concerns (following industry best practices from Backstage, SonarQube, ESLint, and TypeScript):
> - **Scan paths** (broad) — "Which directories should be checked for compliance violations?"
> - **Component sources** (narrow) — "Which patterns produce architectural component candidates?"

## Choosing Between `--init` and `--bootstrap`

| Flag | Behaviour | When to use |
|------|-----------|-------------|
| `--init` | Emits a blank skeleton with empty arrays and inline comments; no guessing, no project assumptions | Starting fresh in a new project with no existing folder structure to scan, or when you want full control over every path |
| `--bootstrap` | Scans the current folder tree and guesses project-specific paths; output is a draft rich with project defaults | Starting in an existing project where you want a quick draft that's already populated with likely paths |

**Recommended flow for brand-new projects:**

1. `python scripts/doc_compliance_scanner.py --init` — creates a blank `docs/doc_compliance.json`
2. Edit the file by hand or with AI guidance (see `instructions.md`)
3. `python scripts/doc_compliance_scanner.py --discover-components` — populate `docs/components.json`

**Recommended flow for existing projects:**

1. `python scripts/doc_compliance_scanner.py --bootstrap` — creates a pre-populated draft
2. Review and tailor the draft (the bootstrap is always project-specific)
3. `python scripts/doc_compliance_scanner.py --discover-components`

---

## What You're Creating

| File | Purpose | Consumers |
|------|---------|-----------|
| `docs/doc_compliance.json` | Tells the scanner WHERE to look and HOW to interpret the project | Compliance scanner (ongoing) |
| `docs/components.json` | Lists every logical building block of the system | Component registry, knowledge graph |

---

## PHASE 1: Create `docs/doc_compliance.json`

This file is the scanner's permanent configuration. It defines two separate scopes:

```
scan_paths ──────────── BROAD: "Check these files for violations"
                        (headers, frontmatter, doc links)
                        Changes rarely — only when new top-level dirs are added.

component_sources ───── NARROW: "Discover components using these patterns"
                        Architectural — changes when you restructure modules.
```

### Step 1.1 — Classify the Project Layout

Read the top-level directory listing. Classify each directory into one of these categories:

| Category | What it contains | Examples |
|----------|-----------------|----------|
| `source_code` | Business logic, workers, engines | `collector/`, `live_trader/`, `trading/` |
| `models` | ORM models, data classes, schemas | `models/`, `schemas/` |
| `sql` | Database functions, procedures, views, triggers | `sql_functions/`, `database/` |
| `docs` | Documentation files | `docs/`, `adr/`, `architecture/` |
| `config` | App config, settings | `config/`, `settings.py` |
| `infra` | Docker, CI/CD, deployment | `docker/`, `.github/`, `scripts/` |
| `tests` | Unit tests, integration tests | `unit_tests/`, `tests/` |
| `ignore` | Cache, build artifacts, legacy, IDE | `__pycache__/`, `.venv/`, `legacy/` |

**ACTION:** List each top-level directory and assign its category. Skip `ignore`.

---

### Step 1.2 — Define Scan Paths (BROAD)

`scan_paths` tells the compliance scanner which directories to check for violations. Every file under these paths will be examined for correct headers, frontmatter, and doc links.

**Rules:**
- Include ALL directories that contain code or documentation you want checked
- Group by language: `python`, `sql`, `docs`
- This is broad — you're casting a net, not defining components

**ACTION:** From your Step 1.1 classification, add every `source_code`, `models`, `sql`, and `docs` directory:

```json
"scan_paths": {
  "python": ["collector/", "models/", "trading/", "utils/", ...],
  "sql": ["sql_functions/"],
  "docs": ["docs/", "adr/"]
}
```

**Verification:** Ask yourself — "Is there any directory with `.py`, `.sql`, or `.md` files that I care about but didn't include?" If yes, add it.

---

### Step 1.3 — Define Component Sources (NARROW)

`component_sources` tells the discovery engine where to look for architectural components. This is more specific than scan_paths — not every scanned file is a component.

For each `source_code` directory, answer:

1. **Is it a directory of subdirectories?** (e.g., `collector/services/candle_context/`)
   → Each subdirectory is likely a separate component
   → Pattern: `"collector/services/*/"`, `name_from: "folder"`

2. **Is it a flat directory of files?** (e.g., `models/candles.py`, `models/trades.py`)
   → Each file represents one entity
   → Pattern: `"models/*.py"`, `name_from: "filename"`
   → Consider an `exclude` list for utility files (`__init__.py`, `base.py`, `*_type.py`)

3. **Is it a single cohesive module?** (e.g., `analytics/` has one purpose)
   → The entire directory is one component
   → Pattern: `"analytics/"`, `name_from: "folder"`

4. **Does it have a mixed structure?** (e.g., `live_trader/` has `main.py` + subdirectories)
   → The root is the component; subdirectories are sub-components
   → Pattern: `"live_trader/"`, `name_from: "folder"`

**ACTION:** For each source_code directory, write one `component_sources` entry:
```json
{ "pattern": "<glob>", "type": "<component_type>", "name_from": "<strategy>" }
```

**Also check for standalone components** — important root-level files that don't fit any directory pattern:
- A single large file that acts as a module (e.g., `database_manager.py`)
- Config entry points (e.g., `app_launcher.py`, `settings.py`)

Add these to a separate `standalone_components` array:
```json
{ "file": "database_manager.py", "type": "infrastructure", "name": "database_manager" }
```

**Component types** (pick the most fitting):
- `service` — Background worker or scheduled process
- `data_pipeline` — Ingests, transforms, stores data
- `data_table` — A database table/entity
- `engine` — Real-time processing logic
- `utility` — Shared helpers, tools
- `infrastructure` — Docker, DB, CI/CD
- `model` — ML/AI pipeline
- `api_integration` — External API client

**name_from strategies:**
- `"folder"` — Component name = directory name (e.g., `candle_context/` → `candle_context`)
- `"filename"` — Component name = filename without extension (e.g., `trades.py` → `trades`)
- `"class"` — Component name = first class name in the file (requires parsing)

---

### Step 1.4 — Define Documentation Conventions

Answer:
1. Where do documentation files live? (→ already captured in `scan_paths.docs`)
2. What pattern do code file headers use? (Look for `MODULE:`, `"""Module:`, or similar)
3. What pattern do SQL file headers use? (Look for `Object Name:`, `-- Function:`, or similar)

**ACTION:** Set `code_header_pattern` and `sql_header_pattern`. Verify each pattern by checking at least one real file.

---

### Step 1.5 — Define Ignore Patterns

List directories and file patterns that should NEVER be scanned:
- Test directories, caches, virtual environments
- Build artifacts, IDE configs
- Legacy/deprecated code (if isolated in its own directory)

---

### Step 1.6 — Assemble `docs/doc_compliance.json`

```json
{
  "$schema": "doc-compliance-config-v1",
  "project": "<project_name>",

  "scan_paths": {
    "python": ["<every dir with .py files you care about>"],
    "sql": ["<every dir with .sql files>"],
    "docs": ["<every dir with .md documentation>"]
  },

  "component_sources": [
    // One entry per pattern from Step 1.3
  ],

  "standalone_components": [
    // Root-level files that are components but don't fit a glob pattern
  ],

  "code_header_pattern": "MODULE:",
  "sql_header_pattern": "Object Name:",

  "ignore": [
    "__pycache__", ".venv/", ".git/", "alembic/",
    "unit_tests/", "debugging/", "legacy/", ".pytest_cache/"
  ]
}
```

### ✅ Quality Checklist for `doc_compliance.json`

**Scan Paths:**
- [ ] Every directory with `.py` files is in `scan_paths.python`
- [ ] Every directory with `.sql` files is in `scan_paths.sql`
- [ ] Every directory with `.md` docs is in `scan_paths.docs`
- [ ] No `ignore` directories accidentally appear in scan_paths

**Component Sources:**
- [ ] Every `source_code` directory has at least one `component_sources` entry
- [ ] `component_sources` is a SUBSET of `scan_paths` (never broader)
- [ ] Standalone root-level files that act as modules are in `standalone_components`

**Conventions:**
- [ ] `code_header_pattern` matches at least one existing file header (verify!)
- [ ] `sql_header_pattern` matches at least one existing SQL header (verify!)

---

## PHASE 2: Create `docs/components.json`

Now that you know WHERE to look (from `component_sources`), you can discover the actual components.

### Step 2.1 — Discovery: Walk Each Component Source

For EACH `component_sources` entry in your config:

1. **Resolve the glob pattern** → list all matching directories/files
2. **For each match**, determine:
   - `name`: The component ID (snake_case, from `name_from` strategy)
   - `display_name`: Human-readable name (Title Case)
   - `description`: 1-2 sentence elevator pitch (read the README.md or module docstring)
   - `type`: From the component_sources entry
   - `detail_ref`: Path to the most informative doc or README for this component
   - `primary_code`: List of primary code paths
   - `status`: `"active"` unless clearly deprecated

### Step 2.2 — Enrichment: Read READMEs and Docstrings

For each discovered component:
1. Check if the directory has a `README.md` → extract the first paragraph as `description`
2. If no README, check the main `.py` file's module docstring → extract summary
3. If neither exists, write "TODO: Add description" and flag for review

### Step 2.3 — Identify Relationships

For each component:
1. **`contains`** — What sub-modules exist inside this component?
   - List only if the component is a directory with meaningful subdirectories
   - Sub-components are NOT separate registry entries

2. **`depends_on`** — What other components does this one import/use?
   - Read the main file's imports → map imported modules to other components
   - Only list dependencies on OTHER components, not standard library or third-party

3. **`owners`** — Which top-level module "owns" this component?
   - Usually the parent directory (e.g., `collector`, `live_trader`)

### Step 2.4 — Apply the Component vs Sub-Component Test

For each discovered item, ask:

| Question | YES → Component | NO → Sub-component |
|----------|-----------------|---------------------|
| Can it be deployed/tested/deprecated independently? | ✅ | ❌ |
| Would you talk about it in a meeting as a separate thing? | ✅ | ❌ |
| Does it have its own documentation file? | ✅ | ❌ |
| Does it introduce a new database table? | ✅ | ❌ |
| Removing it would change the architecture diagram? | ✅ | ❌ |

If 3+ answers are YES → it's a **component** (gets a registry entry)
If 2 or fewer → it's a **sub-component** (listed in parent's `contains` array)

### Step 2.5 — Type-Specific Fields

Add conventional fields based on the component type:

| Type | Extra Fields |
|------|-------------|
| `data_table` | `table_name`, `model_ref` (path to ORM model) |
| `data_pipeline` | `data_tables` (list of tables it reads/writes) |
| `service` | `entry_point` (path to worker/main file) |
| `engine` | (none required) |
| `infrastructure` | `docker_service` (name in docker-compose) |

### Step 2.6 — Assemble `docs/components.json`

```json
{
  "$schema": "component-registry-v1",
  "project": "<project_name>",
  "version": "1.0.0",
  "components": {
    "<component_id>": {
      "name": "<Human Readable Name>",
      "description": "<1-2 sentence elevator pitch>",
      "type": "<type>",
      "detail_ref": "<path/to/main/doc>",
      "contains": [],
      "primary_code": [],
      "owners": [],
      "depends_on": [],
      "status": "active",
      "created": "YYYY-MM-DD"
    }
  }
}
```

### ✅ Quality Checklist for `components.json`
- [ ] Every component has a non-empty `description` (no "TODO" left)
- [ ] Every `detail_ref` path exists on disk
- [ ] Every `primary_code` path exists on disk
- [ ] No duplicate component names or overlapping aliases
- [ ] Sub-components are in `contains` arrays, NOT as separate entries
- [ ] `depends_on` references only other registered components
- [ ] At least 15 components for a medium-sized project (red flag if < 10 or > 40)
- [ ] Component vs Sub-component test was applied to every entry

---

## PHASE 3: Validation

After creating both files, run these checks:

### 3.1 — Path Validation
For every path referenced in both JSON files:
```bash
# Verify all detail_ref paths exist
# Verify all primary_code paths exist
# Verify all doc_paths exist
```

### 3.2 — Coverage Check
- Does every `source_code` directory have at least one component mapped to it?
- Are there any directories with code files that aren't covered by any scan_path?
- `component_sources` should be a strict subset of `scan_paths` — verify!

### 3.3 — Cross-Reference
- Does every component's `detail_ref` actually mention the component?
- Do `depends_on` references form a reasonable graph? (some cycles OK, but a component depending on everything is suspicious)

---

## Common Mistakes to Avoid

| ❌ Mistake | ✅ Correct Approach |
|-----------|---------------------|
| Putting everything in `component_sources` | `scan_paths` = broad net. `component_sources` = specific patterns. A standalone SQL file needs scanning but isn't a component. |
| Registering every Python file as a component | Only register logical units with their own lifecycle |
| Using vague descriptions like "handles data" | Be specific: "Enriches 1-minute candles with multi-timeframe confluence signals" |
| Setting `detail_ref` to a non-existent file | Verify the path exists; create a stub doc if needed |
| Listing test files in `primary_code` | Tests belong in `unit_tests/`, not in component metadata |
| Creating a component for every database table | Only if the table is a first-class concept (not just a join table) |
| Over-nesting in `contains` | `contains` is flat — just list the sub-component names |
| Forgetting standalone root-level files | Files like `database_manager.py` need `standalone_components` entries |
