---
title: "Reference: AC Schema Examples"
description: "Worked AC YAML examples that accompany ac-schema.md: the pattern-inherited AC with a placeholder criteria text. Moved from ac-schema.md."
type: reference
status: active
created: 2026-10-14
last_updated: 2026-10-14
components:
  - ac_store
  - ac_driven_dev
related_docs:
  - docs/reference/ac-schema.md
  - config/ac_store_schema.json
---

# AC Schema Examples

> **Parent document:** [ac-schema.md](ac-schema.md). The example below was moved here verbatim
> (ACD-2500c-3) to keep the parent under its length ratchet.

### Pattern-inherited AC example (empty criteria)

When an AC inherits all of its behavior from a reusable pattern, the `criteria`
field may contain a plain-text placeholder instead of a full `Given`/`When`/`Then`
scenario. The schema validator accepts this form when `implements_pattern` is set.

```yaml
id: PAGE-005
title: "Users list page — standard CRUD table (PTN-001)"
component: users-ui
status: active
created_by: "tickets/00_inbox/epics/EPIC-UsersUI/03_users_list.md"
criteria: "No page-specific behavior — all behavior inherited from pattern."
implements_pattern: "PTN-001"
pattern_bindings:
  entity_type: "users"
  columns:
    - "name"
    - "email"
readiness: draft
priority: medium
origin_agent: business-analyst
```

**Key points:**
- `criteria` must still be a non-empty string (the schema requires `minLength: 1`).
- A plain-text placeholder like `"No page-specific behavior — all behavior inherited from pattern."` satisfies this requirement.
- The effective behavior is entirely derived from the pattern referenced in `implements_pattern`, instantiated with the `pattern_bindings` values.
- The schema validator does **not** enforce `Given`/`When`/`Then` format — any non-empty string is valid.

### Pattern AC example (with pattern_slots)

A pattern AC declares the slots that consuming ACs must bind. The `pattern_slots`
field lists each `{word}` placeholder from the `criteria` field explicitly.

```yaml
id: ACS-500a-1
title: "A pattern AC defines shared behavior with parameterized slots"
component: ac-store
level: L2
status: active
created_by: "tickets/00_inbox/epics/EPIC-PatternReuse/01_define_pattern.md"
criteria: |
  Given an AC YAML file with level: L2,
  When its criteria describes behavior with named slots
    (e.g. "sortable table with columns {columns}, sorted by {default_sort}"),
  Then that AC is the single authoritative definition of the shared behavior.
pattern_slots:
  - "{columns}"
  - "{default_sort}"
readiness: approved
priority: high
origin_agent: BrainCandy
```

### Example: CRUD list page

Given the following ACs:

```yaml
# Page AC (consumer)
id: PAGE-001
implements_pattern: PTN-020
criteria: "No page-specific wiring — all behavior inherited from PTN-020."

# Composite pattern AC
id: PTN-020
depends_on: [PTN-010, PTN-011, PTN-012]
criteria: |
  Given a page implements sort, filter, and pagination,
  When the user changes a filter, Then pagination resets to page 1 ...

# Atomic pattern ACs
id: PTN-010
criteria: |
  Given a page contains a sortable table ...
id: PTN-011
criteria: |
  Given a page contains a filter bar ...
id: PTN-012
criteria: |
  Given a page displays a paginated collection ...
```

`resolve_behavior_stack("PAGE-001", id_index)` returns:

```python
[
  {"layer": "page",      "ac_id": "PAGE-001", "source": "self", ...},
  {"layer": "composite", "ac_id": "PTN-020",  "source": "implements_pattern", ...},
  {"layer": "atomic",    "ac_id": "PTN-010",  "source": "depends_on", ...},
  {"layer": "atomic",    "ac_id": "PTN-011",  "source": "depends_on", ...},
  {"layer": "atomic",    "ac_id": "PTN-012",  "source": "depends_on", ...},
]
```
