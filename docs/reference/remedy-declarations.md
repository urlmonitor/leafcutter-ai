---
title: 'Reference: Remedy Declarations for Commit Checks'
type: reference
status: active
created: 2026-10-12
last_updated: 2026-10-12
components:
- commit_guardian
- precommit_hooks
related_docs:
- docs/architecture/components/commit-guardian.md
- docs/acceptance-criteria/guardrail-engine/GE-132-checks-say-what-happens-next/GE-132a-1.yaml
- templates/scripts/commit_guardian/README.md
description: 'Lookup for the GE-132a-1 remedy declaration: which commit checks need one, where it lives, how the shared loader finds it, and the three refusals check-hook-parity raises.'
---
# Reference: Remedy Declarations for Commit Checks

Lets a reader look up what a remedy declaration is, how `_remedy_declarations.load()` resolves it, and why `check-hook-parity` refuses a commit over it.

## Which checks need a declaration

A check needs one when its `hooks_manifest.hooks` member in `templates/scripts/commit_guardian/commit_guardian.json` has `tier: "judgment"` and `"pre-commit"` in `stages`. The set is derived from the manifest at run time; no hook id is listed in code. Transform-tier and manual-stage hooks are out.

## Where a declaration lives

A declaration is a `rules[]` entry keyed by `hook_id` in `templates/scripts/precommit-autofix.json` (the package seed) or in the local table. An entry counts as a declaration only if it carries a truthy `disposition`.

| Field | Type | Read by loader | Description |
|---|---|---|---|
| `hook_id` | string | required | Registered hook id. A rule whose `hook_id` is not a string makes the table malformed. |
| `disposition` | string | yes | What happens next. Absent or empty means "not declared". |
| `instruction` | string | yes (default `""`) | What the author or agent does. |
| `agent` | string or null | yes | Specialist to engage; `null` when none. |
| `skills` | list of strings | yes (non-list becomes `[]`) | Skills the agent loads. |
| `category`, `model`, `subagent_type`, `description` | string | no | Autofix routing fields; not part of the declaration view. |

`disposition` values used by the seed: `engage-specialist`, `mechanical-autofix`, `author-clears`. The code does not validate the value (any truthy value declares); see Code versus AC.

`blocking_hook_ids` in the same file is a sibling key. The remedy leg does not read it.

## Loader lookup order

`load(hook_id, root=None)` in `templates/scripts/commit_guardian/_remedy_declarations.py`; `root` defaults to the process cwd.

1. Local table: `precommit_autofix_config_path` from `.claude/skills_config.json`, default `.claude/precommit-autofix.json`.
2. Package seed: `templates/scripts/precommit-autofix.json`, else `scripts/precommit-autofix.json` (first that exists).

The first table that declares the hook wins, so a seed declaration fills in for any hook the local table does not declare. A table that does not exist is skipped; a path appearing twice is read once.

Return shape, or `None` when neither table declares the hook:

```json
{
  "hook_id": "check-complexity",
  "disposition": "engage-specialist",
  "instruction": "Cyclomatic complexity violation. Refactor the flagged function to reduce branching.",
  "agent": "python-coder",
  "skills": ["complexity-reduction"],
  "source": "templates/scripts/precommit-autofix.json"
}
```

`source` is `str(path)` of the file that supplied the declaration. Related helpers: `load_tables(root)` returns `[(path, rules)]`, local first; `declared_view(tables)` returns `{hook_id: declaration}`.

## Refusal reasons

`check-hook-parity` runs the leg through `_remedy_registration_parity.run_leg`, called from `check_hook_parity.py` after the three older parity legs. Its manifest member triggers on `scripts/commit_guardian/|templates/scripts/commit_guardian/|templates/commit-guardian/|templates/scripts/precommit-autofix\.json`, so a commit staging only the routing table runs it.

| Reason | Condition | Fix |
|---|---|---|
| (a) No declaration | A gating check is not declared and not on the excused list. | Add a rule with a `disposition` for the hook to `templates/scripts/precommit-autofix.json`. |
| (b) Addition to excused list | An id is in `undeclared_remedy_baseline` but in no parent's list. | Remove it from the list and give the check a declaration. |
| (c) Declaration for an unregistered check | A rule with a `disposition`, in either table, has a `hook_id` not in `hooks_manifest.hooks`. | Remove the declaration or register the check. |

Reason (c) names the table the declaration came from. Reasons (a) and (b) have no declaration to source, so they name the manifest.

## Excused list

`hook_parity.undeclared_remedy_baseline` in `commit_guardian.json` is a list of check ids that were gating and undeclared when the rule landed. A gating check on the list is not refused under (a). It may lose entries and never gain one. The ratchet compares the list with the one in `HEAD` and in every `MERGE_HEAD` line; an id absent from the union of those lists is an addition (reason b). When no parent carries the list (the commit that first seeds it), the ratchet is skipped. When any parent carries it, the working manifest must keep the key: removing it is refused, naming the list as removed. An empty list is allowed.

## Fail-closed behaviour

Unreadable or malformed input raises `RemedyInputError`, which `run_leg` returns as a could-not-check reason instead of violations. `report()` then emits the GE-120 `could_not_check` outcome and exits 2. It is never a pass and never "no declaration". If real violations were also found, the exit is 1.

Inputs that raise: an existing `.claude/skills_config.json` that cannot be read, cannot be parsed, or is not a JSON object; an existing routing table that cannot be read or parsed, or whose `rules` is not a list of objects with string `hook_id`; a canonical manifest that exists but cannot be read, is not UTF-8, is not valid JSON, or has no `hooks_manifest` object; a malformed `hooks_manifest.hooks`; an excused list that is not a list of strings, in the working tree or a parent; git failing to run; a parent manifest that is not valid JSON.

## Code versus AC

Differences between `GE-132a-1.yaml` and the code as it is now:

- Disposition values: the AC names three; the loader accepts any truthy value and does not check membership.
- Ratchet with no parent list: the AC says an id in no parent's list is an addition. The code skips the comparison only for the seeding commit, when no parent has ever carried the list. Once a parent carries it, removing the key is refused.
- Absent canonical manifest: in a consumer install the package's canonical manifest does not exist, so there is no registry to judge. The leg prints that it is not applicable, naming the path, and exits 0. The AC does not state this case.
- Source named in refusals: the AC says every refusal states the declaration's file. Only reason (c) does (see Refusal reasons).

## See also

- Commit guardian hook table: `templates/scripts/commit_guardian/README.md`
- Architecture: `docs/architecture/components/commit-guardian.md`
- Rule: `docs/acceptance-criteria/guardrail-engine/GE-132-checks-say-what-happens-next/GE-132a-1.yaml`
