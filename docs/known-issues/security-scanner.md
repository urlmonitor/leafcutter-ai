---
title: "Known issues — security-scanner"
description: "Open, observed defects in the secrets and vulnerability scanning surface: scan_secrets.py, check_secrets.py, the .security-allowlist grammar, the prose exemption, and the /security-audit workflow. Recorded on sight so they are not lost, and read before adding new capability to this surface."
type: reference
category: reference
status: active
created: 2026-08-19
last_updated: 2026-08-19
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

### KI-SEC-001 — Prose exemption disables entropy detection for WHOLE FILES, including executable Python under `templates/skills/`

- **Severity:** high
- **Status:** open — partially anticipated by `GE-123d-4-i` (draft), but that AC governs a *proposed* widening, not this existing behaviour
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/check_secrets.py` — `_PROSE_FILE_PREFIXES` / `_is_prose_exempt`
- **History:** filed 2026-08-18 as `KI-CG-004` in `commit-guardian.md`; moved here 2026-08-19 when this register was created. `KI-CG-004` is retired, not reused.

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

Six `GE-123` records cite this defect by its original id and file path
(`KI-CG-004` in `docs/known-issues/commit-guardian.md`), deliberately, as an
out-of-scope fence. Those citations were left untouched by the move: they are dated
records of a decision, and the retired-id stub in `commit-guardian.md` resolves them in
one hop. Do not "fix" them to point here — the fence is what stops this issue and
`GE-123d-4-i` being closed as duplicates of each other.
