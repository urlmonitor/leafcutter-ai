---
allowed-tools: Read, Edit, Bash(git status *, git log *, find *, grep *)
description: >
  Pre-archive validation gate invoked by finalize-feature.js Step 5 before
  completing an epic. Scans ALL .md files recursively in the epic folder
  (including any legacy done/ subfolder) and verifies that each sub-ticket
  has frontmatter `status: done`. Uses frontmatter status: as the authoritative
  signal — not folder position (BO-400a-3, BO-400c-2). Reports any tickets that
  are missing the status, offers a confirmation-gated auto-fix via
  set_ticket_status.py, and blocks archival until all tickets are valid.
  Use when finalizing an epic — do NOT invoke for single-ticket branches.
name: finalize-feature-archive-check
---

# finalize-feature-archive-check

This skill is the **pre-archive validation gate** for epic finalization. It is invoked
by `finalize-feature.js` Step 5 before the epic is considered complete. It enforces
the invariant that every sub-ticket in an epic has `status: done` in its YAML frontmatter.

**BO-400 change:** The scan no longer looks only in the `done/` subfolder. It scans
ALL `.md` files recursively in the epic folder and uses each file's frontmatter
`status:` field as the authoritative lifecycle signal. The `done/` subfolder convention
is deprecated — tickets remain at their original paths and their frontmatter `status:`
is updated by `set_ticket_status.py` instead.

**Backward compatibility:** Legacy epics with tickets already in a `done/` subfolder
are handled correctly — those files are included in the recursive scan and their
frontmatter `status:` is read. If a legacy ticket in `done/` lacks a `status:` field,
it is treated as `status: done` (the only reason it would be in that folder under the
old convention).

**Root cause:** During EPIC-MoveOnMainOnly, ticket 03 was archived without its
frontmatter `status:` being set to `done`. This caused `completed_ticket_count` to
read 5 instead of 6 in the retrospective. This skill closes that gap.

---

## §1 Inputs

The skill receives:

```yaml
epic_folder: "<absolute or repo-relative path to the epic folder>"
# Example: tickets/01_todo/EPIC-MoveOnMainOnly/
```

The `epic_folder` is the current location of the epic. The skill scans ALL `.md`
files recursively, including any legacy `done/` subfolder.

---

## §2 Algorithm

### §2.1 Scan

1. Find all `*.md` files recursively under `<epic_folder>` (excluding `Master_Plan.md`
   and `README.md`):

   ```bash
   find <epic_folder> -name "*.md" ! -name "Master_Plan.md" ! -name "README.md" -type f
   ```

2. For each file found, parse the YAML frontmatter block (content between the
   first and second `---` delimiters) and extract the `status:` field value.

   **Backward-compat rule:** If the file lives under a `done/` subfolder and has no
   `status:` field, treat its effective status as `done`.

3. Build two lists:
   - `ok_tickets`: files where effective status is `done` or `deferred`.
   - `missing_tickets`: files where effective status is any other value (or `null` if
     absent outside a `done/` subfolder).

### §2.2 Report

Return a structured result:

```json
{
  "epic_folder": "<path>",
  "ok_count": <N>,
  "missing_count": <M>,
  "ok_tickets": ["<path>", ...],
  "missing_tickets": [
    {
      "path": "<path>",
      "current_status": "<value or null if absent>"
    },
    ...
  ],
  "all_clear": <true if missing_count == 0>
}
```

- **`all_clear: true`**: proceed with epic completion. No user input needed.
- **`all_clear: false`**: surface the `missing_tickets` list to the caller and offer
  the auto-fix described in §2.3.

### §2.3 Auto-fix (confirmation-gated)

When `all_clear` is `false`, the caller (finalize-feature.js Step 5) MUST:

1. Display the list of `missing_tickets` to the user:
   ```
   WARNING: The following sub-tickets in <epic_folder> are not done:
     - <path> (current: <current_status or "absent">)
     - ...
   ```

2. Ask the user:
   ```
   Auto-fix: set `status: done` via set_ticket_status.py for all listed tickets and commit? (yes / no)
   ```

3. **On `yes`**: for each ticket in `missing_tickets`:
   a. Invoke `set_ticket_status.py` to update the frontmatter status:
      ```bash
      python scripts/set_ticket_status.py --ticket <path> --status done
      ```
      If the ticket still has `needed` agents, add `--force` and note the override.
   b. The script automatically stages the file via `git add`.
   c. After all fixes are applied, commit:
      `git commit -m "chore(tickets): fix frontmatter status on archived sub-tickets"`
   d. Re-run the §2.1 scan to confirm `all_clear: true` before proceeding.

4. **On `no`**: halt the epic archival. Return:
   ```json
   {
     "status": "halted",
     "reason": "user declined auto-fix — epic archival blocked until missing tickets are fixed",
     "missing_tickets": [...]
   }
   ```
   The caller MUST NOT proceed with epic archival when `status: halted`.

---

## §3 Caller Contract (finalize-feature.js Step 5)

The caller invokes this skill as follows, embedded in Step 5:

```javascript
// SKILL: finalize-feature-archive-check
// Invoke only for epic-scoped branches (closeInfo.scope === "epic")
if (closeInfo.scope === "epic") {
  const archiveCheck = await agent({
    agentType: "status-checker",
    input: {
      instructions:
        "Run the finalize-feature-archive-check skill on <epic_folder>.\n" +
        "Scan ALL .md files recursively (not just done/ subfolder).\n" +
        "Use frontmatter status: as the authoritative signal (BO-400a-3).\n" +
        "Return the structured JSON result (all_clear, missing_tickets, etc.).\n" +
        "If all_clear is false, surface the missing_tickets list and ask for " +
        "user confirmation before applying auto-fix via set_ticket_status.py.",
    },
  });

  // Parse archiveCheck result
  // If status === "halted": return { status: "halted", halted_at_step: 5, reason: archiveCheck.reason }
  // If all_clear !== true: block archival
}
// Proceed only when all_clear === true
```

**Archival proceeds only when `all_clear === true`.**

---

## §4 Edge Cases

| Case | Behaviour |
|------|-----------|
| Epic has no `.md` files at all | `ok_count: 0`, `missing_count: 0`, `all_clear: true` — proceed |
| `done/` subfolder exists (legacy) | Include in recursive scan; frontmatter `status:` is authoritative |
| Legacy `done/` ticket has no `status:` field | Treat as `status: done` (backward compat — it was moved there under old convention) |
| `status` field is present but empty (`status: ""`) | Treat as missing — include in `missing_tickets` |
| A ticket file cannot be parsed (malformed YAML) | Include in `missing_tickets` with `current_status: "(parse error)"` |
| Single-ticket branch (not epic-scoped) | Skip this skill entirely — caller determines scope via `closeInfo.scope` |
| Mixed-state epic (BO-400c-2-i): some in `done/`, some at root | Both sets scanned; any with non-done status appear in `missing_tickets` |

---

## §5 Known Instances

**EPIC-MoveOnMainOnly retrospective** — ticket 03 (`03_single_writer_guarantee.md`)
was archived without `status: done`, causing `completed_ticket_count` to read 5
instead of 6. The fix in this skill is the mechanical enforcement of the invariant
that building-epics §7.2 describes at the supervisor level.

**BO-400 update** — the skill was updated to scan ALL `.md` files recursively (not
just `done/` subfolder) and to use `set_ticket_status.py` for auto-fix instead of
direct YAML editing. This makes the auto-fix consistent with the single authoritative
status-transition mechanism.
