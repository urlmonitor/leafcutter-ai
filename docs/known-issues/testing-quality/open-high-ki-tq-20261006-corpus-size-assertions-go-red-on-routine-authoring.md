---
title: "KI-TQ-20261006-corpus-size-assertions-go-red-on-routine-authoring — six tests assert the size of this repository's own on-disk corpus against a hardcoded integer, so adding a decision record, mockup, mock dataset, changelog entry, flow or ticket turns them red with no defect present"
description: "high — the assertion is `len(<glob over a real repo directory>) == <literal>`, so routine authoring breaks it and the failure is attributed to whatever PR is in flight. Six are red on main 46a6033d (2026-10-06); four more siblings have the same shape and currently agree. Measured by running the tests, not by reading them. The same family already uses the lower-bound form in four places, and the identical defect was diagnosed and fixed once on 2026-10-02 in test_ge_122e_3_protected_diagrams.py."
type: reference
category: reference
status: active
created: '2026-10-06'
last_updated: '2026-10-06'
components:
  - testing_quality
  - knowledge_management
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge/KM-400a-3-i.yaml
  - docs/architecture/adrs/ADR-012-retire-create-ticket-js.md
---

# KI-TQ-20261006-corpus-size-assertions-go-red-on-routine-authoring — six tests assert the size of this repository's own on-disk corpus against a hardcoded integer, so adding a decision record, mockup, mock dataset, changelog entry, flow or ticket turns them red with no defect present

- **Severity:** high. Not because work cannot land (the `Test suite (pytest)` aggregator is currently **not** a required check — `.github/workflows/ci.yml:382-400` exists so re-promoting it is a ruleset checkbox), but because a red set that is not attributable to the change under review is the mechanism by which a real regression hides inside a "N pre-existing failures, all unrelated" story. Graded the same as `KI-TQ-20260927-windows-local-runs-disagree-with-linux-ci`, which is `high` for the same non-attributability reason. **Escalates to `blocker` the day the suite is promoted back to required**: at that point every merge that writes a changelog entry — which the required Changelog gate obliges every merge to do — blocks itself.
- **Status:** open. Not fixed here, by instruction. No AC of its own; see "Fixing this needs ACs first" below.
- **Occurrences:** 6 currently red + 4 latent siblings (table below), plus 3 prior instances of the identical shape already on record: the dynamically-derived `len(...) == 11` in the old AC-4 test of `test_ge_122e_3.py`, which "already broke twice (PR #635, a folder README, patched by excluding it; PR #981, new docs)" and was rewritten on 2026-10-02 — its own module docstring at `unit_tests/commit_guardian/test_ge_122e_3_protected_diagrams.py:24-42` is the write-up.
- **First seen:** 2026-10-06 (this filing; the three oldest were already stale before the commit window below) · **Last seen:** 2026-10-06
- **Reported by:** found while investigating an unrelated CI failure set. Re-measured independently on main `46a6033d` by running the tests.
- **Where:** `tests/knowledge/test_native_{decision_corpus,mock_data,mockup,flow,changelog_entry,ticket}.py` — each in the one test per module carrying `# angle: real_artifact`.

## Mechanism

Each of these tests globs a directory **of the live repository** and asserts the result length equals an integer typed into the test, so any commit that adds a file under that directory makes the test fail — correctly, by its own assertion, with nothing wrong in the code under test.

## Per-test table

Measured by running the six modules on main `46a6033d`: `python -m pytest tests/knowledge/test_native_*.py -q --tb=line` → `6 failed, 199 passed`. "On disk now" is the left-hand side pytest printed, not a separate `ls`.

### Currently stale — red on main right now

| File | Line | Asserted literal | On disk now | Stale | Collection asserted |
|---|---|---|---|---|---|
| `tests/knowledge/test_native_decision_corpus.py` | 18 | `6` | **9** | yes (+3) | `docs/decisions/` `glob("dec-*.yaml")` |
| `tests/knowledge/test_native_decision_corpus.py` | 20 | `6` | **9** | yes (unreached) | `decision.extract(root)` |
| `tests/knowledge/test_native_mock_data.py` | 131 | `3` | **4** | yes (+1) | `docs/product-truth/mock-data/` `rglob("*.mock.json")` |
| `tests/knowledge/test_native_mockup.py` | 124 | `15` | **17** | yes (+2) | `docs/product-truth/mockups/` `rglob("*.mockup.json")` |
| `tests/knowledge/test_native_flow.py` | 174 | `25` | **27** | yes (+2) | `docs/product-truth/flows/` `rglob("*.flow.json")` |
| `tests/knowledge/test_native_changelog_entry.py` | 248 | `551` | **566** | yes (+15) | `changelogs/` + `docs/changelog/` `glob("*.md")` |
| `tests/knowledge/test_native_changelog_entry.py` | 250 | `551` | **566** | yes (unreached) | distinct `native_id` over the same set |
| `tests/knowledge/test_native_ticket.py` | 156 | `1560` | **1565** | yes (+5) | `tickets/` `rglob("*.md")` minus `readme.md` |

The three oldest drifted further between the investigation and this filing: `6` was reported as `8 == 6` and is now `9 == 6`; `551` was `560 == 551` and is now `566 == 551`; `1560` was `1561 == 1560` and is now `1565 == 1560`. That drift-while-being-written-up is itself the finding.

### Same shape, currently in agreement — red on the next addition

| File | Line | Asserted literal | On disk now | Stale | Collection asserted |
|---|---|---|---|---|---|
| `tests/knowledge/test_native_agent.py` | 148, 150, 151 | `61` | 61 | no | `config/agent_registry.json` `agents[]` |
| `tests/knowledge/test_native_skill.py` | 101, 103, 104 | `42` | 42 | no | `config/skill_registry.json` `skills[]` |
| `tests/knowledge/test_native_glossary_term.py` | 287 | `51` | 51 | no | `docs/glossary.md` `###` sections |
| `tests/knowledge/test_native_capability.py` | 100 | `9` | 9 | no | `config/capability_registry.json` `capabilities[]` |

These four are green today and were confirmed green by the same run. Registering an agent, promoting a skill, triaging a glossary term or adding a capability turns each red the same way.

### Secondary corpus-derived literals inside the six failing tests

These sit **after** the first failing assertion in the same test, so they are masked today and will surface one at a time as each count is bumped. Fixing only the first literal in each file does not make the test maintainable.

| File | Lines | Literals | What they count |
|---|---|---|---|
| `test_native_mock_data.py` | 139, 140, 147, 149 | `2`, `9`, `54`, `1` | manifest-registered datasets; entities; records across entities; datasets carrying `shape_version` |
| `test_native_mockup.py` | 132, 133, 134, 135 | `14`, `10`, `5`, `5` | registered mockups; with `render_body`; with `shape_version`; with `realization` |
| `test_native_flow.py` | 183 | `14` | flows whose description differs from the manifest summary |
| `test_native_changelog_entry.py` | 261, 262-266, 268 | `3`, a 3-element rule list, `5` | entries needing lenient-parse recovery; their recovery rules; migration steps in one of them |
| `test_native_ticket.py` | 178, 179 | `44`, `92` | union of frontmatter **keys** across all tickets; tickets whose subtype is `epic` |
| `test_native_agent.py` | 152 | `59` | registry entries whose template has frontmatter |

`test_native_ticket.py:178` is the nastiest of these: `len(fields) == 44` breaks when any ticket introduces a frontmatter key not previously used anywhere in `tickets/`.

### Checked and excluded — same textual shape, not this class

- `tests/test_check_ticket_state_integrity.py:195` (`== 200`) and `unit_tests/ac_store/test_tree_traversal.py:163` (`== 190`) — both count files the test itself wrote under `tmp_path`. Self-consistent by construction.
- `tests/knowledge/test_native_decision.py:200` (`len(raw) == 31`), `test_native_acceptance_criterion.py:139` (`len(schema["properties"]) == 47`), `test_native_capability.py:83` (`len(record.metadata) == 21`) — schema/field-count pins over a synthetic record, not repo corpus. A related but distinct fragility (`test_native_decision.py:196` also pins the schema file's sha256); not covered by this entry.
- `tests/knowledge/test_native_roadmap_phase.py:221` (`active == 2`) — borderline. It counts a **property** of the real `docs/roadmap.json` rather than a file count, and only breaks on a phase-status flip, not on authoring. Note it when the above are fixed.
- `tests/knowledge/test_native_source_file.py`, `test_native_test.py` — glob the real tree and pin **no** count. These are the shape the others should have.

## Why this is not a flaky test

A flaky test gives different answers for the same inputs. These give exactly one answer for a given tree state:

1. **Deterministic.** Same commit, same count, same verdict, every run and every machine. Nothing is timing-, ordering-, network- or filesystem-dependent.
2. **Correct to fail.** `9 == 6` is false. The test is working; re-running it, re-ordering the suite, or raising a timeout changes nothing.
3. **The assertion is the wrong thing to assert.** The AC these tests cover (`KM-400a-3-i`, `work_status: done`) asks that every authored field survive projection losslessly and that absent/null/empty stay distinguishable. It says nothing about how many records exist. And in all six tests the line immediately after the count already proves the lossless-ness exhaustively and self-maintainingly — `test_native_decision_corpus.py:21-24` compares both the full `{id: metadata}` mapping and the `source_path` **set** against the glob; `test_native_mock_data.py:132`, `test_native_mockup.py:125`, `test_native_changelog_entry.py:249` do set equality; `test_native_flow.py:175` compares the full metadata mapping; `test_native_ticket.py:166` indexes `by_path` for every candidate and would `KeyError` on a missing one. So the count literal is redundant with an assertion that is already stronger, and is the only part of these tests that needs hand-maintenance.

So: not flaky, not a bug in the code under test, and not fixable by making the test "more robust". The fix is to change what is asserted — which is why it needs ACs.

## Detection

A CI failure set in which every failing assertion is `assert <bigger-number> == <smaller-number>` and the delta equals the number of files the PR (or a recently merged one) added under the globbed directory. The arithmetic is the tell: if the deltas add up to the added files, no code is broken.

Fast check for the whole class without running the suite:

```bash
grep -rnE "(len\([^)]*\)|\bcount\(\))\s*==\s*[0-9]+" tests/ unit_tests/
```

then keep only the hits whose collection comes from a real repo path (`Path(__file__).resolve().parents[2]`) rather than `tmp_path`.

## Workaround

None that preserves the test. Until it is fixed, read these six failures as baseline noise — **but** re-run the named modules against `origin/main` before accepting that story, because a "pre-existing, all unrelated" narrative over a large red set is exactly how a real regression has been missed here before. Do not bump the literal as a drive-by in an unrelated PR: it is a one-commit reprieve that re-breaks on the next authoring commit, and it puts a change to a test's assertion into a PR whose reviewer is not looking at it.

## Fix directions, with trade-offs

Four options. None is obviously right for all six; the choice is per test and belongs in the AC.

1. **Assert a lower bound** — `assert len(records) == len(paths) >= 6`.
   Cheapest, and **already the convention in this very directory**: `test_native_document.py:203` (`>= 700`), `test_native_component.py:84` (`>= 46`), `test_native_roadmap_phase.py:218` (`>= 13`), `test_native_adr.py:199` (`>= 10`). The same authoring pass wrote both forms; the six just did not get it. Keeps the `len(records) == len(paths)` equality (the part that actually has oracle value) and adds a non-emptiness floor so an extractor returning `[]` still fails.
   *Trade-off:* a bound can no longer detect a *shrinking* corpus — deleting five of nine decision records still passes `>= 6`. Mitigate by setting the floor at today's count, so it only loosens upward.

2. **Assert a property of every record instead of the count** — e.g. every record round-trips, every record's `source_path` resolves, no duplicate `native_id`.
   Strongest oracle and fully self-maintaining: it gets *more* evidence as the corpus grows. Several of these tests already do this on the next line.
   *Trade-off:* says nothing about whether the extractor *found* everything — an extractor that silently returns one record passes every per-record property. Must be paired with option 1's floor or option 3's set equality.

3. **Derive the expected count from the glob** — `assert len(records) == len(paths)`.
   Already present in five of the six, and it is the assertion that actually matters.
   *Trade-off, and the reason it is not a complete answer:* if the test's glob is written to mirror the production glob, it becomes a **tautology** — both sides compute the same thing from the same inputs, so a wrong glob in production is matched by the same wrong glob in the test and the assertion cannot fail. It only has oracle value while the test's glob is *independently authored* from the extractor's (which is the case today: the tests spell their patterns literally rather than importing them). Any fix in this direction must state that independence as a requirement, or the test degrades into self-agreement — the `KI-TQ-009` self-mirroring-oracle failure mode.

4. **Pin a fixture corpus instead of the live one** — copy a frozen set of records into `tmp_path` and assert exact counts there.
   Gives exact, stable counts and full control of edge cases, and most of these modules already have `tmp_path` siblings doing exactly this.
   *Trade-off:* it deletes the one property that makes the `real_artifact` angle worth having — these tests exist to run against the **actual on-disk artifact**, because synthetic fixtures reproduce the author's bias about the data's shape (the `files_touched` column-0-dash defect is the canonical local example, and this repo's CLAUDE.md prescribes real-artifact spot-checks for exactly that reason). Replacing the live corpus with a fixture would be a retreat on coverage dressed as a test fix. Viable only as a *second* test alongside a live-corpus one, never as a replacement.

**Precedent to copy:** the 2026-10-02 fix in `unit_tests/commit_guardian/test_ge_122e_3_protected_diagrams.py` chose a hybrid — pin the protected set **by name** in a module constant, drop the count assertion entirely, and prove the resulting helper load-bearing with a dedicated test that it reports a rename even when a new file keeps the count unchanged. That is options 2+3 with an explicit anti-tautology test, and it is the most complete worked example of this fix in the repo.

## Fixing this needs ACs first

Every option above **changes what the tests assert**, so per ADR-012 this starts with `/plan-feature` authoring ACs, not with a hand-written ticket or a drive-by edit. Two specific reasons it cannot be treated as a mechanical cleanup:

- The six tests carry `# covers:` tags for `KM-400a-3-i` and the `KM-400a-1-*` leaves, all `work_status: done`. Weakening their assertions retires coverage that a done AC is currently credited with. Which guarantee survives, and at what strength, is an AC decision — and if any `KM-400a` leaf genuinely required an exact census, that AC needs amending rather than its test softening.
- Option 3 is only sound under an independence constraint that has to be written down, or the next author "simplifies" the test into a tautology that proves nothing and still reads green.

**Pattern:** a test that measures its own repository instead of the behaviour it was written to check. It then reports the repository's growth as the code's failure, on a commit whose author has no reason to connect the two.
