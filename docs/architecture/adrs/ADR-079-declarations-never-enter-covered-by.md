---
title: "ADR-079: Front-End Declarations Never Enter covered_by"
description: "A front-end file's component-level declaration is recorded in a new declared_by field and an element pin in a new pinned_by field; neither is ever written into covered_by or implemented_by, and the AC-schema commit check rejects any covered_by entry shaped like either, with no opt-out. A declaration is a claim a file makes about itself, so letting it into the coverage field would automate the phantom-done defect the store exists to prevent."
type: "adr"
status: "active"
created: "2026-10-23"
last_updated: "2026-10-23"
deciders:
  - BrainCandy
  - adr-author
components:
  - ac_store
  - commit_guardian
related_docs:
  - docs/reference/ac-schema.md
  - docs/architecture/components/phantom-done-prevention.md
  - docs/architecture/adrs/ADR-008-ac-store-schema-id-format-enforcement.md
  - docs/architecture/adrs/ADR-050-runtime-reachability-guard-refuses-not-warns.md
  - docs/acceptance-criteria/guardrail-engine/GE-124-frontend-declares-what-it-renders/GE-124g.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-124-frontend-declares-what-it-renders/GE-124g-1.yaml
  - docs/product-truth/mock-data/guardrails/frontend-ac-declarations.mock.json
related_code:
  - config/ac_store_schema.json
  - templates/scripts/commit_guardian/_ac_schema_validators.py
  - templates/scripts/commit_guardian/check_ac_schema.py
  - scripts/ac_store/validate_ac_schema.py
---

# ADR-079: Front-End Declarations Never Enter covered_by

## Status

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-10-23 |
| **Author** | adr-author (ticket `44_TICKET-20261023-GE-124g-1`, EPIC-EveryScreenSaysWhichRequirementItIs) |
| **Supersedes** | None |

---

## Context

The GE-124 tree ("the frontend declares what it renders") lets a front-end file name the
acceptance criteria it serves. It can do this in two ways: a component-level declaration
(an `@ac` comment at the top of a `.tsx`, `.jsx`, `.vue`, `.svelte` or `.html` file, per
GE-124a-2), or an element pin (a `data-ac="..."` attribute on a rendered element, per
GE-124b-1). Both are cheap and machine-readable signals that a criterion is connected to
running code. Neither one asserts that the criterion works.

The parent criterion
[GE-124g](../../acceptance-criteria/guardrail-engine/GE-124-frontend-declares-what-it-renders/GE-124g.yaml)
states the risk directly. Every cheap signal of this shape in this repo has eventually
been read as proof of correctness by something downstream. If a declaration lands in an
AC record's `covered_by`, a field that means "something asserts this", GE-124 will have
automated the phantom-done defect that the guardrail engine exists to prevent. The false
confidence would also look rigorous, because a machine wrote it. The mock-data artifact
`frontend-ac-declarations.mock.json` pins the case: KM-ADM-004 is pinned on a real
element and has `covered_by: []`.

This ADR records the store-side half of that rule, as specified in
[GE-124g-1](../../acceptance-criteria/guardrail-engine/GE-124-frontend-declares-what-it-renders/GE-124g-1.yaml).
It is written now because four facts about the current store make the wrong outcome the
default one if nothing is decided:

1. **There is no field for a declaration today.** `config/ac_store_schema.json` defines
   `covered_by` ("test file paths ... child AC IDs, or other references that verify or
   cover this criterion") and `implemented_by` ("source file paths that implement this
   criterion"). A writer looking for somewhere to put a front-end path will pick one of
   those two.
2. **The JSON schema cannot tell the values apart.** A front-end component path is a
   valid string, so it passes every `items: {type: string}` check. A rule that lives
   only in the JSON schema rejects nothing.
3. **`covered_by` legitimately holds front-end paths.** A front-end test file
   (`__tests__/realization-badge.decisions.test.tsx::...`) has the same in-scope
   extension as the component it tests. A naive "no `.tsx` in `covered_by`" rule would
   refuse every legitimate front-end coverage entry.
4. **The commit hooks see only the staged record.** `check_ac_schema.py` validates each
   staged AC file individually. The rule has to be judgeable from one record's own
   `covered_by` values, with no lookup into the front-end tree.

ADR-008
([AC store schema and ID-format enforcement](ADR-008-ac-store-schema-id-format-enforcement.md))
established that store-shape rules are enforced mechanically at commit time.
ADR-050
([runtime-reachability guard refuses, not warns](ADR-050-runtime-reachability-guard-refuses-not-warns.md))
set the precedent that a guard against a phantom-done vector refuses outright, with no
warn tier. This ADR applies both to the new fields.

---

## Decision

### 1. Two new fields, and only these two, hold declarations

`config/ac_store_schema.json` MUST define two new optional AC-record fields. Both are
arrays of strings and both default to `[]`:

- **`declared_by`** holds the repo-relative path of every front-end file whose
  component-level declaration names this criterion. It holds component-level
  declarations only.
- **`pinned_by`** holds the stable pin slug (the GE-124b-1 `AcDeclaration.id`, for
  example `decl-realization-badge-live`) of every rendered element that pins this
  criterion. It holds element pins only.

There MUST be two fields, not one merged field. The two declaration surfaces are
non-interchangeable everywhere else in the GE-124 tree (GE-124b-2, GE-124c-1-i), and a
merged field would make them indistinguishable to every reader.

### 2. A declaration MUST NOT be written to `covered_by` or `implemented_by`

Every tool and agent that records a declaration or a pin against a criterion MUST write
it to `declared_by` or `pinned_by` respectively. It MUST leave `covered_by` and
`implemented_by` byte-identical to their prior values.

- `covered_by` is ruled out because it means "something asserts this", and a declaration
  asserts nothing.
- `implemented_by` is ruled out because it records a link established by completed work.
  A declaration is an unverified claim a file makes about itself at the moment it is
  written. If declarations went into `implemented_by`, that field would sometimes mean
  "built" and sometimes "says it is built". This reason MUST be stated in
  `docs/reference/ac-schema.md` next to the field definitions, so that a later author
  cannot re-fold the two without reading why they were separated.

### 3. The detection rule

A `covered_by` entry is a **misplaced declaration** when either of the following holds.
The rule is evaluated per entry. An entry of the form `<path>::<test name>` is judged on
its `<path>` part.

- **(a) Pin slug.** The whole entry matches the pin-slug shape `^decl-[a-z0-9]+(-[a-z0-9]+)*$`.
  The entry belongs in `pinned_by`.
- **(b) Front-end source path.** The path part ends in one of the GE-124a-2 in-scope
  front-end extensions (`.tsx`, `.jsx`, `.vue`, `.svelte`, `.html`) **and** is not a
  test or story file. The entry belongs in `declared_by`.

A path is a test or story file, and is therefore **not** a misplaced declaration, when its
basename contains `.test.`, `.spec.` or `.stories.`, or when any of its directory
segments is `__tests__`. This mirrors the GE-124a-3-ii test-file and story-file
exclusions. The exclusion MUST be applied before the rejection, or every legitimate
front-end test reference is refused. (GE-124a-3-ii's third exclusion, the generated-file
marker, reads file content and cannot apply to a path string. A generated non-test file
in `covered_by` is still not a test, so it is rejected.)

Child AC IDs (`GE-124g-1-i`), Python test paths, and test references with any other
extension never match (a) or (b), so the rule leaves them untouched.

### 4. Enforcement lives in the validation path the commit hook runs

- The rule MUST have exactly one definition, a function in
  `templates/scripts/commit_guardian/_ac_schema_validators.py`. A second implementation
  MUST NOT be written.
- `templates/scripts/commit_guardian/check_ac_schema.py` MUST apply that function to
  every staged AC record. A violation MUST make the hook exit non-zero.
- `scripts/ac_store/validate_ac_schema.py` MUST reach the same definition through an
  import bridge, never through a copy, so that the bulk pre-flight and the commit hook
  cannot disagree. `templates/scripts/commit_guardian/_test_spec_entry_bridge.py` is the
  existing pattern for one rule reached from both directories.
- A rule that only computes a rejection that no entry point enforces is inert. The
  acceptance test for this decision MUST therefore run the entry point as a subprocess,
  the way the hook runs it, and not call the function directly.

### 5. The report names the criterion, the value, and the right field

Each rejection MUST name three things: the criterion ID, the offending `covered_by`
value, and the field the value belongs in (`declared_by` for (b), `pinned_by` for (a)).
That makes the fix a single move.

### 6. No opt-out of any kind

The rejection MUST hold for every AC record, whatever its `change_target`, `status`,
`readiness` or `work_status`. There MUST NOT be a warn tier, a per-item exception, an
allowlist, or a configuration key that relaxes it. The validator MUST NOT read any
configuration to decide whether the rule applies. GE-124d's escapes govern whether a
file must declare and have no application here. The configuration surfaces themselves
are tested for the absence of such a key under GE-124g-1-i.

### 7. These fields are a record, never evidence

Writing `declared_by` and `pinned_by` is the business of the GE-124 recorder. A gate
MUST NOT read them as evidence. In particular, the GE-124e-2 declaration gate MUST scan the
front-end source and MUST NOT consult these fields, because they are the recorded
projection of that scan, and a gate that read them would be checking the store against
itself.

---

## Consequences

### Positive

- The one substitution GE-124g names as "place 1 of four" (the store) is closed
  mechanically at commit time, not by convention. Nothing can turn a signpost into a
  coverage claim by writing it into the wrong field.
- `covered_by` and `implemented_by` keep one meaning each. Coverage and proof-of-done
  readers do not need to learn to subtract declarations.
- Because the rule judges one record's own values, it fits the per-file model of
  `check_ac_schema.py` and needs no front-end tree lookup and no new hook.
- Rejection messages name the destination field, so a writer who made the mistake fixes
  it in one edit.

### Negative

- The detection rule is a shape heuristic. A front-end test file that follows none of the
  recognised conventions (no `.test.` / `.spec.` / `.stories.` infix and not under
  `__tests__`) is refused from `covered_by`. Such a project MUST rename the test or move
  it under `__tests__`. No exception can be configured (§6), by design.
- A non-front-end coverage reference that happens to start with `decl-` and contains only
  lowercase segments would be refused as a pin slug. No such entry exists in the store
  today, and the `decl-` prefix is reserved for pin slugs from here on.
- The in-scope extension list is duplicated in spirit between this rule and the GE-124a-2
  declaration reader. If GE-124a-2 adds an extension, this rule MUST be updated in the
  same change, or a new-extension component path can slip into `covered_by`.

### Operational

- `scripts/ac_store/validate_ac_schema.py` gains a dependency on the commit-guardian
  validator module. Any module it imports MUST be in the build deploy map
  (`scripts/build_phases_ac_store.py`), or the deployed validator raises
  `ModuleNotFoundError` at hook runtime (see CLAUDE.md, "New Hook / Gate Dependencies Must
  Be in the Build Deploy-Manifest").
- Existing records are unaffected: no store record carries a front-end path or `decl-`
  slug in `covered_by` today. A record that does will be refused the next time it is
  staged.
- `docs/reference/ac-schema.md` MUST document `declared_by` and `pinned_by` beside
  `covered_by` and `implemented_by`, stating what each field does and does not establish.

---

## Alternatives

- **Write declarations into `covered_by`.** Rejected. `covered_by` means "something
  asserts this criterion", and a declaration asserts nothing. Every downstream
  coverage count, done gate and report would then treat on-screen presence as proof,
  which is the exact defect GE-124g exists to block.
- **Write declarations into `implemented_by`.** Rejected. `implemented_by` records a link
  established by completed work. A declaration is a claim a file makes about itself,
  unverified when written. Folding them makes `implemented_by` mean both "built" and
  "says it is built", which moves the ambiguity one field along without removing it.
- **One merged `declared_by` field for both surfaces.** Rejected. Component-level
  declarations and element pins are non-interchangeable across the GE-124 tree
  (GE-124b-2, GE-124c-1-i). A merged field makes them indistinguishable to every reader,
  and it cannot carry both a file path and a pin slug without a second discriminator.
- **Enforce the rule only in `config/ac_store_schema.json`.** Rejected. A front-end path
  is a valid string and passes every type check. A JSON-schema `pattern` cannot express
  "has an in-scope extension and is not a test file" without becoming a second, untested
  copy of the rule. It would also enforce nothing the hook does not already enforce.
- **Reject any in-scope extension in `covered_by`, with no test-file exclusion.**
  Rejected. Front-end test files share the in-scope extensions, so this refuses every
  legitimate front-end coverage entry, and the rule becomes unusable on any project with
  a front end.
- **A warn tier or a configurable allowlist.** Rejected. A configurable version of this
  rule is not a rule. The GE-124g "no opt-out" clause and the ADR-050 precedent both
  require a refusal, because a warning against a phantom-done vector is read once and
  then ignored.
- **Detect misplaced declarations by looking each `covered_by` path up in the front-end
  tree and checking for an `@ac` comment.** Rejected. `check_ac_schema.py` validates one
  staged record at a time and has no reliable view of the consumer's front-end tree. A
  lookup would make the verdict depend on files outside the commit, and it would be
  silent whenever the tree is absent.
