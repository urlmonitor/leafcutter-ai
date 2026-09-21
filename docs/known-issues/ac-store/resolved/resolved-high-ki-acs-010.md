---
title: "KI-ACS-010 — The store's test vocabulary is Python-only, so 29 web-app ACs are unvalidatable landmines"
description: "KI-ACS-010 — The store's test vocabulary is Python-only, so 29 web-app ACs are unvalidatable landmines"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-010 — The store's test vocabulary is Python-only, so 29 web-app ACs are unvalidatable landmines

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** RESOLVED 2026-09-01 — both enums widened; see "Resolution" at the end of
  this entry. Kept rather than deleted because the coupling it documents is permanent.
- **Occurrences:** 2
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `config/ac_store_schema.json` → `test_spec[].framework` and
  `test_spec[].type`, against the ACs under `docs/acceptance-criteria/ux-prototyping/`
  and `docs/acceptance-criteria/build_pipeline/BP-1400-web-app-ci-gate/`; **and the
  identical pair** in `config/test_requirements.schema.json` →
  `$defs.test_entry.properties.framework.enum` (`:74`) and `...type.enum`

**Symptom.** `test_spec[].framework` permits exactly `unittest` and `pytest`; `test_spec[].type`
permits exactly `unit`, `integration`, `e2e`, `behavioral`. The repo now contains a Next.js
app under `leafcutter-web/`, and the ACs written for it declare the tests that app actually
uses — `framework: vitest` (40 entries), `framework: playwright` (2), and `type: component`
(12). None of those three values is in either enum, so **every one of those records fails
the store schema right now**, on `main`, unmodified.

**Why nothing has caught fire.** The required `AC store valid` job is diff-scoped by
design — `ci.yml:210` explains the choice, and it is a defensible one. The consequence is
that a record can be invalid indefinitely and cost nobody anything until the moment
somebody edits it for an unrelated reason, at which point they inherit a failure they did
not cause and cannot fix without either widening the schema or falsifying their own test
contract. `ci.yml:212` states the intended bargain plainly — *"Touch a broken record and
you own it"* — which is a fair rule for 57 orphaned children and an unfair one here,
because these 29 records are not malformed. They are correct descriptions of real tests
that the schema has no vocabulary for.

This is the exact shape BO-2900g-3's MIGRATE-DO-NOT-DEFER constraint was written against:
*"'The hook validates staged files only, so existing records are not invalidated in bulk'
is not a mitigation — it converts an immediate, visible breakage into a landmine that
fires on whoever next edits an untouched record for an unrelated reason."* Here the
narrowing was never a decision at all; the schema simply predates the web app.

**Evidence.** 2026-08-25, at `d37687ff`, whole-store run:

```
$ python scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria
AC schema validation FAILED:
  ... 28 files: schema violation at test_spec ...
```

Single-record reproduction, showing it is the enum and not a malformed record:

```
$ python scripts/ac_store/validate_ac_schema.py \
    docs/acceptance-criteria/ux-prototyping/UXP-596-decision-diamonds/UXP-601.yaml
AC schema validation FAILED: ... 'framework': 'vitest', 'type': 'component' ...
exit: 1
```

28 files fail the schema validator; a 29th carries the same vocabulary and is caught only
by the stricter hook (KI-ACS-009). The whole-store run was only possible at all because
KI-ACS-001 was fixed on 2026-08-19 — before that the bare-directory form exited 0 without
reading anything, which is why a population this size went unnoticed.

**Second occurrence, 2026-08-25 — the same gap exists in a second schema, and the two are
coupled.** `config/test_requirements.schema.json` `$defs.test_entry` carries a
byte-identical `framework` enum (`["unittest", "pytest"]`, `:74`) and `type` enum
(`["unit", "integration", "e2e", "behavioral"]`), also under `additionalProperties: false`.
That schema governs the `## Test Requirements` block in a **ticket** body.

The coupling is `generate_ticket_from_ac.py::_test_descriptors_from_spec` (`:1451-1454`),
which copies the AC's `test_spec[].framework` and `[].type` straight through onto the
emitted ticket descriptor:

```python
if item.get("framework"):
    entry["framework"] = item["framework"]
if item.get("type"):
    entry["type"] = item["type"]
```

So widening only the AC schema does not finish the job. A web-app AC would validate,
`/build-ac` would generate a ticket carrying `framework: vitest` / `type: component`, and
those are values the ticket schema forbids — the defect would move one step downstream
rather than being fixed.

That downstream failure would be **silent**, which is the worse half.
`test_requirements.schema.json` is enforced by no hook and no CI gate; it is a declared
contract cited in `templates/agents/test-writer.md` and pinned by two unit tests
(`test_bo_2900g_3`, `test_bo_2900g_4`). Nothing would refuse the malformed ticket — the
generator would simply emit a descriptor violating the contract `test-writer` is
instructed to conform to.

**One precision about the affected records.** They are web-app ACs but not exclusively
web-app *tests*: `BP-1400c-1` pairs a Playwright e2e entry with a `pytest` entry targeting
`unit_tests/build_pipeline/` (it asserts the CI workflow wires the route-smoke job and does
not set `continue-on-error`). Across the 28 validator-visible records the entries are 40
`vitest`, 2 `playwright`, 1 `pytest`. A record is refused if *any* single entry uses an
unlisted value, so a mixed-stack AC is refused on its JS half alone.

**Fix direction.** Widen both enums rather than rewriting 29 records to say something
untrue about themselves: add `vitest` and `playwright` to `framework`, and decide
deliberately whether `component` joins the level axis or those 12 entries move to an
existing level. Note the axis question is genuine and should not be settled by reflex —
`component` is a test **level** (heavier than a unit test, lighter than e2e, renders a
component in a DOM), so it belongs on `type` and not on `angle`; adding it to `angle`
would repeat the level/kind muddle BO-2900g-3 exists to have removed. Whichever way it
goes, per BO-2900g-3 the change must move the affected records in the same commit, not
leave them for whoever touches them next.

**Do both schemas in the one change, and add a test asserting the two vocabularies are
equal.** They are hand-duplicated today with nothing holding them in step, which is how
they drift apart again the moment one is edited alone.

~~Because `config/ac_store_schema.json` is a package surface, the change needs an AC
declaring `package_surface: true` or `check-package-surface-declaration` will refuse the
commit.~~ **This was wrong, and struck out rather than deleted so the next person does not
re-derive it.** `scripts/commit_guardian/_package_surface_registry.py:39-47` enumerates the
four watched files and `config/ac_store_schema.json` is not among them. The claim was
plausible enough to have deterred the fix for a week: it named a real hook, a real flag and
a real refusal, and only the membership was false. Check the registry, not the intuition —
"is a package surface" is a list, not a judgement.

**Where to build it.** Prefer **AR-100** ("Every part of your codebase has a specialist who
genuinely owns it") over a standalone `ac_store` patch. AR-100's criteria require that
there be "no unclaimed technologies where the system quietly falls back on whoever happens
to be nearby", and this is its first concrete instance — the repo gained a TypeScript web
app and the store's test vocabulary never followed. Patched as three enum values, the next
JS tool reproduces it; built as "every vocabulary admits the technologies this repo ships",
it does not.

**Related.** KI-ACS-009 (the pre-flight is weaker than the gate — the reason a
locally-clean folder run does not clear these). BO-2900g-3 (the MIGRATE-DO-NOT-DEFER
constraint this violates). `ACS-200h`, named at `ci.yml:215` as the unbuilt whole-store
backstop, is the check that would have surfaced this on day one.

**Resolution — 2026-09-01, two commits on `fix/bp-1400-test-spec-angle`.**

Both enums widened in one change, as this entry prescribed: `framework` gains `vitest` and
`playwright`, `type` gains `component`, in `config/ac_store_schema.json` **and**
`config/test_requirements.schema.json`. The axis question above was settled the way it
argued for — `component` is a level, so it joined `type` and not `angle`.

`unit_tests/ac_store/test_test_spec_framework_vocabulary.py::test_framework_enums_agree_across_both_schemas`
is the requested equality assertion. It is green before and after the change by
construction: it is a drift guard, not a red-baseline test, and saying so is more useful
than presenting it as evidence the fix worked.

No record was rewritten, because none needed to be — the whole point was that all 28 were
already telling the truth. Afterwards the entire 3,256-record store validates: the
ACS-100i-7 whole-store refusal baseline went from 28 entries to zero, with the guard
reporting `Added: []` and `Messages changed: []`. Removals only, which is the shape that
distinguishes a vocabulary repair from validation quietly getting weaker.

Two things this resolution deliberately did **not** do:

- It did not build AR-100. "Where to build it" above is still right that three enum values
  is a patch and the general rule is the durable fix; the patch was taken because 28
  records were live landmines. AR-100 remains the real answer and is not closed by this.
- It did not touch `config/skills_config.schema.json:232`, which carries the same
  two-value enum on an unrelated field (a Python test-directory map read by `test-writer`).
  Widening it would have been scope nobody asked for.

**And it made a quieter defect louder, so read `KI-ACS-20260901-1520` next.**
`generate_ticket_from_ac.py` hard-codes `.py` on every derived test filename regardless of
declared framework, and `done_proof.py` routes the proof oracle **by file extension** — so
a `framework: playwright` record generates a Python filename and the wrong runner is asked
for evidence. Until 2026-09-01 the schema failure was the only thing keeping that family
visible. Widening makes those records validate and look healthy. It was filed *before* the
widening landed, on purpose.

---
