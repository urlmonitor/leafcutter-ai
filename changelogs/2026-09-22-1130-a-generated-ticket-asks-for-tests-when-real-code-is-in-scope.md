---
title: "A generated ticket asks for tests when real code is in scope — and one helper decides, for both generators"
date: "2026-09-22"
time: "11:30"
type: manual
components:
  - ticket_creation_pipeline
  - ac_store
  - build_pipeline
summary: "TKT-500f-6 and its three children are implemented and green. A generated ticket now carries a '## Test Requirements' section whenever its files_touched holds at least one real implementation .py, and each stub names the file it applies to. The classification predicate has exactly ONE owner repo-wide — scripts/ac_store/_gtfa_impl_py.py — reached by both work-item generators, so the two cannot drift. The normative rule is stated once in the reference docs, because the third consumer is a markdown agent template that cannot import Python. Landing this required splitting docs/reference/ac-schema.md, which was 1052 lines against a 300-line limit and could not grow."
description: "Built by hand rather than through /fast-lane-build, which was pointed at this AC first and instead deleted an unrelated remote branch — filed the same day as KI-BO-20260921-fastlane-worktree-agent-acts-on-leaked-conversation. THE RED BASELINE CAME FIRST, AND WAS SALVAGED RATHER THAN REWRITTEN. The four test files plus their three-module harness were written days earlier, verified red, then withheld from PR #844 because CI runs strict AC enforcement and a red baseline cannot land on main. They were preserved on branch salvage/gte-eight-ac-tests, seeded into this worktree unchanged, and re-verified red against the CURRENT tree: 11 failed, 7 passed under AC_ENFORCE_STRICT=1 — notable in itself, because they transplanted with no import errors onto a layout that had been decomposed into 22 new modules by PR #843 in the interim. After implementation: 18 passed, 0 failed. Verified independently by the coordinator, not taken on the coder's report. git diff shows the seven test files as PURE ADDITIONS — no test was edited, weakened, skipped or xfailed to reach green. THE SHARED HELPER. scripts/ac_store/_gtfa_impl_py.py (new, 208 raw / 69 content lines) holds is_implementation_python_path, the single owner of the predicate: a path qualifies when it ends .py AND is not under docs/ AND is not .yaml/.json AND is not under tickets/ AND its basename matches neither test_*.py nor *_test.py. Three thin folds sit over it — qualifying_implementation_paths (per-entry filter, deduplicated, order-preserving), requires_test_requirements_section (the emission decision), annotate_descriptors (names the production surface on each stub) — and none restates the rule. TKT-500f-6-iii-a's AST-fingerprint test scans all of scripts/ and confirms exactly one implementation; it failed on absence before and would fail on duplication later. There is no all(...) anywhere in the change, which is what TKT-500f-6-i's any-vs-all discriminator exists to catch: an implementation requiring ALL paths to qualify passes the single-file case and the all-excluded case and fails only that one test. HOW BOTH GENERATORS REACH IT — and why epic_tickets.py is untouched. The direct path (generate_ticket_from_ac.py) imports the sibling in its _sibling() wiring block and re-exports it; _gtfa_body._build_ticket_body calls it for the gate and _gtfa_tests_section._build_test_requirements_section for the stub annotation. The goal path already shells out to generate_ticket_from_ac.py as a real subprocess, so it reaches the same helper through the same code. Adding an import to epic_tickets.py would have created a SECOND entry point into the predicate — the opposite of what the AC's it_requirements ask. The seam test asserts the two emitted sections are byte-equal AND that each names the implementation file, so the delegation is proven rather than assumed. This is a deliberate reading of 'one shared helper used by both', recorded here because the AC's doc_links relevance text could be read as demanding a direct call. THE EMPTY files_touched DECISION, measured rather than guessed. Neither TKT-500f-6 (Given: at least one qualifying path) nor its sibling TKT-500f-7 (Given: paths present, none qualifying) specifies an EMPTY files_touched. A strict iff reading would treat empty as a hard No. Measured against the real store first: of 1,100 coder-assigned records with no authored test_spec, 769 derive an empty files_touched and 199 more are non-empty with nothing qualifying — a strict iff strips the section from 968 records and turns three currently-green tests red. So empty is treated as NO EVIDENCE and falls back to the prior computed-map classification, while entries-present-but-none-qualifying (the case the seeded tests actually exercise) is a hard No. Documented in the helper, at the gate, and normatively in the reference docs; reversible in one line. STUBS ANNOTATE RATHER THAN APPEND. Each descriptor gains implementation_files: [<paths>] instead of the plan gaining a per-file stub. Appending would change the emitted descriptor count and angle distribution, and test_derived_test_reachability_floor.py asserts over the REAL store that the criterion-tagged count equals the AC's Then-clause count and that the angle set is exactly {criterion, reachability}. Annotating satisfies 'at least one stub per qualifying file' at zero blast radius. DEPLOY MANIFEST, PROVEN NOT ASSUMED. _gtfa_impl_py.py added to AC_STORE_DEPLOY_MAP in build_phases_ac_store.py (the sibling count comment bumped 22 -> 23), and added to the shell's if TYPE_CHECKING: relative-import block — without that, build_referential_integrity's closure analyser goes blind and test_gtfa_sibling_closure_guard.py fails, because the shell resolves siblings via importlib under a COMPUTED prefix that static analysis cannot see. After build.py, the DEPLOYED copy was driven as a subprocess from a fresh process over five throwaway stores written with yaml.dump: impl .py -> section names the file; mixed impl/docs/config -> names only the impl file; test files + tickets/ path -> no section; docs/config-only -> no section; test file + impl file -> names only the impl file. 5/5. THE DOC SPLIT THIS FORCED. it_requirements #4 requires the rule stated once normatively, because the ticket-supervisor is markdown prose and there is deliberately no shared import across the .py/.md boundary — that prose IS the contract. Adding it grew docs/reference/ac-schema.md from 974 to 1037 counted lines against a 300-line limit, and check-doc-length's ratchet refuses ANY growth on an already-over doc while explicitly refusing deletion-to-bypass. Resolved by extracting the ID-format, parent-derivation and covered_by-scope material into a new docs/reference/ac-id-hierarchy.md (165 lines), leaving a pointer, and cross-linking both ways: ac-schema.md is now 916 counted, 58 BELOW its pre-change baseline. Faithfulness was proven before deletion — grep -vxFf of the child against the extracted 133-line slice returned nothing, so every line survived the move. THREE DEFECTS FOUND DURING THAT SPLIT, none of them the task: a killed agent had written its own literal tool-call markup (</content>, </invoke>) into the child doc; it had invented two See Also links to files that do not exist; and the trim itself orphaned a same-file anchor on the covered_by schema row, now repointed cross-file. The last would have shipped broken, because — and this is the finding worth keeping — check_doc_links DOES NOT READ MARKDOWN. Its get_staged_files() returns staged Python and SQL only, so it passed green while the child doc carried two dangling links. Markdown links were validated out-of-band instead: 34 relative links across the three touched docs, 0 broken. AC STATUS. TKT-500f-6-i, -6-ii and -6-iii-a are marked work_status: done via mark_ac_done.py's coverage gate. TKT-500f-6 itself stays todo: it is a composite whose child TKT-500f-6-iii has an unbuilt llm-expert sibling TKT-500f-6-iii-b (the ticket-supervisor template skip-rule), and marking a composite done over an unfinished child is precisely the phantom-done shape this repo's CLAUDE.md documents. implemented_by is left empty deliberately — the store's convention is that it names TICKET files, and this was a direct-commit drive with no ticket. NOT DONE, stated plainly: TKT-500f-5 and -5-i (agent-registry substitution with warnings) and the two standalone ACD records remain specification-only, with authored contracts and no tests. Five results in the regression sweep were wall-clock budget failures on a loaded machine, each timed rather than waved away; one (test_ge_127a_1) fails even in isolation because a clean build takes 56s against a 30s budget, which no change here affects."
commits:
breaking: false
---

## Entry

A generated ticket now carries a **`## Test Requirements`** section whenever its
`files_touched` holds at least one real implementation `.py`, and each stub
names the file it applies to. `TKT-500f-6`, `-6-i`, `-6-ii` and `-6-iii-a` are
implemented and green — **18 passed, 0 failed** under strict AC enforcement.

### One owner for the predicate

`scripts/ac_store/_gtfa_impl_py.py` holds `is_implementation_python_path`. The
AST-fingerprint test in `-6-iii-a` scans all of `scripts/` and confirms
**exactly one** implementation — it failed on absence before, and would fail on
duplication later.

Both work-item generators reach it. The direct path imports it; the goal path
already shells out to `generate_ticket_from_ac.py` as a real subprocess, so it
arrives at the same code. Adding an import to `epic_tickets.py` would have
created a *second* entry point into the predicate — the opposite of what the AC
asks. The seam test proves both paths emit byte-equal sections.

### The tests were salvaged, not rewritten

They were written days earlier, verified red, and withheld from PR #844 because
CI runs strict enforcement and a red baseline cannot land on `main`. Seeded here
unchanged, they re-verified red against the *current* tree — **11 failed, 7
passed** — having transplanted with no import errors onto a layout that PR #843
had split into 22 new modules in the meantime.

`git diff` shows all seven test files as **pure additions**. Nothing was edited,
weakened or xfailed to reach green.

### Two judgement calls, measured rather than assumed

**Empty `files_touched` is "no evidence", not "no".** Neither `TKT-500f-6` nor
its sibling `-7` specifies the empty case. Measured first: 769 of 1,100
coder-assigned records derive an empty list, so a strict reading would strip the
section from 968 records and turn three green tests red.

**Stubs annotate rather than append.** Appending would change the descriptor
count and angle distribution, which a real-store test asserts over.

### The split this forced, and what it exposed

The normative rule had to be stated once in the reference docs — the third
consumer is a markdown agent template that cannot import Python, so the prose
*is* the contract. That grew `ac-schema.md` past a ratchet that refuses any
growth on an already-over doc. Extracting the ID/hierarchy material into
`ac-id-hierarchy.md` brought it to **916 counted lines, 58 below its baseline**,
with faithfulness proven before deletion.

That work turned up a finding worth more than the split: **`check_doc_links`
does not read markdown.** It checks staged Python and SQL only, and passed green
while the child doc carried two links to files that do not exist.
