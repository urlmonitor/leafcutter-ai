---
title: "Known issues — security-scanner"
description: "Open, observed defects in the secrets and vulnerability scanning surface: scan_secrets.py, check_secrets.py, the .security-allowlist grammar, the prose exemption, and the /security-audit workflow. Recorded on sight so they are not lost, and read before adding new capability to this surface."
type: reference
category: reference
status: active
created: 2026-08-19
last_updated: 2026-09-14
components:
  - security_scanner
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/architecture/components/security-scanner.md
  - templates/skills/security-scanner/SKILL.md
---


# Known issues — security-scanner

Observed defects in the **secrets and vulnerability scanning** surface that are **not
yet fixed**. This file exists so a defect noticed in passing can be recorded in
seconds, without authoring a full acceptance criterion for something nobody has
decided to build yet.

## Why this register is separate from `commit-guardian`

The scanner ships as a skill (`templates/skills/security-scanner/`) and is *invoked*
as a pre-commit hook, so until 2026-08-19 its defects were filed under
`commit-guardian`. That made the one question this surface has to answer — *what,
right now, can a credential slip past?* — unanswerable in one place: it was interleaved
with AC-hook scoping, frontmatter enums and drift-manifest paths.

The split is by **surface**. `security_scanner` is a registered component in
`docs/components.json` as of 2026-08-19, with
[`docs/architecture/components/security-scanner.md`](../architecture/components/security-scanner.md)
as its `detail_ref`. It declares `depends_on: ["commit_guardian"]` — the registry has no
`parent` field, and that dependency edge is the closest modelled relationship. The
division of responsibility is set out in the architecture doc.

Note the two component axes do not both gain an entry. `docs/components.json` (underscore
ids) governs knowledge-graph membership and now carries `security_scanner`;
`docs/acceptance-criteria/index.yaml` (kebab ids) governs AC file placement and id
prefixes and deliberately does **not** — a new AC namespace would renumber every existing
`GE-` record. Scanner ACs stay in the `guardrail-engine` namespace and carry
`security_scanner` in their `components` list.

**Scope.** Anything whose failure mode is *a real credential or vulnerability goes
unreported*, or *a suppression removes more coverage than it claims*. Hook plumbing that
happens to affect the scanner but is really about the guardrail framework —
deployment paths, manifest resolution, index scoping — belongs in
[`commit-guardian.md`](commit-guardian.md).

## How to use this file

**Read it before adding new capability to this surface.** Fixing what is already broken
takes precedence over building more — and here that rule has teeth, because a scanner
with a known hole reports clean.

**Adding an issue.** Append a new `### KI-SEC-NNN` section using the next free number.
Verify the number is free **at merge time, not at authoring time** — three duplicate
identifiers were minted across these registers on 2026-08-18 by checking free-ness while
writing and merging after another PR had taken the number. Nothing here is generated —
edit it by hand.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics). For this surface,
read `high` as *a credential can pass unreported* — that is the default severity for a
detection gap, even when the path looks obscure.

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

## How this register is stored

This file is an **index**. Each known issue is its own file under [`security-scanner/`](security-scanner/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/security-scanner/open-blocker-*   # anything critical open?
ls docs/known-issues/security-scanner/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`security-scanner/resolved/`](security-scanner/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 2** (0 blocker, 1 high, 1 low) · **Resolved: 0**

## Open

| Severity | Issue | File |
|---|---|---|
| `high` | Prose exemption disables entropy detection for WHOLE FILES, including executable Python under `templates/skills/` | [open-high-ki-sec-001.md](security-scanner/open-high-ki-sec-001.md) |
| `low` | ENTROPY_HIGH reads a long CamelCase test class name carrying an AC id as a secret, and the only remedy it offers is an allowlist edit that an automated reviewer rightly refuses | [open-low-ki-sec-20260914-entropy-flags-test-class-names.md](security-scanner/open-low-ki-sec-20260914-entropy-flags-test-class-names.md) |

## Resolved

None yet.
