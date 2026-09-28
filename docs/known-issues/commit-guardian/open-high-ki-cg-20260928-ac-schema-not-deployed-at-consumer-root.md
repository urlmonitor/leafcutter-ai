---
title: "KI-CG-20260928-ac-schema-not-deployed-at-consumer-root — the build deploys config/ac_store_schema.json only under .leafcutter/config/, but check-ac-schema looks for it at <repo root>/config/, so in a consumer install the schema gate always degrades to manual field validation"
description: "medium-high — even from the correct cwd, a consumer install has no <root>/config/ac_store_schema.json, so check-ac-schema prints its 'not found ... falling back to manual field validation' warning on every run and never applies the JSON schema. Verified by reading build_ac_store's core-config loop and check_ac_schema's loader on main at 8ed47463. The consumer-run warning is session observation."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - commit_guardian
  - build_pipeline
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260914-ac-hooks-resolve-root-from-cwd.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-012-check-ac-schema-reports-a-clean-pass-on.md
---

# KI-CG-20260928-ac-schema-not-deployed-at-consumer-root — the build deploys config/ac_store_schema.json only under .leafcutter/config/, but check-ac-schema looks for it at <repo root>/config/, so in a consumer install the schema gate always degrades to manual field validation

- **Severity:** medium-high. A silent downgrade. The hook still runs its manual field checks and prints a warning, so it is not a vacuous pass. But the JSON schema, which is the rule set the store is defined by, is never applied in any consumer repository.
- **Status:** open. No AC.
- **Occurrences:** 1 (fresh consumer install, 2026-09-27/28; session observation). Not reproduced on this machine: no consumer install with a built `.leafcutter/` was found to re-run it against. The mechanism below is from reading the code.
- **First seen:** 2026-09-28 · **Last seen:** 2026-09-28
- **Where:** `scripts/build_phases_ac_store.py:450-471` (the core-config deploy loop in `build_ac_store`) · `scripts/commit_guardian/check_ac_schema.py:91` (`SCHEMA_PATH = "config/ac_store_schema.json"`), `:524-541` (`_load_schema`), `:660-667` (root and warning)

## Symptom (session observation)

Committing from the root of a fresh consumer install, as `.pre-commit-config.yaml` runs it:

```text
WARNING: config/ac_store_schema.json not found at <consumer root>; falling back to manual field validation.
```

## Mechanism (verified in code, main 8ed47463)

**Write side.** `build_ac_store(target_root, ...)` states that *"`target_root` IS the output root (`.leafcutter/` by default)"* (`build_phases_ac_store.py:235`). Its core-config loop writes `target_root / "config" / core_config_name` for `ac_store_schema.json`, `agent_registry.json`, `doc_types.json`, `diagram_types.json`, `skill_registry.json`, `guardrail_gates.yaml` and `paths.json` (`:450-465`). In a consumer install the schema therefore lands at `<consumer>/.leafcutter/config/ac_store_schema.json` and nowhere else.

**Read side.** `check_ac_schema.main()` takes `root = HOOK_ROOT or Path.cwd()` (`:660`) and loads `root / "config/ac_store_schema.json"` (`:533`). Nothing in the deployed hook path sets `HOOK_ROOT` (`run_hook.py` does not). pre-commit runs hooks from the repository root. So `root` is `<consumer>`, the file is `<consumer>/config/ac_store_schema.json`, it does not exist, and `_load_schema` returns `None`.

**Why the self-hosting repo does not show it.** In leafcutter-ai itself, `config/ac_store_schema.json` is the source file at the repo root, so the lookup succeeds. The defect only appears where source and deploy are different trees, which is every adopter.

**Not the same as `KI-CG-20260914-ac-hooks-resolve-root-from-cwd`.** That entry is about running from the wrong cwd. The fix it proposes (route the six AC hooks through `find_project_root()`) resolves the git toplevel, which here is the consumer root, where the file still does not exist. Fixing that entry does not fix this one.

## Detection

In a consumer repository: `ls config/ac_store_schema.json .leafcutter/config/ac_store_schema.json`. Only the second exists. Any `check-ac-schema` run that prints the `falling back to manual field validation` line from the repository root is this defect.

## Workaround

Run the hook with `HOOK_ROOT=<consumer>/.leafcutter`. That loads the schema, but it also moves the staged-file lookup, so confirm the file count is non-zero before trusting a pass (see `KI-CG-20260914-ac-hooks-resolve-root-from-cwd`'s recipe). Copying the schema to `<consumer>/config/` also works, but it is a hand-maintained copy that will go stale.

## Suggested fix

1. Resolve the schema relative to the hook's own deployed location (`Path(__file__).resolve().parents[2] / "config" / ...`), falling back to `<root>/config/` for the self-hosting layout. The schema then comes from the same install as the hook.
2. Make a missing schema fail closed (exit non-zero, naming both paths it tried) rather than degrading. A gate that cannot load its rules has not passed. `KI-CG-20260914-ac-hooks-resolve-root-from-cwd` suggests the same second arm.
3. Check the other readers of the same core-config loop for the same split: anything that reads `config/agent_registry.json`, `config/doc_types.json` or `config/paths.json` relative to the repository root rather than to its own install. Not audited here.

**Pattern:** the build and the reader each use a sensible root, but not the same one, and the reader degrades quietly when the file is missing. In the one repository where both roots coincide, nobody sees it.
