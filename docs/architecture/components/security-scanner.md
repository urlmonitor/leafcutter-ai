---
title: "Security Scanner — Secrets Detection and Suppression"
description: "Secrets and vulnerability scanning surface: the rule set that decides what counts as a credential, the allowlist and prose-exemption mechanisms that narrow it, and the pre-commit hook and audit workflow that invoke them."
flight_level: L3-Component
status: active
type: reference
created: 2026-08-19
last_updated: 2026-08-19
components:
  - security_scanner
  - commit_guardian
---

# Security Scanner

## Overview

The Security Scanner is the surface that decides whether a credential committed to this
repository is reported. It ships as a skill
(`templates/skills/security-scanner/`), is invoked at commit time by the
`check-secrets` pre-commit hook, and is also driven directly by the `/security-audit`
workflow for a full-repository pass.

## Relationship to Commit Guardian

`docs/components.json` has **no `parent` field** and models no hierarchy. What it does
model is a dependency edge: this component declares

```json
"depends_on": ["commit_guardian"]
```

which `check-components-integrity` validates against the existing component ids. That is
the closest the registry gets to the containment, and it is the honest shape — the
scanner is *invoked by* the guardrail framework and cannot run without it, but the
framework does not own what the scanner decides. Only one other component (`epic_retrospective`)
declares a dependency at all, so this edge is sparse by convention rather than absent by
design.

A `parent` key was deliberately not invented. It would be a field nothing validates and
no other entry uses; if the registry should gain real hierarchy, that is its own decision
with consequences for all 43 entries.

The practical division, which is also the boundary used by
[`docs/known-issues/security-scanner.md`](../../known-issues/security-scanner.md):

| Concern | Owner |
|---|---|
| What counts as a credential; what a suppression may remove | `security_scanner` |
| Whether the hook can find, load and execute its scripts at all | `commit_guardian` |
| Hook ordering, index scoping, manifest resolution, deployment paths | `commit_guardian` |

The division is imperfect at one seam and deliberately so: an AC about the hook resolving
`scan_secrets` is a `commit_guardian` resolution problem whose *failure mode* is a
credential going unreported. Those records carry **both** component ids, because
`components` is a membership list rather than an ownership claim.

## Responsibilities

- **Detect.** Apply the rule set to staged (hook) or all (audit) files. Four rules are
  declared in `_RULES` — `PRIVATE_KEY`, `AWS_KEY`, `EXCHANGE_API_KEY`, `GENERIC_SECRET` —
  and two more, `ENV_FILE` and `ENTROPY_HIGH`, are emitted as inline literals rather than
  declared entries. There is no single canonical rule-id vocabulary; a caller cannot
  enumerate the rules from the module.
- **Narrow, never disable.** Two mechanisms reduce the finding set: the
  `.security-allowlist` (grammar `rule_id:file_path:line_no`, suffix-matched on path
  segments) and the prose exemption (`_PROSE_FILE_PREFIXES`). The governing principle,
  authored as the `GE-123` acceptance-criteria tree, is that a suppression narrows a check
  and never switches it off.
- **Report honestly.** A suppression that cannot match, or a scan that could not run, must
  say so rather than presenting as a clean result.

## Primary code

| Path | Role |
|---|---|
| `templates/skills/security-scanner/scripts/scan_secrets.py` | the scanner: rules, allowlist loading, suffix matching |
| `templates/scripts/commit_guardian/check_secrets.py` | the pre-commit entry point and the prose post-filter |
| `.security-allowlist` | suppression entries; resolved from the workspace root, not the worktree |
| `templates/skills/security-scanner/SKILL.md` | the skill surface and the `/security-audit` workflow |

## Known constraints

Open defects are tracked in
[`docs/known-issues/security-scanner.md`](../../known-issues/security-scanner.md). The
one worth knowing before reading any scan result: `KI-SEC-001` — the prose exemption
disables high-entropy detection for **whole files**, and matches its path prefixes
**unanchored**, so any path containing a `tickets/`, `docs/retrospectives/`,
`docs/acceptance-criteria/` or `templates/skills/` segment at any depth loses entropy
detection entirely, including this scanner's own source.

`.security-allowlist` resolution is also a live trap: the hook computes its project root
from the resolved `.leafcutter` symlink target, so it reads the **workspace-root**
allowlist and silently ignores a suppression placed only in a worktree's own copy.

## Acceptance criteria

ACs for this surface live in the `guardrail-engine` AC namespace (prefix `GE`) and carry
`security_scanner` in their `components` list. The namespace is deliberately not split:
`docs/acceptance-criteria/index.yaml` governs AC file placement and id prefixes, so giving
this component its own namespace would renumber every existing `GE-` record. The two axes
are independent by design — see that file's own header note.

| Tree | Subject |
|---|---|
| `GE-123` | a suppression narrows a security check, it never disables it |
| `GE-113c-3` | allowlist entries match on path segments, and an entry that cannot match says so |
| `GE-113c-1-v` | the allowlist is read from the checkout the developer is actually working in |
