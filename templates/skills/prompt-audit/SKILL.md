---
name: prompt-audit
description: >-
  Audit agent templates and skill files against the Prompt-Quality Checklist.
  Detects violations: compound bash commands, tool allowlist mismatches,
  missing signoff protocol, missing spawn_allowlist. Reports structured findings.
allowed-tools: Bash, Read
portable: true
---

# prompt-audit

This skill systematically audits agent template files and skill files against
the Prompt-Quality Checklist. It performs six detection checks and returns a
structured findings report so `llm-expert` can address violations methodically.

The skill is **read-only** — it does not modify any file it audits.

---

## When to Invoke

`llm-expert` invokes this skill when it needs to:

- Validate a newly created or modified agent template before submitting it.
- Perform a batch audit of all templates in `templates/agents/`.
- Check a specific skill file for convention violations.
- Produce a structured findings report for user review.

### Invocation pattern

```
Load this skill, then for each file to audit:
  result = run_audit(file_path)
  collect results into batch_report
```

Pass the target file path explicitly. Do not glob — let `llm-expert` control
which files are in scope.

---

## Audit Checks

### Check 1 — Frontmatter Schema Validation

Verify that all required frontmatter fields are present and valid.

**Required fields for agent templates:**

| Field | Required | Valid values |
|-------|----------|-------------|
| `name` | Yes | Non-empty string matching filename stem |
| `description` | Yes | Non-empty string |
| `model` | Yes | `claude-opus`, `sonnet`, `claude-opus-mini`, `opus`, `haiku` |
| `tools` | Yes | Non-empty comma-separated list or YAML array |
| `portable` | Yes | Boolean (`true` or `false`) |
| `signoff` | Conditional | Boolean; required when agent is a phase agent |

**Required fields for skill files:**

| Field | Required | Valid values |
|-------|----------|-------------|
| `name` | Yes | Non-empty string matching directory name |
| `description` | Yes | Non-empty string |
| `allowed-tools` | Yes | Non-empty comma-separated list or YAML array |

**Detection steps:**

1. Read the file and extract the YAML frontmatter block (between `---` delimiters).
2. Parse the YAML and check for each required field.
3. Validate field values against the table above.
4. Flag any missing or invalid field as an `error`.

**Severity:** `error` for missing required fields, `warning` for unrecognized
model values or empty tool lists.

---

### Check 2 — Tool Allowlist vs Body Usage

Cross-reference the declared tool allowlist against tools actually referenced
in the template body.

**Detection steps:**

1. Extract the declared tools from frontmatter (`tools:` for agents,
   `allowed-tools:` for skills).
2. Scan the template body for tool invocation patterns:
   - Direct mentions: `Bash`, `Read`, `Edit`, `Write`, `Agent`, `WebSearch`,
     `WebFetch`, `TodoRead`, `TodoWrite`.
   - Contextual mentions: `"Bash tool"`, `"Read tool"`, `"use the Agent tool"`.
   - Sub-agent spawn language: `"spawn"`, `"invoke"`, `"via the Agent tool"`.
3. Compare the two sets:
   - **Undeclared tool used**: tool mentioned in body but not in allowlist →
     severity `error`.
   - **Overly permissive allowlist**: tool in allowlist never mentioned in body →
     severity `warning` (may be intentional for future use; do not block).

**Notes:**
- `Bash` declarations may appear as `Bash(*)` or `Bash(<subcommand>)` — treat
  all `Bash` variants as the same tool.
- Comments and code blocks should still be scanned — a tool in a code block is
  a usage signal.

---

### Check 3 — Compound Bash Detection

Scan Bash tool descriptions and inline bash code blocks for compound command
patterns that violate the "one command per Bash call" convention.

**Patterns to detect:**

| Pattern | Example | Severity |
|---------|---------|---------|
| ` && ` operator | `git add . && git commit` | `error` |
| `; ` semicolon chain | `cd /path; python script.py` | `error` |
| ` \|\| ` operator | `command1 \|\| command2` | `error` |
| `cd <path> &&` | `cd /project && make build` | `error` |
| Side-effect pipe | `ls \| rm -rf` | `error` |
| Read-only pipe | `git log \| grep fix` | `warning` |

**Detection steps:**

1. Locate all Bash command descriptions in the template body. These appear as:
   - Inline code: `` `git add . && commit` ``
   - Fenced code blocks labeled `bash` or `sh`.
   - Descriptions of Bash tool calls (prose paragraphs referencing bash commands).
2. Apply the pattern table above to each located command string.
3. For each match, record:
   - `line_number`: 1-indexed line in the file.
   - `description`: the matched pattern and the offending text snippet (≤ 60 chars).
   - `suggested_fix`: "Split into two separate Bash tool calls."
4. Report side-effect pipes as `error`, read-only pipes (grep, head, tail, wc,
   sort, uniq) as `warning`.

---

### Check 4 — Signoff Protocol Validation

If the agent template declares `signoff: true`, verify that the signoff
protocol section exists and is well-formed.

**Detection steps:**

1. Check frontmatter: if `signoff: true` is absent or `false`, skip this check
   (emit `N/A` for this check in the report).
2. Search for the `## Sign-off` or `## Sign-offs` heading in the body.
3. If the heading is absent: severity `error`.
4. If the heading is present, check for:
   - At least one `- [ ] <agent-name>` checkbox line (agent has signoff tasks).
   - The instruction to load `signoff/SKILL.md`.
5. If any sub-check fails: severity `warning`.

---

### Check 5 — spawn_allowlist Validation

If the agent template declares or uses the `Agent` tool (spawning sub-agents),
verify that `spawn_allowlist` is declared in the frontmatter.

**Detection steps:**

1. Check if `Agent` appears in the declared tools list.
2. Scan the body for spawn language: "spawn", "invoke", "via the Agent tool",
   `Agent(`, `subagent_type`.
3. If either condition is true, check for `spawn_allowlist:` in the frontmatter.
4. If `spawn_allowlist` is absent: severity `error`.
5. If `spawn_allowlist` is present:
   - Verify it is a YAML list (not a bare string).
   - Check that each entry is a non-empty string (no validation against the
     registry — `llm-expert` performs that separately).
   - If malformed: severity `warning`.

---

### Check 6 — Stop-and-Ask Rules

If the agent has scope boundaries (e.g. "python-coder should not edit SQL files"),
verify that stop-and-ask rules are documented in the template body.

**Detection steps:**

1. Scan the body for scope-boundary signals:
   - Agent name contains a file-type qualifier: `python-coder`, `sql-coder`,
     `frontend-coder`.
   - Body contains phrases like "do not edit", "do not modify", "only edits",
     "restricted to", "out of scope".
2. If scope-boundary signals are present, check for stop-and-ask language:
   - "Stop and defer to", "do not proceed", "ask the user", "stop and ask",
     "escalate to".
3. If boundary signals found but no stop-and-ask language: severity `warning`.
4. If no boundary signals found: skip this check (emit `N/A`).

---

## Audit Report Format

After running all applicable checks, return a structured report as a Python dict
(or equivalent JSON object). The report schema:

```python
{
  "template_name": str,           # value of name: field from frontmatter, or filename if absent
  "file_path": str,               # absolute path of the audited file
  "frontmatter_valid": bool,      # Check 1 passed
  "tool_allowlist_valid": bool,   # Check 2 passed (no undeclared tools used)
  "no_compound_bash": bool,       # Check 3 passed
  "signoff_protocol_valid": bool | None,   # Check 4 result; None if N/A
  "spawn_allowlist_valid": bool | None,    # Check 5 result; None if N/A
  "stop_and_ask_valid": bool | None,       # Check 6 result; None if N/A
  "violations": [
    {
      "check_name": str,          # e.g. "compound_bash_detection"
      "severity": str,            # "error" or "warning"
      "line_number": int,         # 1-indexed
      "description": str,         # human-readable explanation
      "suggested_fix": str        # optional; empty string if none
    }
  ],
  "passed_checks": [str],         # list of check names that produced no errors
  "recommendations": [str],       # improvement suggestions beyond violations
  "summary": {
    "total_violations": int,
    "total_errors": int,
    "total_warnings": int
  }
}
```

**Violations are sorted by line_number ascending.**

`passed_checks` includes the check name only when it ran and produced zero
violations (not when it was skipped as N/A).

---

## Running an Audit

### Single file audit

To audit one template:

```bash
# 1. Read the target file
cat /absolute/path/to/templates/agents/some-agent.md
```

Then apply each check in order (1 → 6), collect violations, and assemble the
report dict.

### Batch audit

To audit all agent templates:

```bash
# 1. List all template files
find /absolute/path/templates/agents -name "*.md" -type f
```

Then run the single-file audit for each path and collect results into a list of
report dicts. Sort the batch by `total_errors desc, total_warnings desc` so the
most problematic files appear first.

### Invoking individual checks

`llm-expert` may request a specific check only. In that case, run only the
named check and return a partial report with only the relevant fields populated.
All other boolean fields default to `true` (not assessed) and `violations`
contains only entries from the run check.

---

## Severity Reference

| Severity | Meaning | Action for `llm-expert` |
|----------|---------|------------------------|
| `error` | Convention violation that must be fixed before the template can be used | Flag to user; block the template from being marked `done` |
| `warning` | Style issue or potential problem; does not block usage | Surface to user as improvement opportunity |

---

## Examples

### Example 1 — Clean template (no violations)

```
{
  "template_name": "python-coder",
  "file_path": "/path/templates/agents/python-coder.md",
  "frontmatter_valid": true,
  "tool_allowlist_valid": true,
  "no_compound_bash": true,
  "signoff_protocol_valid": true,
  "spawn_allowlist_valid": true,
  "stop_and_ask_valid": null,
  "violations": [],
  "passed_checks": [
    "frontmatter_schema",
    "tool_allowlist",
    "compound_bash",
    "signoff_protocol",
    "spawn_allowlist"
  ],
  "recommendations": [],
  "summary": {
    "total_violations": 0,
    "total_errors": 0,
    "total_warnings": 0
  }
}
```

### Example 2 — Template with compound bash and missing spawn_allowlist

```
{
  "template_name": "my-agent",
  "file_path": "/path/templates/agents/my-agent.md",
  "frontmatter_valid": true,
  "tool_allowlist_valid": true,
  "no_compound_bash": false,
  "signoff_protocol_valid": true,
  "spawn_allowlist_valid": false,
  "stop_and_ask_valid": null,
  "violations": [
    {
      "check_name": "compound_bash_detection",
      "severity": "error",
      "line_number": 42,
      "description": "Compound command detected: 'cd /project && python build.py'",
      "suggested_fix": "Split into two separate Bash tool calls."
    },
    {
      "check_name": "spawn_allowlist_validation",
      "severity": "error",
      "line_number": 0,
      "description": "Agent uses the Agent tool (spawn sub-agents) but has no spawn_allowlist in frontmatter.",
      "suggested_fix": "Add spawn_allowlist: [<agent-names>] to the frontmatter."
    }
  ],
  "passed_checks": [
    "frontmatter_schema",
    "tool_allowlist",
    "signoff_protocol"
  ],
  "recommendations": [
    "Consider adding a stop-and-ask rule for out-of-scope file types."
  ],
  "summary": {
    "total_violations": 2,
    "total_errors": 2,
    "total_warnings": 0
  }
}
```

---

## Constraints

- This skill is **read-only**. It must never write to or modify the files it audits.
- Use only `Bash` (for listing files or reading content via `cat`-equivalent
  commands) and `Read` tool calls. No `Edit`, `Write`, `Agent`, or search tools.
- Do not perform registry lookups (e.g. checking agent names against
  `agent_registry.json`). That validation is `llm-expert`'s responsibility.
- Report findings only; do not auto-fix. `llm-expert` decides remediation.
