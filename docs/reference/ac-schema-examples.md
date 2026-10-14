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
