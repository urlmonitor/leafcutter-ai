---
title: "Jev trial: criterion to existing category (or none)"
description: "Live trial of 82 which-existing-category-asks-the-same-question choices against 7 mock categories, behind the p >= 0.8 threshold in decision dec-a070edfb6465bced."
type: explanation
status: active
created: 2026-10-05
last_updated: 2026-10-05
components:
  - decision_kernel
---

# Jev trial: criterion -> existing category (or none)

Evidence for kernel run `run-b5af8c7fae2248ba`, AC DK-300b. Trial only; no decision is made here.

## What was run

- Provider: the kernel's own `TypeSafeJevAdapter.from_config` (transport `classifier`, model `jev-latest`), `kernel_config.default.json` limits (20 questions/call, 60000 state chars). No tracer (no Langfuse traces written).
- One `choice` question per candidate. Choices: the 7 non-retired gold categories (description = preferred label + alternative labels, with the candidate's own exact wording removed) plus `__NONE__`. Retired `cat-40cc613f737e3323` left out (its member moved to `cat-d15d52392d7aa94c`; labels duplicate).
- State per call (as in `kernel/scheduler/routing.py`): `task.goal` plus `candidates.<id>` for that call's candidates only; ids are opaque (`c01`..), criterion ids are not shown to Jev.
- Candidates: **22 in-category** (every sighted wording in an active gold category), **56 true-none** (every other published or mined wording in `rv_corpus.json`), **4 pair probes**; total **82** questions. Excluded: 7 mined wordings from `run-b5af8c7fae2248ba` (this decision's own criteria; circular).
- Calls: **5**; tokens: 74760 in / 15488 out; cost **$0.00314** (estimated: input tokens x configured price 4.2e-08; no output price configured). Model reported: jev-1.13.0.
- Accepted merge at threshold t: choice != `__NONE__` and p(choice) >= t. Precision = correct accepted merges / accepted merges; recall = correct accepted merges / in-category candidates; none-rate = true-none candidates with no accepted merge.

## Metrics

### Gold set as-is (crit.small_to_maintain counts as a maintainability member) (n=78)

| threshold | accepted merges | precision | recall | false merges (on none / wrong cat) | none-rate on true-none | same with conf>=0.5 gate: precision / recall / false merges |
|---|---|---|---|---|---|---|
| 0.5 | 23 | 78% (18/23) | 82% (18/22) | 5 (5 / 0) | 91% (of 56) | 81% / 77% / 4 |
| 0.7 | 16 | 94% (15/16) | 68% (15/22) | 1 (1 / 0) | 98% (of 56) | 94% / 68% / 1 |
| 0.8 | 12 | 100% (12/12) | 55% (12/22) | 0 (0 / 0) | 100% (of 56) | 100% / 55% / 0 |

### crit.small_to_maintain treated as NOT maintainability (the caller's pair) (n=78)

| threshold | accepted merges | precision | recall | false merges (on none / wrong cat) | none-rate on true-none | same with conf>=0.5 gate: precision / recall / false merges |
|---|---|---|---|---|---|---|
| 0.5 | 23 | 78% (18/23) | 86% (18/21) | 5 (5 / 0) | 91% (of 57) | 81% / 81% / 4 |
| 0.7 | 16 | 94% (15/16) | 71% (15/21) | 1 (1 / 0) | 98% (of 57) | 94% / 71% / 1 |
| 0.8 | 12 | 100% (12/12) | 57% (12/21) | 0 (0 / 0) | 100% (of 57) | 100% / 57% / 0 |

### Without the 3 borderline true-none wordings (crit-easy-to-adopt, crit-human-authority-kept, crit.human_approved_git_record) (n=74)

| threshold | accepted merges | precision | recall | false merges (on none / wrong cat) | none-rate on true-none | same with conf>=0.5 gate: precision / recall / false merges |
|---|---|---|---|---|---|---|
| 0.5 | 20 | 90% (18/20) | 82% (18/22) | 2 (2 / 0) | 96% (of 52) | 94% / 77% / 1 |
| 0.7 | 15 | 100% (15/15) | 68% (15/22) | 0 (0 / 0) | 100% (of 52) | 100% / 68% / 0 |
| 0.8 | 12 | 100% (12/12) | 55% (12/22) | 0 (0 / 0) | 100% (of 52) | 100% / 55% / 0 |

Raw top-1 (no threshold): correct category on 82% of in-category candidates; `__NONE__` chosen on 91% of true-none candidates.

## Confidence distribution (p of the chosen label; Jev confidence)

| group | n | p(choice) histogram | p min..max | confidence histogram |
|---|---|---|---|---|
| correct_category_pick | 18 | {'[0.50,0.70)': 3, '[0.70,0.80)': 3, '[0.80,0.90)': 3, '[0.90,0.95)': 3, '[0.95,1.00)': 6} | 0.54..0.99 | {'[0.00,0.50)': 1, '[0.50,0.70)': 3, '[0.70,0.80)': 3, '[0.80,0.90)': 2, '[0.90,0.95)': 3, '[0.95,1.00)': 6} |
| wrong_category_pick_on_positive | 0 | - | -..- | - |
| missed_positive_chose_none | 4 | {'[0.50,0.70)': 2, '[0.80,0.90)': 2} | 0.56..0.85 | {'[0.50,0.70)': 2, '[0.70,0.80)': 1, '[0.80,0.90)': 1} |
| true_none_chose_none | 51 | {'[0.50,0.70)': 2, '[0.70,0.80)': 7, '[0.80,0.90)': 4, '[0.90,0.95)': 5, '[0.95,1.00)': 33} | 0.59..1.00 | {'[0.50,0.70)': 4, '[0.70,0.80)': 6, '[0.80,0.90)': 3, '[0.90,0.95)': 10, '[0.95,1.00)': 28} |
| true_none_chose_category | 5 | {'[0.50,0.70)': 4, '[0.70,0.80)': 1} | 0.51..0.71 | {'[0.00,0.50)': 1, '[0.50,0.70)': 4} |

## Pair probes (a probe category built from one side of a related-but-different pair)

| probe | expected | Jev choice | p(choice) | p(probe category) | confidence |
|---|---|---|---|---|---|
| maintainability (cat-73d2 removed) vs probe category {crit.small_to_maintain}; caller expects none, gold would expect the probe | __NONE__ | __NONE__ | 0.98 | 0.01 | 0.97 |
| both_hosts vs probe category {crit.one_source} | __NONE__ | __NONE__ | 0.61 | 0.39 | 0.55 |
| one_source vs probe category {crit.both_hosts} | __NONE__ | __NONE__ | 0.73 | 0.26 | 0.70 |
| human_authority vs probe category {crit.approval_unit_and_path} (+ its real category) | cat-d15d52392d7aa94c | cat-d15d52392d7aa94c | 0.99 | 0.00 | 0.98 |

## Every disagreement with the gold set (top-1 choice != gold)

- **MISS (chose none)** `c67` (crit.reviewable_diffs, published_record): "Does a new decision, an approval or a correction show up as a small, reviewable diff in one file?"
  - gold `cat-52b16c7b5a23106f` (Does every change stay reviewable in normal git review?...); Jev chose `__NONE__` with p=0.85 (p(gold)=0.14), confidence 0.82
- **MISS (chose none)** `c46` (crit.small_to_maintain, published_record) [contested]: "Does the option keep the number of artifacts small enough that one change to the lifecycle touches few files?"
  - gold `cat-73d233fc8b15c735` (Maintainability: does it keep working with little upkeep as decisions ...); Jev chose `__NONE__` with p=0.83 (p(gold)=0.02), confidence 0.79
- **FALSE MERGE** `c34` (crit-human-authority-kept, mined:resume-run-35ecc5ce9780442d-2.json) [borderline_none]: "Below the threshold does the human decide, and above it is the label recorded as Jev's classification with its probability, so no record self-authorizes?"
  - gold `__NONE__`; Jev chose `cat-d15d52392d7aa94c` (Does the option keep the rule that only a human approval creates a dec...) with p=0.71 (p(gold)=0.29), confidence 0.67
- **FALSE MERGE** `c47` (crit-easy-to-adopt, mined:resume-run-57d16125a4a94de0-3.json) [borderline_none]: "Can it be put in place with a small change and used with one command or click per run?"
  - gold `__NONE__`; Jev chose `cat-1dc11c5a2ffa7310` (Can it be built and verified as one ticket?...) with p=0.69 (p(gold)=0.30), confidence 0.64
- **MISS (chose none)** `c59` (crit.edit.7, langfuse_trace): "Use of existing solution: does it build on something that already exists rather than a new tool from scratch?"
  - gold `cat-1df63b670163b54e` (Use of existing solution: does it build on something that already exis...); Jev chose `__NONE__` with p=0.67 (p(gold)=0.32), confidence 0.62
- **FALSE MERGE** `c14` (crit.human_approved_git_record, mined:resume-run-aa2831ba7f0e4ec9-2.json) [borderline_none]: "Is every stored criterion or category reviewable in a Git diff, and does it come into existence only through a human approval, as ADR-060 requires for published records (so criteria mined automatically cannot self-publish)?"
  - gold `__NONE__`; Jev chose `cat-d15d52392d7aa94c` (Does the option keep the rule that only a human approval creates a dec...) with p=0.63 (p(gold)=0.31), confidence 0.56
- **FALSE MERGE** `c38` (crit.flat_filters_readable, mined:resume-run-aa2831ba7f0e4ec9-2.json): "Can the format expose category, decision_type and components as flat top-level fields in the plain-YAML subset that the stdlib knowledge-map parser and the decision-store validator already read?"
  - gold `__NONE__`; Jev chose `cat-6c3eb4f2af148922` (Do the filter fields take their values only from declared vocabularies...) with p=0.63 (p(gold)=0.35), confidence 0.57
- **MISS (chose none)** `c26` (crit.reuses_conventions, published_record): "Does it reuse existing schemas, id minting and validators rather than adding new ones?"
  - gold `cat-1df63b670163b54e` (Use of existing solution: does it build on something that already exis...); Jev chose `__NONE__` with p=0.56 (p(gold)=0.40), confidence 0.50
- **FALSE MERGE** `c48` (crit.approval_unit_and_path, published:dec-93c1c730463c1f3c): "Does the option name the unit a human approves (a category, a criterion, or a criterion's membership in a category) and give it a path like decision records have: staged in the run root, entered into Git only by a human-run publish command, and never created directly from Langfuse or from a mined candidate (ADR-060, ADR-058)?"
  - gold `__NONE__`; Jev chose `cat-d15d52392d7aa94c` (Does the option keep the rule that only a human approval creates a dec...) with p=0.51 (p(gold)=0.49), confidence 0.43

## Categories offered

- `cat-1dc11c5a2ffa7310` (published): Can it be built and verified as one ticket? | alt: Can it be built and verified as one ticket without new infrastructure? / Can the option be built and verified as one ticket without new infrastructure such as a graph database? / Can it be put in place with a small change?
- `cat-d15d52392d7aa94c` (published): Does the option keep the rule that only a human approval creates a decision record and that precedent is evidence, never authority (ADR-060)? | alt: Is every record that enters docs/decisions authorised by a person, either per decision or by a standing rule the person approved in an ADR, and never by a record or a precedent? / Does it keep human approval as the only source of authority, so no record or category self-authorizes?
- `cat-52b16c7b5a23106f` (published): Does every change stay reviewable in normal git review? | alt: Does every published record still go through git review in a pull request? / Does a new decision, an approval or a correction show up as a small, reviewable diff in one file?
- `cat-d6ce5f78c181ebd1` (published): Can a later run find what it needs by filter, without opening every file? | alt: Can a later run select precedent by component, roadmap phase, repository-wide flag and file type or language without opening every record? / Can a later run find candidate criteria or categories by filter and by criterion wording, not only by a decision's question and title, without opening every file? / Can a later run find candidate criteria for a new decision by filter and text without opening every file, as docs/decisions/index.json allows for decisions?
- `cat-6c3eb4f2af148922` (staged, broader cat-d6ce5f78c181ebd1): Do the filter fields take their values only from declared vocabularies that validation enforces? | alt: Are category, decision_type and components top-level plain-YAML fields whose values come from declared vocabularies that validation enforces, with the category list itself a reviewed vocabulary (ADR-061 section 4)?
- `cat-1df63b670163b54e` (published): Use of existing solution: does it build on something that already exists rather than a new tool from scratch? | alt: Does it reuse existing schemas, id minting and validators rather than adding new ones?
- `cat-73d233fc8b15c735` (candidate): Maintainability: does it keep working with little upkeep as decisions and the harness evolve? | alt: Maintainability: does it keep working with little upkeep as the kernel and its traces evolve? / Maintainability: does it keep working with little upkeep as decisions, components and the harness evolve? / Does the option keep the number of artifacts small enough that one change to the lifecycle touches few files?

## Caveats

- The gold set is LLM-drafted mock data the user approved as mock data: indicative, not authoritative. `cat-73d2` (maintainability) is a mined *candidate* nobody has approved, and it contradicts the caller's maintainability vs crit.small_to_maintain pair; both readings are shown.
- The true-none set is "not placed in a category by the gold set", not "verified distinct". 3 wordings are borderline (crit-easy-to-adopt: compound: 'put in place with a small change' (a cat-1dc1 alt label) AND 'one command or click per trace/run'; crit-human-authority-kept: ends 'so no record self-authorizes' (near cat-d15d alt); rv_overlap.py treated it as a positive; crit.human_approved_git_record: compound: Git-diff reviewable (cat-52b1) AND only through human approval (cat-d15d)); a separate table excludes them.
- Small sample: 22 in-category candidates over 7 categories, several near-duplicates (same criterion id, small wording changes), so the recall/precision numbers carry wide uncertainty (one error moves precision by several points).
- Leave-one-out only removes the candidate's own exact wording; near-identical sibling wordings stay in the description (e.g. the crit-use-existing-solution and maintainability variants), which makes those positives easy.
- One run at one seed; Jev answers can vary between calls. The question template (instructions, description format) is this trial's, not a shipped kernel template.
- Gold wordings not present in rv_corpus.json: none.
