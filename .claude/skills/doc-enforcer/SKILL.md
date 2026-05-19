---
allowed-tools: Read, Edit, Bash
description: Use when a coder agent finishes editing Python or SQL files. Enforces
  module docstrings, function docstrings, DECISION HISTORY block structure, and (from
  EPIC-DocTraceability onward) the tail-tag ticket-traceability format on new entries.
  Also detects and reads .pending/adr_handoff.json to inject ADR back-links automatically.
name: doc-enforcer
---

# doc-enforcer

This skill is the **single runbook** for coder agents when appending `DECISION HISTORY`
entries and verifying documentation requirements on edited files. It is invoked by
`python-coder`, `sql-coder`, and `documentation-expert` as the final step before
sign-off.

> **Cross-reference:** The tail-tag wire format is formally specified in
> [ADR-033: Inline ADR Ticket-Traceability Convention](docs/architecture/adrs/ADR-033-inline-adr-ticket-traceability.md).
> For a task-oriented step-by-step, see
> [How-To: Write an Inline ADR Entry](docs/how-to/documentation/write-inline-adr.md).

---

## §1 When to Invoke This Skill

Invoke `doc-enforcer` **after every edit pass**, before declaring the task done.
Specifically:

- After editing or creating any `.py` file.
- After editing or creating any `.sql` file.
- After editing any `.md` file that has a `DECISION HISTORY` block.

---

## §2 Module-Level Docstring Enforcement (Python)

Every Python file you create or substantively modify MUST have:

1. **Module docstring** at the top of the file (after the encoding comment and before
   any imports), containing all four required fields:

   ```python
   """
   MODULE: <short name of this module, matching the filename>
   GOAL: <one sentence describing what this module does>
   BUSINESS CONTEXT: <one sentence explaining why this module exists>
   ARCHITECTURE: <one sentence describing where this module fits in the system>
   """
   ```

2. **Function and class docstrings** on every public function, method, and class.
   One-sentence docstrings are acceptable for simple functions.

If either requirement is missing, add the docstring before proceeding to the DECISION
HISTORY step. Do NOT skip this step.

---

## §3 DECISION HISTORY Block Structure

Every Python and SQL file you create or edit MUST have a `DECISION HISTORY` block.
Its canonical form:

```
DECISION HISTORY
================================================================================
- YYYY-MM-DD HH:MM [Author]: WHY text. (#TICKET-REF-OR-TICKETLESS)
```

**Rules:**

- The block is **append-only** — never delete or modify existing entries.
- New entries appear at the **bottom** of the block, after existing ones.
- The block heading is exactly `DECISION HISTORY` followed by a `================` line
  (at least 40 `=` characters).
- If the file has no DECISION HISTORY block yet, add one at the end of the file.

---

## §4 Tail-Tag Format (mandatory for all NEW entries)

From EPIC-DocTraceability onward, every **new** `DECISION HISTORY` entry MUST end with
a tail-tag. **Legacy entries (written before EPIC-DocTraceability shipped) are valid
without a tag — do NOT modify them.**

### §4.1 Ticket tag (standard case)

```
- 2026-05-18 14:32 [python-coder]: Switched routing threshold to per-symbol. (#EPIC-Name/NN)
```

Format: `(#EPIC-Name/NN)` where:
- `EPIC-Name` is the epic folder name, e.g. `EPIC-DocTraceability`, `EPIC-Routing`.
- `NN` is the two-digit ticket number prefix, e.g. `03` for `03_verify_decision_history_upgrade.md`.
- For standalone tickets (not in an epic): `(#TICKET-slug)` using the ticket basename
  without the date prefix.

### §4.2 ADR back-link tag (when adr_handoff.json is present)

If `adr_handoff.json` is found (see §5), append `(ADR-NNN)` after the ticket tag:

```
- 2026-05-18 16:45 [python-coder]: Extracted shared helper. (#EPIC-CCRefactor/CC-33) (ADR-033)
```

The `(ADR-NNN)` tag always comes AFTER the ticket tag, never before.

### §4.3 Multiple tickets

If a single change was driven by more than one ticket, list each tag:

```
- 2026-05-18 18:01 [claude]: Coordinated bump. (#EPIC-A/01) (#EPIC-A/02)
```

### §4.4 TICKETLESS opt-out

When the change has no associated ticket (e.g. a typo fix, lint cleanup, comment
clarification), use `#TICKETLESS` instead of a ticket tag:

```
- 2026-05-18 09:10 [hh]: Fixed typo in docstring. (#TICKETLESS reason=docstring-typo-fix)
```

**Rules for `#TICKETLESS`:**
- The `reason=` string MUST be at least **10 characters** (not including `reason=`).
- The reason should explain WHY there is no ticket — not repeat the change.
- Good: `docstring-typo-fix`, `comment-clarification-nochange`, `lint-whitespace-only`.
- Bad: `misc`, `fix`, `cleanup` (too short or too vague).

### §4.5 Formal grammar (for self-validation)

```
ticket_tag   = \(#[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\)
ticketless   = \(#TICKETLESS reason=[A-Za-z0-9_\-]{10,}\)
adr_tag      = \(ADR-[0-9]{3}\)
tail_tag     = (ticket_tag | ticketless) (adr_tag)*
entry        = - \d{4}-\d{2}-\d{2} \d{2}:\d{2} \[[^\]]+\]: .+ tail_tag
```

---

## §5 Handoff File Check (adr_handoff.json)

Before appending a new DECISION HISTORY entry, check whether `adr-author` has
left a handoff file for the current ticket. This file, when present, tells you
which ADR to back-link.

### Procedure

1. Determine `<ticket-dir>`: the directory containing the current ticket's `.md` file.
   Example: if your ticket is `tickets/01_todo/EPIC-DocTraceability/02_doc_enforcer.md`,
   then `<ticket-dir>` = `tickets/01_todo/EPIC-DocTraceability`.

2. Run:
   ```bash
   cat "<ticket-dir>/.pending/adr_handoff.json" 2>/dev/null
   ```

3. If the file exists and is valid JSON, extract `adr_id` (e.g. `"ADR-033"`).

4. Append `(ADR-NNN)` after the ticket tag in your entry.

5. If the file does NOT exist (or fails to parse), do NOT add an `(ADR-NNN)` tag —
   proceed with just the ticket tag.

**Idempotency:** Running this check multiple times is safe. It reads only; it does not
modify the handoff file. If you have already appended the ADR tag to the entry, do not
append it again — verify the entry ends with exactly one `(ADR-NNN)` tag.

### Using the helper script (optional)

If `scripts/inline_adr/append_entry.py` is present:

```bash
python scripts/inline_adr/append_entry.py \
  --ticket-dir "<ticket-dir>" \
  --ticket-ref "EPIC-DocTraceability/02" \
  --author "python-coder" \
  --why "Updated skill to emit tail-tagged entries."
```

The script produces a pre-formatted entry string you can paste into the DECISION HISTORY
block, with the ADR back-link already injected if `adr_handoff.json` exists.

---

## §6 Legacy Entries

Any `DECISION HISTORY` entry that was written **before this skill was loaded in the
current session** is a legacy entry. Legacy entries:

- Are **valid** even without a tail-tag.
- MUST NOT be modified, re-formatted, or have tail-tags retrofitted onto them.
- Are not validated by the `verify_decision_history` pre-commit hook.

You can identify legacy entries by their timestamp: any entry with a date before
2026-05-18 is definitely legacy. For entries dated on or after 2026-05-18, check
whether you wrote them in the current session — if not, treat them as legacy.

### §6.1 Discovering Untagged Legacy Entries

The `verify_decision_history` pre-commit hook ships with an advisory mode that
counts untagged legacy entries per file without blocking any commit:

```bash
python scripts/commit_guardian/check_documentation.py --report-legacy
```

Exits 0 and prints a per-file count. Useful at epic kick-off to understand
legacy tail-tag debt before starting new work — large counts may motivate a
dedicated documentation epic. Does **not** modify any file and does **not**
enforce tail-tags on legacy entries (per the rule above).

---

## §7 Post-Edit Checklist

After completing all edits on a file, verify:

- [ ] Module docstring present and has all 4 required fields (Python only).
- [ ] All public functions/classes have docstrings (Python only).
- [ ] DECISION HISTORY block is present in every edited file.
- [ ] A new entry was appended at the bottom of the block.
- [ ] The new entry ends with a valid tail-tag (`(#...)` or `(#TICKETLESS reason=...)`).
- [ ] If `adr_handoff.json` was found, entry ends with `(ADR-NNN)` after the ticket tag.
- [ ] No legacy entries were modified.

If any item is unchecked, fix it before returning to the supervisor.

---

## §8 DECISION HISTORY in new files

When creating a new file from scratch, add the DECISION HISTORY block at the end:

**Python:**
```python
# DECISION HISTORY
# ================================================================================
# - 2026-05-18 14:32 [python-coder]: Created module for X. (#EPIC-Name/NN)
```

**SQL:**
```sql
-- DECISION HISTORY
-- ================================================================================
-- - 2026-05-18 14:32 [sql-coder]: Created procedure for X. (#EPIC-Name/NN)
```

**Markdown:**
```
DECISION HISTORY
================================================================================
- 2026-05-18 14:32 [documentation-expert]: Created doc for X. (#EPIC-Name/NN)
```

Use the appropriate comment style for the file type.
