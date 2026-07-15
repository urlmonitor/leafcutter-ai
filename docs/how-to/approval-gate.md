---
title: "How to use the readiness and approval gate"
description: "Task-oriented guide: read the readiness report, choose a gate option (yes / review-all / cancel), and manage the IT PO review-all path."
type: how-to
category: how-to
status: active
created: 2026-06-06
last_updated: 2026-06-06
components:
  - ac_driven_dev
  - build_orchestration
related_docs:
  - docs/architecture/diagrams/c2-005-goal-to-epic-dispatch.md
  - docs/architecture/diagrams/c2-003-ac-readiness-states.md
  - docs/how-to/goal-to-epic.md
  - docs/how-to/build-ac-unified.md
  - docs/how-to/ac-driven-development.md
---

# How to use the readiness and approval gate

The approval gate is the checkpoint between AC tree traversal and ticket
generation in the goal-to-epic workflow. Before any ticket files are written,
the system shows you a **readiness report** and gives you three choices:
proceed with only the approved ACs, send unapproved ACs to IT PO for bulk
review, or cancel.

This guide covers four tasks:

1. [Reading the readiness report](#1-reading-the-readiness-report)
2. [Choosing your gate option](#2-choosing-your-gate-option)
3. [The IT PO review-all path](#3-the-it-po-review-all-path)
4. [Cancelling and returning later](#4-cancelling-and-returning-later)

**Related AC IDs:** ACD-1200b-3 (this guide), ACD-1200b (readiness gate),
ACD-1200b-1 (classify_readiness), ACD-1200b-2 (gate prompt routing).

---

## 1. Reading the readiness report

When you invoke `/build-ac --ac <goal-id>` with a goal-level AC, the system
traverses the AC tree and then prints a readiness report before prompting you:

```
3 of 5 leaf ACs are approved. 2 ACs need approval:
  - ACD-050a-2 (readiness: reviewed)
  - ACD-050b-3 (readiness: draft)
Proceed with 3 approved ACs only? (yes / review-all / cancel):
```

### What the readiness values mean

| Readiness | Meaning | Eligible for ticket generation? |
|-----------|---------|--------------------------------|
| `approved` | You have explicitly approved this AC for building. | Yes |
| `reviewed` | IT PO has enriched the AC; awaiting your approval. | No — must be promoted to `approved` first |
| `draft` | AC authored but not yet enriched by IT PO. | No |
| `unknown` | AC file not found or missing `readiness` field. | No |

### All-approved fast path

If every leaf AC beneath the goal is already `approved`, the gate is
bypassed entirely. The system prints:

```
All 5 leaf ACs are approved. Generating epic...
```

No prompt is shown. Ticket generation begins immediately.

---

## 2. Choosing your gate option

The prompt offers three choices:

```
Proceed with M approved ACs only? (yes / review-all / cancel):
```

### `yes` — Proceed with approved ACs only

The system generates tickets only for the ACs classified as `approved`.
Unapproved ACs are excluded from this EPIC run.

When to choose this:
- You deliberately left some ACs at `reviewed` or `draft` because they are
  not yet ready to build.
- You want a smaller EPIC with only the highest-priority subset.
- You plan to revisit the unapproved ACs in a separate `/build-ac` run later.

### `review-all` — Send unapproved ACs to IT PO

The system dispatches `it-po` to enrich and promote all unapproved ACs
in the batch. See [The IT PO review-all path](#3-the-it-po-review-all-path).

### `cancel` — Abort without writing any files

The system exits cleanly. No ticket files are created, no AC YAML files are
modified, and no EPIC folder is assembled. The prompt message is:

```
Epic generation cancelled. No files written.
```

---

## 3. The IT PO review-all path

When you choose `review-all`, the system:

1. Collects all unapproved AC IDs from the readiness report.
2. Dispatches `it-po` with those IDs and the AC store root.
3. `it-po` enriches each AC with technical fields
   (`assigned_agent`, `estimated_complexity`, `delivers_to`, `expects_from`)
   and promotes eligible ACs to `readiness: reviewed`.
4. The system **re-reads** all AC YAML files from disk after `it-po`
   returns (it does not rely on cached values).
5. If all ACs are now `approved` after the re-read, the fast path fires:
   `"All N leaf ACs are approved. Generating epic..."`
6. If some ACs remain unapproved, the system re-presents the updated
   readiness report and prompts you one more time.

**Note:** `it-po` can enrich and promote `draft` ACs to `reviewed`, but
only you (the user) can promote an AC from `reviewed` to `approved`. After
the `review-all` pass, you will typically need to manually approve any ACs
that `it-po` set to `reviewed` before the final `yes` prompt is answered.

### After the review-all pass

The system shows the updated readiness counts. At this point you can:

- Answer `yes` — proceed with whatever subset is now `approved`.
- Answer `cancel` — abort. The AC enrichment done by `it-po` is
  preserved on disk (the YAML files now have `readiness: reviewed`), so
  your work is not lost.

There is no second `review-all` option on the re-presented prompt — the
system will accept only `yes` or `cancel` after one review-all pass.

---

## 4. Cancelling and returning later

Cancelling at the gate prompt is always safe. The system writes no files,
so the AC store is unchanged (except for any enrichment done during a
`review-all` pass, which is harmless).

To return later and resume:

1. Manually promote the ACs you want to build from `reviewed` to `approved`:
   ```yaml
   readiness: approved
   ```
   Commit the YAML changes:
   ```bash
   git add docs/acceptance-criteria/<component>/<ID>.yaml
   git commit -m "approve <ID>: ready to build"
   ```

2. Re-invoke `/build-ac --ac <goal-id>`.

The system will re-traverse the AC tree, re-classify readiness, and present
an updated report. The EPIC folder name is derived from the goal AC's title
and is deterministic, so re-running after approval changes produces the
same folder name (but only if the folder does not already exist — if it
does, `goal_to_epic.py` raises a conflict error).

---

## Diagram Reference

The approval gate sequence is shown as steps 3–5 in the:

- [Goal-to-Epic Dispatch — Sequence Diagram](../architecture/diagrams/c2-005-goal-to-epic-dispatch.md)

For all five AC readiness states and their owner transitions, see:

- [AC readiness state machine](../architecture/diagrams/c2-003-ac-readiness-states.md)

---

## See Also

- [How to use the goal-to-epic workflow](goal-to-epic.md) — full end-to-end
  walkthrough from goal AC to EPIC folder.
- [Unified /build-ac entry point](build-ac-unified.md) — how `/build-ac`
  detects leaf vs goal mode before the gate is presented.
- [How to use the AC-driven development system](ac-driven-development.md) —
  authoring and approving individual ACs.
