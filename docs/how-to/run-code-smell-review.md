---
title: "How to run a code-smell review"
description: "Step-by-step guide for invoking /code-smell-review against a single file, a folder, or pasted code, and for reading the resulting severity-ranked Fowler smell report."
type: how-to
status: active
created: 2026-08-11
last_updated: 2026-08-11
components:
  - review_system
related_docs:
  - templates/commands/code-smell-review.md
  - templates/skills/code-smell-review/SKILL.md
  - templates/skills/review-for-code-smells/SKILL.md
---

# How to run a code-smell review

Run `/code-smell-review` to get a single, severity-ranked report that names every
Martin Fowler code smell present in your code and the refactoring that removes it.

---

## Prerequisites

- leafcutter is installed in your project and the `/code-smell-review` command is
  available in your Claude Code session.
- You know what you want to review: a specific file path, a folder path, or a code
  snippet you can paste directly into the chat.
- No prior knowledge of Fowler's twelve smells is required — the report names and
  explains each one it finds.

---

## Steps

### Step 1 — Review a single file

Pass the file path as the argument to `/code-smell-review`.

```
/code-smell-review src/billing/invoice.py
```

The command reads `invoice.py` in full, follows any imports it needs to understand
context, and runs both reviewers against it. Use this form when you want focused
feedback on one module before opening a PR.

**Worked example:**

```
/code-smell-review src/billing/invoice.py
```

Expected chat reply: a single sentence confirming the output file path and the
finding count by severity — for example:

```
Report written to code-smells-invoice.md — 2 HIGH, 3 MEDIUM, 1 LOW.
```

---

### Step 2 — Review a folder

Pass the folder path as the argument to `/code-smell-review`.

```
/code-smell-review src/billing/
```

The command reads every file in the folder, follows cross-file relationships (shared
types, repeated field groups, function call chains), and produces one merged report
for the whole target. Use this form when you want to catch smells that only appear
across multiple files — such as Data Clumps or Shotgun Surgery.

**Worked example:**

```
/code-smell-review src/billing/
```

Expected chat reply:

```
Report written to code-smells-billing.md — 1 HIGH, 4 MEDIUM, 2 LOW.
```

---

### Step 3 — Review pasted or inline code

Invoke `/code-smell-review` with no argument, then paste the code directly into
the chat message.

```
/code-smell-review
```

After you send that command, paste the snippet you want reviewed — either in the
same message body or in the next message. The command picks up pasted code when no
file or folder argument is supplied.

Use this form when the code is not saved to disk yet, or when you want to review a
small excerpt without pointing at the full file.

**Worked example:**

```
/code-smell-review

def process(u, o, p, d, t):
    if u.status == "active":
        ...
    if u.status == "active":
        ...
```

Expected chat reply:

```
Report written to code-smells-snippet.md — 1 HIGH, 2 MEDIUM, 0 LOW.
```

---

## What the report looks like

The report file (`code-smells-{target-id}.md`) is written to your workspace root.
It always contains the following sections in this order.

### Inferred Context

A small table stating the language and stack (with confidence level) and what the
reviewed code appears to be trying to do. Correct the inferred intent in chat if it
is wrong — the reviewers use it to calibrate severity.

### Summary

A table counting findings per smell name and per severity band (HIGH, MEDIUM, LOW).
Use this table to get an at-a-glance picture before reading the details.

### HIGH, MEDIUM, and LOW sections

Findings are grouped by severity. Within each band, each finding is formatted as:

1. **Title** — `[SMELL NAME] short description`, e.g. `[LONG FUNCTION] save() does five jobs`.
2. **What's wrong** — three to five plain-English sentences naming the problem and
   explaining why it matters.
3. **Refactoring** — the named Fowler refactoring move to apply, e.g.
   `Extract Function`, `Replace Primitive with Object`, `Move Function`.
4. **File** — exact path and line range, e.g. `src/billing/invoice.py:42–91`.
5. **Before** — a verbatim excerpt from your source code (never altered).
6. **After** — a minimal direction sketch starting with
   `# direction only – not a full rewrite`. It shows the shape of the fix, not
   finished code.

Finding IDs follow the pattern `H-1`, `H-2`, `M-1`, `M-2`, `L-1`, numbered
continuously within each band across both reviewers' findings.

### Scorecard

A 0–10 rating per smell category that had signal, a one-sentence verdict for each,
and an overall mean rounded to one decimal place.

---

## Verification

Open the report file confirmed in the chat reply and verify it contains:

- An **Inferred Context** table at the top.
- A **Summary** table listing at least one finding.
- At least one `H-N`, `M-N`, or `L-N` finding block with a **Before** code fence and
  an **After** code fence.
- A **Scorecard** at the bottom.

If the chat reply says only one bucket ran (structural or design), see
Troubleshooting below.

---

## Troubleshooting

**1. Chat says "only one bucket ran"**

One of the two parallel reviewers (`find-structural-smells` or `find-design-smells`)
returned an error or produced no usable output. The report is still written from the
other reviewer's findings and is stated plainly in the chat. Check whether your
Claude session has access to Opus-tier models — `find-design-smells` runs on Opus.
If Opus is unavailable, only structural smells are reported.

**2. No report file appears and there is no chat confirmation**

The target could not be resolved. This happens when you invoke `/code-smell-review`
with no argument and no code is pasted or attached. Re-invoke with a file or folder
path, or paste the code snippet into the same message as the command.

**3. Report lists very few or zero findings for a large file**

For a single short function or a very small snippet, the command may run only one
reviewer instead of both and states this in the chat. For larger targets, verify the
file path resolves correctly (use an absolute path if the relative path is ambiguous
in your session).

**4. The "After" block looks like a full rewrite, not a sketch**

The After block is direction only by design. If you received a full rewrite, that is
a reviewer output issue — the canonical format specifies a 5–15 line sketch starting
with a comment line. You can ask the session to re-emit the After block in sketch form.

---

## See Also

- `templates/commands/code-smell-review.md` — the slash-command surface definition,
  including target-resolution priority and related surfaces.
- `templates/skills/code-smell-review/SKILL.md` — the orchestration skill: how the
  parallel fan-out works and how findings are merged.
- `templates/skills/review-for-code-smells/SKILL.md` — the core review method:
  severity rubric, writing style, finding format, and full output format.
- `docs/how-to/creating-an-agent-template.md` — if you need to extend or customise
  the reviewer agents themselves.
