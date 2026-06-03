---
allowed-tools: Read, Edit, Bash(git status *, git log *, git mv *, find *, grep *)
description: >
  Pre-archive validation gate invoked by finalize-feature.js Step 5 before
  moving an epic folder to tickets/99_done/. Scans every sub-ticket in the
  epic's done/ subfolder and verifies that each has frontmatter `status: done`.
  Reports any tickets that are missing the status, offers a confirmation-gated
  auto-fix (set `status: done` + commit), and blocks the folder move until all
  tickets are valid. Use when finalizing an epic — do NOT invoke for
  single-ticket branches.
name: finalize-feature-archive-check
---

# finalize-feature-archive-check

This skill is the **pre-archive validation gate** for epic finalization. It is invoked
by `finalize-feature.js` Step 5 immediately before `git mv` moves the epic folder to
`tickets/99_done/`. It enforces the invariant that every sub-ticket in an epic's `done/`
folder has `status: done` in its YAML frontmatter.

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

The `epic_folder` is the current location of the epic (before any move). The skill
expects the epic to have a `done/` subfolder containing completed sub-ticket files.

---

## §2 Algorithm

### §2.1 Scan

1. Find all `*.md` files under `<epic_folder>/done/` (excluding `Master_Plan.md`):

   ```bash
   find <epic_folder>/done/ -name "*.md" ! -name "Master_Plan.md" -type f
   ```

2. For each file found, parse the YAML frontmatter block (content between the
   first and second `---` delimiters) and extract the `status:` field value.

3. Build two lists:
   - `ok_tickets`: files where `status: done` (exact match, case-sensitive).
   - `missing_tickets`: files where `status` is absent or any value other than `done`.

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

- **`all_clear: true`**: proceed with the epic folder move. No user input needed.
- **`all_clear: false`**: surface the `missing_tickets` list to the caller and offer
  the auto-fix described in §2.3.

### §2.3 Auto-fix (confirmation-gated)

When `all_clear` is `false`, the caller (finalize-feature.js Step 5) MUST:

1. Display the list of `missing_tickets` to the user:
   ```
   WARNING: The following sub-tickets in <epic_folder>/done/ are missing status: done:
     - <path> (current: <current_status or "absent">)
     - ...
   ```

2. Ask the user:
   ```
   Auto-fix: set `status: done` in frontmatter for all listed tickets and commit? (yes / no)
   ```

3. **On `yes`**: for each ticket in `missing_tickets`:
   a. Edit the ticket's frontmatter `status:` field — replace the current value
      (or insert after the `---` opening line if absent) with `status: done`.
   b. Stage the edited file: `git add <path>`.
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
   The caller MUST NOT proceed to `git mv` the epic folder when `status: halted`.

---

## §3 Caller Contract (finalize-feature.js Step 5)

The caller invokes this skill as follows, embedded in Step 5 before the `git mv`:

```javascript
// SKILL: finalize-feature-archive-check
// Invoke only for epic-scoped branches (closeInfo.scope === "epic")
if (closeInfo.scope === "epic") {
  const archiveCheck = await agent({
    agentType: "status-checker",
    input: {
      instructions:
        "Run the finalize-feature-archive-check skill on <epic_folder>.\n" +
        "Return the structured JSON result (all_clear, missing_tickets, etc.).\n" +
        "If all_clear is false, surface the missing_tickets list and ask for " +
        "user confirmation before applying auto-fix.",
    },
  });

  // Parse archiveCheck result
  // If status === "halted": return { status: "halted", halted_at_step: 5, reason: archiveCheck.reason }
  // If all_clear !== true: block the git mv
}
// Proceed to git mv only when all_clear === true
```

**The `git mv` of the epic folder MUST NOT execute if `all_clear` is not `true`.**

---

## §4 Edge Cases

| Case | Behaviour |
|------|-----------|
| `done/` subfolder is empty | `ok_count: 0`, `missing_count: 0`, `all_clear: true` — proceed |
| `done/` subfolder does not exist | Treat as empty — `all_clear: true`, log a warning |
| `status` field is present but empty (`status: ""`) | Treat as missing — include in `missing_tickets` |
| A ticket file cannot be parsed (malformed YAML) | Include in `missing_tickets` with `current_status: "(parse error)"` |
| Single-ticket branch (not epic-scoped) | Skip this skill entirely — caller determines scope via `closeInfo.scope` |

---

## §5 Known Instance

**EPIC-MoveOnMainOnly retrospective** — ticket 03 (`03_single_writer_guarantee.md`)
was archived without `status: done`, causing `completed_ticket_count` to read 5
instead of 6. The fix in this skill is the mechanical enforcement of the invariant
that building-epics §7.2 describes at the supervisor level.

This skill operationalizes §7.2 at the finalize-feature.js layer, making the check
automatic and confirmation-gated rather than manual.
