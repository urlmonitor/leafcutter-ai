---
name: add-component
description: >
  Agent-facing wrapper around scripts/add_component.py. Provides a structured
  interface so agents can add a new entry to docs/components.json during a
  workflow without knowing the script path or argument format. Validates the
  entry against the minimum schema before writing and exits non-zero on
  duplicate IDs.
allowed-tools: Bash(python3 scripts/add_component.py *), Read, Bash(git add *)
---

# add-component

Provide an agent-facing interface for appending a new component entry to
`docs/components.json`. Wraps `scripts/add_component.py` so that agents
invoking this skill do not need to know the script path or argument format.

## Inputs

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Unique snake_case component identifier (top-level key in the registry) |
| `name` | yes | Human-readable display name for the component |
| `type` | yes | Component type: `analysis`, `coding`, `documentation`, `infrastructure`, `orchestration`, `review`, or `utility` |
| `description` | yes | Plain-English description (minimum 10 characters) |
| `primary_code` | yes | Repo-relative path(s) to primary source file(s) or directory. Provide as a list when multiple paths apply. |
| `status` | yes | Component lifecycle status: `active`, `planned`, or `reviewed` |
| `detail_ref` | no | Repo-relative path to the architecture doc for this component. Omit when no doc exists yet. |
| `components_json` | no | Override the path to components.json. Defaults to `docs/components.json` relative to the repo root. |

## Pre-flight check

Before invoking the script, confirm the `docs/components.json` file is
readable:

```
Read docs/components.json
```

If the file does not exist, surface a `(status: blocker)` comment to the
supervisor — do NOT create the file manually. The file must be bootstrapped
by the `add_component.py` script on first run.

## Invocation

Call the script with a single Bash command. Map each input field to the
corresponding CLI flag:

```
python3 scripts/add_component.py --id <id> --name <name> --type <type> --description <description> --primary-code <primary_code_path> --status <status>
```

For multiple `primary_code` paths, repeat `--primary-code` for each path:

```
python3 scripts/add_component.py --id <id> --name <name> --type <type> --description <description> --primary-code <path1> --primary-code <path2> --status <status>
```

To include an optional `detail_ref`:

```
python3 scripts/add_component.py --id <id> --name <name> --type <type> --description <description> --primary-code <primary_code_path> --status <status> --detail-ref <detail_ref>
```

**Do NOT** combine flags on a single chained shell command. Each invocation is
one Bash tool call.

Use absolute paths for the script itself when the caller's working directory
is not the repo root:

```
python3 /absolute/path/to/scripts/add_component.py --id <id> ...
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Component added successfully |
| `1` | Validation error (duplicate ID, invalid type, insufficient description length, or missing required field) |

On non-zero exit, capture stdout/stderr and surface a `(status: blocker)`
comment to the supervisor with the error message verbatim.

## Post-invocation

After the script exits 0:

1. Stage the updated file:
   ```
   git add docs/components.json
   ```
   (Or use the absolute path if required by the caller's context.)

2. Verify the entry was written by reading `docs/components.json` and
   confirming the new component ID appears in the top-level keys.

## Error handling

If the script exits non-zero:

- Do NOT modify `docs/components.json` manually to work around the error.
- Do NOT re-run the script with `--force` or similar flags — no such flag
  exists.
- Surface the error verbatim to the caller with a structured `(status: blocker)`
  comment so the supervisor can adjudicate.

Common error causes:

| Error text | Cause | Remediation |
|------------|-------|-------------|
| `Component ID '<id>' already exists` | Duplicate `--id` value | Use a unique `id`; do not re-add an existing component |
| `type must be one of ...` | Invalid `--type` value | Use one of the eight allowed enum values listed under Inputs |
| `description must be at least 10 characters` | Too-short description | Provide a fuller description string |
| `primary-code path does not exist` | Bad path argument | Check the repo-relative path is correct |

## Invariants

- **Never** hand-edit `docs/components.json`. Always invoke this skill.
- **Never** pass `--components-json` to a path outside the repo unless
  explicitly authorised by the ticket's acceptance criteria.
- **Never** chain this Bash call with other commands using `&&`, `;`, or
  `||` — the shell convention requires each Bash call to be a single
  command.
- The script is idempotent for zero-state (non-existent component ID);
  it is NOT idempotent for duplicate IDs — it exits 1 rather than silently
  skipping.
