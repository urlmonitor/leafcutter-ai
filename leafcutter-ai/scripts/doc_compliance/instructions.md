# AI Prompt for Configuring Doc Compliance

## Starting Point: `--init` vs `--bootstrap`

You have two ways to generate the initial `docs/doc_compliance.json`:

- **`--init`** — produces a blank skeleton with empty `scan_paths`, `component_sources`, and `standalone_components` arrays, plus a `# REVIEW` comment style inline. Use this when starting from scratch or when you want to fill in every field explicitly. After running `--init`, use the prompt below to guide an AI agent to populate `scan_paths`, `component_sources`, and `standalone_components`.

- **`--bootstrap`** — scans the folder tree and generates a draft populated with project-guessed defaults. Use this when an existing project is being onboarded.

Either way, the prompt below applies once the blank or draft config exists.

---

After running `--bootstrap` or `--init`, the scanner generates a `docs/doc_compliance.json`. Because every project's architecture is unique, the `component_sources` (how to auto-discover components) need to be tailored to your repository.

Instead of figuring this out manually, copy the prompt below and provide it to your AI coding assistant (e.g. Cursor, Copilot, or Gemini) while giving it access to your codebase context.

---

## The Prompt

```text
I am setting up a documentation compliance scanner for my project. The scanner requires a `docs/doc_compliance.json` configuration file to know where to look for documentation violations and how to discover architectural components. 

I have already run the bootstrap command, which generated a draft `docs/doc_compliance.json`.

Please review my project's directory structure and purpose, and update the draft `docs/doc_compliance.json` with project-specific rules:

1. Update `scan_paths`: Ensure it includes every top-level directory that contains code or documentation files that should be checked for compliance.
2. Update `ignore`: Ensure all build artifacts, virtual environments, caches, and legacy folders are excluded.
3. Update `component_sources` (CRITICAL): Replace the boilerplate examples with the actual architectural patterns of my project. A component source should define how to discover logical components. 
   - Example 1: If I have a folder `src/services/` where each subfolder is a distinct service, add a pattern: `{"pattern": "src/services/*/", "type": "service", "name_from": "folder", "description": "..."}`. 
   - Example 2: If I have data models at `db/models/*.py`, add a pattern: `{"pattern": "db/models/*.py", "type": "data_table", "name_from": "filename", "exclude": ["__init__.py"]}`.
4. Update `standalone_components`: Add any central singleton files that act as their own components (e.g., a central `app_launcher.py` or `database_manager.py`).

Output the fully corrected and finalized `docs/doc_compliance.json` so I can proceed to component discovery.
```
