---
description: Create a "Ready for Dev" Ticket or Epic
---
**Role:** Switch persona to **Senior Technical Product Owner & System Architect**.
**Goal:** Do NOT write code. Your goal is to produce a "Ready for Dev" Ticket in `/tickets`.

### PHASE 1: THE INTERVIEW (Context & Soundness)
Before creating the file, you must **interview the user** to ensure value and technical feasibility.
1.  **Value Check:** Ask: "What is the specific financial or system value of this?"
2.  **Context Audit:** Check if the relevant folders have a `README.md`.
3.  **Risk Audit:** "Does this impact live trading logic? If so, what is the rollback plan?"
4.  **Data Pipeline Audit:** If adding an indicator or strategy feature, ask yourself: "(a) Does this require its own background worker? (b) Does it need to be injected into `candle_context`? (c) Are the SQL populations aware of historical data limits (e.g. using LEFT JOINs) to gracefully handle backfilling on empty arrays?"

### PHASE 2: THE BUSINESS LOGIC
1. Create / update the respective feature in /docs folder (if applicable).
2. Follow the rules how to put together the files in that folder.
3. Let the user review the business logic.

### PHASE 2.5: ADR CHECK
Before deciding ticket vs epic, check whether this change requires a new ADR:

**An ADR is MANDATORY if the change introduces any of the following:**
- A new external dependency added to `pyproject.toml`
- A new database migration (`alembic/versions/`) that adds a table or changes a schema significantly
- A new Docker service in `docker-compose.yml`
- A new core or service component in `docs/components.json`
- A change to a fundamental design pattern (e.g., switching from polling to event-driven, changing authentication method)

**If an ADR is needed:**
1. Use the ADR template at `adr/template.md`
2. Number sequentially: `adr/NNNN-short-description.md`
3. Set `adr_status: proposed` in frontmatter with `components_affected` listing relevant component IDs
4. Include the ADR in the same commit as the structural change it documents

**If no ADR is needed:** proceed to PHASE 3.

### PHASE 3: THE STRATEGY ("Magnitude Check")
Decide if this is a **Ticket** or an **Epic**.
*   **Ticket:** Changes < 3 Files.
*   **Epic:** Changes > 3 Files OR touches Logic + UI.

#### OPTION A: CREATE A SINGLE TICKET
Once the user confirms the logic, create a Markdown file in `/tickets/00_inbox/`.
**Filename:** `TICKET-[YYYYMMDD]-[ShortDescription].md`

1.  **Header:** Type, Value, Owner.
2.  **Context:** The "Why" and links to Strategy/Directory Docs.
3.  **Architecture:**
    *   Files to change.
    *   **Test Strategy:** explicitly state which test file controls the logic.
4.  **Todo List (Atomic TDD):**
    *   Break tasks down so testing is explicit.
5.  **Acceptance Criteria (Gherkin):**
    *   `Given` / `When` / `Then` scenarios.

#### OPTION B: CREATE AN EPIC (The "Scaffold" Rule)
If this is an Epic, you must **SCAFFOLD IMMEDIATELY**. Do not leave phantom tasks.

1.  **Create Folder:** `/tickets/01_todo/EPIC-[Name]/`
2.  **Create Master Plan:** `/tickets/01_todo/EPIC-[Name]/Master_Plan.md`
    *   This tracks the high-level goals and links to the sub-tickets.
3.  **Create ALL Sub-Tickets:**
    *   You MUST create physical files for every step in the plan immediately.
    *   **Naming Convention:** `01_name.md`, `02_name.md`, `03_name.md`.
    *   **Linkage:** The `Master_Plan.md` must link to these filenames.
    *   *Example:*
        ```markdown
        - [ ] **01_database_setup.md** (Schema Updates)
        - [ ] **02_api_implementation.md** (Endpoints)
        ```

### PHASE 4: THE HANDOFF
End your response with:
> "Ticket/Epic created.
> **Next Step:** Review the file(s). Type `/build [filename]` to start."
