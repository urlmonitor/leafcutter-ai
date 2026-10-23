---
title: "Reference: Document Length Standard"
description: "Lookup for the length limits the check-doc-length gate applies to docs/**/*.md, which locations are set aside from them and on what ground, and what a run reports."
type: reference
status: active
created: 2026-10-14
last_updated: 2026-10-21
components:
  - commit_guardian
  - doc_compliance
  - documentation_system
related_docs:
  - docs/pre-commit-hooks.md
  - docs/reference/source-file-length-measurement.md
  - docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127g-4.yaml
---

# Document Length Standard

Lets an author about to add a document under `docs/` look up whether it is judged for length, which limit applies, and, for the declared exceptions, the ground on which they are set aside and the size at which they are reported.

## Limits

The gate `check-doc-length` measures every staged `docs/**/*.md` file that is not in a set-aside location. Line counts exclude YAML frontmatter. The values below were read from the `doc_length` section of `templates/scripts/commit_guardian/commit_guardian.json`.

| Limit | Value | Applies to |
|---|---|---|
| `max_lines` | 300 | Every judged document except a decision record. |
| `max_lines_adr` | 400 | A decision record: a document under `docs/architecture/adrs/`. |
| `max_sections` | 25 | Top-level (`##`) sections in any judged document. |

Severity is `block`: a judged document that crosses a limit refuses the commit. A document that is already over a limit is judged against its own previous size, so shrinking it or holding it steady passes and growing it is refused.

## A document in no declared location

A document that sits in no declared location is judged. It is held to the limits in the table above: 300 lines, or 400 if it is a decision record, and 25 sections. Being generated, being long, or being unmaintained by hand does not set a document aside; only a declared location does.

## Set-aside locations

A set-aside location is a declared place whose documents are not measured against the limits above. Membership is by location only: a declared path ending in `/` covers every document beneath it at any depth, and any other declared path covers that one document exactly. A document's file name plays no part.

Every declared location carries a stated ground. All three grounds rest on the same property: the document is regenerated whole from another source, so no human author decides its length and no hand edit survives the next regeneration. A location qualifies only if that is true of every document in it, and a location is set aside only once an entry for it is declared with its own ground and report size.

| Declared location | Ground (the property that earns the exemption) | Source the ground identifies | `report_above_lines` |
|---|---|---|---|
| `docs/agents/cards/` | Regenerated whole; no human author decides the length of any document there and no hand edit survives the next regeneration, so a length refusal would name work nobody wrote and prescribe a remedy nobody can apply. | `templates/agents/`, via the build's agent-card phase | 1500 |
| `docs/roadmap.md` | Regenerated whole; carries its own do-not-edit-by-hand marker and names its source, and its length is a function of the roadmap's size, which no author of this file controls. | `docs/roadmap.json` | 1500 |
| `docs/INDEX.md` | Regenerated whole; its length is a function of how many documents the project has, so it grows whenever an unrelated document is added. | The contents of `docs/`, via the build's doc-index phase | 2000 |

Adding a document to an already-declared location needs no change to the declaration. For example, a new file under `docs/agents/cards/` is covered by the existing `docs/agents/cards/` entry. A file beside `docs/roadmap.md` or `docs/INDEX.md` is not covered, because those two entries name one document each.

## The bound on a set-aside location

A set-aside location is not unbounded. Each entry declares its own `report_above_lines`: the size, in lines, of a single document beyond which that document is reported. The figure is set per entry, not globally: `docs/agents/cards/` and `docs/roadmap.md` declare 1500, `docs/INDEX.md` declares 2000.

| Property | Behaviour |
|---|---|
| What the bound measures | One document, not the location's total. |
| A document at or below the bound | Set aside and not reported. |
| A document above the bound | Reported. Standing above the bound never refuses, blocks or fails the commit; the commit completes unless a judged document in the same commit is refused for its own length. |
| Whether it matters if the document shrank or grew | No. On every completing commit that stages it, the report appears for as long as the document stands above the bound, whether it shrank or grew. A run refused for a judged document prints only the two counts, so the report is not shown on that run. |
| Effect on the two counts | None. The document stays among the set-aside documents and is never counted as judged. |

`report_above_lines` is a report threshold, not a refusal limit. It is deliberately not named `max_lines`, whose breach refuses a commit.

## What a run reports

A run states the two populations separately, from the documents it actually partitioned.

| Situation | What the run prints |
|---|---|
| Completing run with set-aside documents | `N documents judged, M set aside`, then one line per set-aside document in the form `set aside: <path> -- ground: <ground>`, then `PASSED: compared N doc files against their length limits` when N is above zero. |
| Every staged document set aside | `0 documents judged, M set aside` and the set-aside lines, with no PASSED line. Zero judged is not a statement that nothing exceeded its limit; nothing was measured. |
| Set-aside document above its bound, on a completing run only | An added paragraph with a signed headroom (C minus S, a negative number here), e.g. `docs/INDEX.md stands above the ceiling its location declares: 2101 lines measured against a ceiling of 2000 (headroom -101).` then `The commit is not refused. This is addressed to the owner of the source named by the location's stated ground: <ground>` |
| Refused run | The two counts only, followed by the refusal for the refused documents. Set-aside documents and any above-bound report are not listed. |

A set-aside document appears in the set-aside count and never in the judged count or the PASSED count. A line reading `set aside` therefore means the document was not measured, not that it was found within its permitted length.

Example of a completing run that includes one set-aside document:

```text
1 documents judged, 1 set aside
  set aside: docs/INDEX.md -- ground: Regenerated whole by the build's doc-index phase ...

✅ PASSED: compared 1 doc files against their length limits
```

## Declaring a location

An entry in `doc_length.set_aside_locations` carries three keys.

| Key | Type | Required | Description |
|---|---|---|---|
| `path` | string | Yes | Repo-relative path; a trailing `/` covers every document beneath it, otherwise one document exactly. |
| `ground` | string | Yes | The stated reason the location is not judged. Absent, empty or whitespace-only is rejected. |
| `report_above_lines` | positive integer | Yes | The per-document size above which a document in the location is reported. Never defaulted: absent or non-positive is rejected. |

A location can be declared set aside only together with both its ground and its report size. An entry missing either is rejected, and the rejection names the entry and says which is absent.

## When the declaration cannot be used

The declaration is read once per run. If the file cannot be read, or its content or any one entry cannot be interpreted (including an entry rejected as above), the run:

- prints `DECLARATION PROBLEM: the declaration commit_guardian.json (doc_length.set_aside_locations) could not be read` (or `interpreted`), followed by the detail, on standard error;
- sets nothing aside, so every staged document is judged against the configured limits (currently 300 lines, 400 for a decision record, 25 sections); the same figures are the fallback only when the configuration file itself cannot be loaded;
- prints `N documents judged, 0 set aside` on standard output;
- fails the commit, even if no document is over a limit.

A declaration that is readable but lists no entries is not a problem: it means nothing is set aside, and the run does not print `DECLARATION PROBLEM`.

## See Also

- [Source File Length Measurement](source-file-length-measurement.md) — the counterpart rule for `.py`, `.js` and other source files.
- [Pre-Commit Hooks](../pre-commit-hooks.md) — where `check-doc-length` sits in the hook sequence.
- [GE-127g-4](../acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127g-4.yaml) — the acceptance criteria this document delivers.
- `templates/scripts/commit_guardian/commit_guardian.json` — the `doc_length` declaration.
- `templates/scripts/commit_guardian/check_doc_length.py` — the gate.
- `templates/scripts/commit_guardian/_doc_length_set_aside.py` — population counts, the above-bound report and declaration validation.
