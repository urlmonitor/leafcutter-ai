---
title: "Known issues — guardrail-engine"
description: "Open, observed defects in the guardrail-engine component: the secrets scanner, the commit-guardian hooks that consume it, and the suppression machinery around them. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - commit_guardian
related_docs:
  - docs/architecture/components/commit-guardian.md
  - templates/skills/security-scanner/SKILL.md
---

# Known issues — guardrail-engine

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-GE-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

### KI-GE-001 — Prose exemption disables entropy detection for WHOLE FILES, including executable Python under `templates/skills/`

- **Severity:** high
- **Status:** open — partially anticipated by `GE-123d-4-i` (draft), but that AC governs a *proposed* widening, not this existing behaviour
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/check_secrets.py` — `_PROSE_FILE_PREFIXES` / `_is_prose_exempt`

**Symptom.** `ENTROPY_HIGH` is the only rule that catches an **opaque** credential — a
Stripe key, a JWT, a random API token — because such values carry no `password =`
style keyword for `GENERIC_SECRET` to match and no fixed prefix for `AWS_KEY` or
`PRIVATE_KEY`. That rule is switched off for entire files under four path prefixes.
The source comment states the scope plainly: *"Prose-only file prefixes — entire files
are exempt from entropy scanning."*

**Evidence.** A live-shaped token (`sk_live_…`, Shannon entropy **5.17**, threshold
4.5) run through the real `_is_prose_exempt`:

```
templates/skills/security-scanner/scripts/scan_secrets.py   EXEMPT — not reported
templates/skills/some-skill/scripts/helper.py               EXEMPT — not reported
tickets/00_inbox/TICKET-20260818-Example.md                 EXEMPT — not reported
docs/acceptance-criteria/guardrail-engine/GE-123.yaml       EXEMPT — not reported
docs/retrospectives/retro.md                                EXEMPT — not reported
scripts/build.py                                            reported
leafcutter-web/app/page.tsx                                 reported
```

**Why `templates/skills/` is the sharp edge.** It is on the prose list but it is not
prose — it holds executable Python, including the secrets scanner's own
`scan_secrets.py`. A credential pasted into any script under that prefix is
unreported by the very tool meant to catch it. The other three prefixes are genuinely
prose directories, so the exposure there is narrower, but a ticket is still a file a
developer will happily paste a token into while writing up an incident.

**Scope of the exemption, precisely.** It gates `ENTROPY_HIGH` only —
`AWS_KEY`, `PRIVATE_KEY`, `EXCHANGE_API_KEY` and `GENERIC_SECRET` still fire in these
paths. So the hole is exactly the class of credential that has no recognisable shape,
which is most modern opaque tokens.

**The exemption is far wider than four directories — the match is NOT root-anchored.**
`_is_prose_exempt` tests `("/" + prefix) in path_str`, a substring test against the
whole path. So the four prefixes are really four *directory names*, matching at **any
depth, in any subtree**. Measured with the same 5.17-entropy token:

```
tickets/00_inbox/note.md                    EXEMPT   (intended)
leafcutter-web/tickets/app.py               EXEMPT   (not intended)
src/vendor/tickets/handler.py               EXEMPT   (not intended)
some/deep/nested/docs/retrospectives/x.py   EXEMPT   (not intended)
unrelated/templates/skills/evil.py          EXEMPT   (not intended)
src/app.py                                  reported
```

This repository already ships `leafcutter-web/`. Any feature directory named
`tickets/`, any vendored dependency containing one, and any nested `templates/skills/`
loses entropy detection silently — for `.py` as readily as for `.md`. The original
framing of this issue (four known prose directories) understated it: the reachable
surface is any path containing one of those four segment names.

**Corollary — a test can be written that passes for the wrong reason.** A fixture
placed under any such path measures the exemption rather than the scanner. This is a
live authoring hazard, not a theoretical one; it is called out as a hard
`it_requirement` in the `GE-123a` and `GE-123c` subtrees for exactly that reason.

**Fix direction.** Three separable changes, in descending order of payoff:

- **Anchor the match at the repository root.** Compare path *segments* from the root
  rather than substring-testing the whole path. This is the single change that shrinks
  the surface from "any path containing these names" back to the four directories the
  exemption was written for, and it is the cheapest of the three.
- Gate the exemption by **file kind**, not only by path. A `.md` under `tickets/` is
  prose; a `.py` under `templates/skills/` is not. This closes the executable-code case
  that anchoring alone leaves open, since `templates/skills/` genuinely is on the list.
- Make the exemption **per finding** rather than per file. The existing rule discards
  every entropy finding in a matching file; the narrower rule is to discard only
  findings whose high entropy is explained by a benign token — which the module
  already computes for `TICKET-…` / `EPIC-…` identifiers and could extend.

**One more thing the fix must not trip over.** `_filter_prose_findings` passes
`finding.excerpt` as the line to test, and `scan_file` sets
`excerpt = line.strip()[:120]` (`scan_secrets.py:248` and `:254`). The exemption
therefore judges a **truncated** line: a benign explanatory token sitting past column
120 is invisible to it, so verdict can turn on line length alone. Any per-finding
rework needs the full matched value, not the excerpt.

**Relationship to in-flight work.** `GE-123d` proposes extending prose exemption to
`GENERIC_SECRET`, and `GE-123d-4-i` exists specifically to require a file-kind gate so
that widening does not inherit this defect. That is the right guard for the *new*
behaviour, but it does not repair the *existing* `ENTROPY_HIGH` exemption — this issue
covers that, and it should be fixed first so the new work is not built on top of it.
