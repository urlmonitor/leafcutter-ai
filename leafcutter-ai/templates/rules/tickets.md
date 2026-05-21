---
trigger: glob
globs: tickets/**/*.md
---

## TASK DEFINITION STANDARDS (The Ticket Template)

### A. The 'Actor' Protocol
Select the voice based on the task type:
- **User (Human):** 'As a [Role]...' (Dashboards, Admin)
- **System (Bot):** 'When [Trigger]...' (Strategies, Cron)
- **Dev (Chore):** 'In order to [Improve]...' (Refactor)

### B. Required Sections (Business Context)
1.  **Context:** The 'Why' and links to strategy docs.
2.  **Acceptance Criteria (Gherkin):**
    - 'Given' [State] 'When' [Trigger] 'Then' [Outcome]
    *Must be copy-pasteable into a Test File.*
3.  **Risk & Safety:**
    - 'Does this touch Money?' -> Add Risk Controls.
    - 'Does this touch Data?' -> Add Migration Plan.

### C. Implementation Tasks (The Atomic Plan)
**CRITICAL:** This section MUST be a nested checkbox list. Vague bullet points are forbidden.
The 'Architect' must pre-solve the structure for the 'Engineer'.

**Rules for Tasks:**
1.  **File-Centric Grouping:** Group tasks by the file being modified.
2.  **Specifics Only:** Name the function, class, or variable. No 'Update logic.'
3.  **Strict Syntax:** Use '- [ ]' for every item.

**Good Example (Required):**
- [ ] **SQL Extraction**
  - [ ] Create 'sql_functions/functions/get_running_candle_start.sql'
  - [ ] Extract SQL body from 'database/' -> 'construct_get_running_candle_start_function'
- [ ] **Verification**
  - [ ] Run 'test_db_rebuild.py' to ensure SQL loads correctly

---

## D. EPIC & SCAFFOLDING RULES (The 'Real Files' Rule)

### 1. Structure
Epics are too big for a single file. They must be a **Folder** containing:
- 'Master_Plan.md': The high-level overview and tracker.
- '01_setup.md': The first step.
- '02_implementation.md': The second step.
- ...etc.

### 2. The 'One Checkbox = One File' Rule
In the 'Master_Plan.md', every major implementation step MUST correspond to a **physical file** in the same directory.
-  **Bad Master Plan:**
  - [ ] Update Database (Just text, no file exists)
  - [ ] Fix API (Just text)
-  **Good Master Plan:**
  - [ ] '01_database_update.md' (Exists in folder)
  - [ ] '02_fix_api.md' (Exists in folder)

### 3. Immediate Scaffolding
When an Epic is defined, the Agent MUST create placeholders for **ALL** planned tickets immediately. An Epic is not 'Planned' until its sub-ticket files exist.

---

## E. TICKET LIFECYCLE MANAGEMENT (The Flow)

**CRITICAL:** Tickets are dynamic assets. You MUST move them across these folders as development progresses:

1.  **'00_inbox/'**: For new, unvetted, or loosely defined ideas.
2.  **'01_todo/'**: For the active Epic or standalone tickets you are currently working on.
3.  **'02_done/'**: For fully completed standalone tickets or finished Epics.

### Rules for 'Moving to Done':
- **Internal Epic Flow**: When a specific task file inside an Epic is finished, move it into the 'done/' subfolder *inside* that Epic's directory.
- **Master Plan Sync**: Whenever a ticket is moved to 'done/', you MUST update the 'Master_Plan.md' checklist.
- **Epic Archiving**: An Epic directory is only moved to '02_done/' once every internal task is in its 'done/' folder and the overall Acceptance Criteria are met.
**NEVER leave a completed ticket in a root directory; keep the workspace clean.**
