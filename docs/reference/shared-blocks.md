---
title: "Reference: Shared Blocks"
description: "Lookup for route authors: the shared-block marker convention, the identity check, the COMMIT-ANSWER caller contract, and which routes take it. Install failures are on a companion page."
type: reference
status: active
created: 2026-10-23
last_updated: 2026-10-23
components:
  - build_orchestration
  - documentation_system
related_docs:
  - docs/reference/shared-block-install-failures.md
  - docs/reference/shared-commit-step.md
  - docs/reference/workflow-authoring-contract.md
  - docs/architecture/adrs/ADR-030-dual-engine-workflow-support.md
  - docs/acceptance-criteria/build-orchestration/BO-4500-fix-once-every-route/BO-4500b.yaml
  - docs/acceptance-criteria/build-orchestration/BO-4500-fix-once-every-route/BO-4500b-4.yaml
---

# Shared Blocks

Lets the author of a workflow route look up how logic shared by several routes is marked in a template, what the identity check inspects, and how a route reads the COMMIT-ANSWER block's decision. Every install failure with its exact message and fix is on [Install Failures](shared-block-install-failures.md). This page covers the caller side; the commit step's own answer contract is in [Shared Commit Step](shared-commit-step.md).

---

## Marker Convention

A shared block is written once under `templates/workflows-js/_shared/` and copied by the install into every route template that marks a place for it. Workflow bodies cannot `require` or call each other ([ADR-030](../architecture/adrs/ADR-030-dual-engine-workflow-support.md)), so the copy is made at install time.

| Item | Rule |
|---|---|
| Start marker | A line holding exactly `// NAME-START`. |
| End marker | A line holding exactly `// NAME-END`. |
| `NAME` | Upper-case letters, digits and hyphens, beginning with a letter (`COMMIT-ANSWER`, `WORKSPACE-ANSWER`). |
| Block source | `templates/workflows-js/_shared/<name lowercased>.js`, for example `_shared/commit-answer.js` for `COMMIT-ANSWER`. |
| Set of blocks | Every `*.js` file in `_shared/`. No block is listed in code. |
| Set of consumers | Every top-level `*.js` route template holding a marker pair. No route is listed in code. |
| Template pair | Always empty: the start marker line is followed directly by the end marker line. |
| Install | Fills each empty pair with the rendered source, byte for byte, before config placeholders are injected, and refuses to install any route while a problem exists. |
| Block placeholders | `{{config.*}}` placeholders in a block source are resolved at install; the `commit_step_*` ones come from `config/commit_step.json`. |

A template pair:

```javascript
// COMMIT-ANSWER-START
// COMMIT-ANSWER-END
```

The installed route holds the same two marker lines with the block text between them. Edit the source in `_shared/`, never the text inside an installed or template pair.

### Hand-kept pairs

A pair that holds text and has no `_shared` source is a deliberate hand copy. It is allowed only when its name is a key of `_shared/hand-kept.json`, an object mapping the block name to a non-empty reason. The install does not fill it and the identity check reports it as not checked. Without the declaration the install fails ([undeclared hand-filled pair](shared-block-install-failures.md#undeclared-hand-filled-pair)).

### Awaiting-adoption declarations

A source that no route uses yet is allowed only when `_shared/awaiting-adoption.json` maps its name to a non-empty list of the records that will adopt it. An entry with an empty list counts as no declaration. The install prints one line per declared block and continues:

```text
Shared block ALPHA-ANSWER awaiting adoption by X-1, X-2
```

Once any route uses the block the declaration is stale and the install fails ([stale declaration](shared-block-install-failures.md#stale-awaiting-adoption-declaration)).

---

## Install Failures

<a id="install-failures"></a>

The install validates every route and block source in one pass and installs nothing while any problem exists. The full list, with each message and its fix, is on [Install Failures](shared-block-install-failures.md):

- [Unknown block name](shared-block-install-failures.md#unknown-block-name)
- [Empty source](shared-block-install-failures.md#empty-source)
- [Unused source](shared-block-install-failures.md#unused-source)
- [Stale awaiting-adoption declaration](shared-block-install-failures.md#stale-awaiting-adoption-declaration)
- [Text between markers](shared-block-install-failures.md#text-between-markers)
- [Nested blocks](shared-block-install-failures.md#nested-blocks)
- [Overlapping blocks](shared-block-install-failures.md#overlapping-blocks)
- [Unpaired or mismatched markers](shared-block-install-failures.md#unpaired-or-mismatched-markers)
- [Unresolvable config placeholder](shared-block-install-failures.md#unresolved-config-placeholder)
- [Undeclared hand-filled pair](shared-block-install-failures.md#undeclared-hand-filled-pair)

---

## Identity Check

`check_identity(layout_root, package_root, config)` in `scripts/shared_block_identity.py` proves that every installed copy of every shared block equals its source as the install renders it.

| Aspect | Rule |
|---|---|
| What it reads | Every `*.js` under the deployed layout root (the installed routes, never the templates). The layout root is the deployed `.leafcutter` directory. |
| What it compares | The text between each installed marker pair against the block source rendered the install's way (commit-step values, then config placeholders). |
| How it compares | Raw bytes. No newline, encoding or whitespace normalisation: a CRLF copy differs. |
| How consumers are found | From the marker pairs in the installed routes. No route is listed. |
| Drift report | One line per copy: route, block, and the 1-based installed-file line of the first difference. |
| Unpaired markers | A start without an end, or an end without a start, fails and names the route, block and line. |
| Awaiting adoption | A block with no installed copy that is declared awaiting adoption is listed separately and does not fail. A block with no installed copy and no declaration fails. |
| Hand-kept and unknown pairs | Listed as not checked and never fail. |
| Nothing inspected | A run that inspects zero copies fails and names the layout root. |
| Where it runs | In the test suite, `unit_tests/scripts/test_bo4500b_2_deployed_layout.py`, against the shared deployed layout (`shared_reference_layout`) built with the real configuration. It spawns no build. |

Output wording, quoted from the real check:

Pass, one line per block:

```text
ALPHA-ANSWER: 2 copies inspected (workflows/r1.js, workflows/r2.js)
```

Pass with an awaiting block:

```text
ALPHA-ANSWER: 1 copies inspected (workflows/r1.js)
BETA-ANSWER: not inspected because it awaits adoption (awaiting adoption)
```

Drift:

```text
workflows/r2.js: block ALPHA-ANSWER differs from its source at line 2
```

Unpaired marker:

```text
workflows/r1.js: block ALPHA-ANSWER START without END at line 1
workflows/r2.js: block ALPHA-ANSWER END without START at line 2
```

Zero copies inspected (the second line names each undeclared block with no copy):

```text
zero installed copies were inspected under /tmp/bo4500b4_id_ys6eab12/layout/.leafcutter
block ALPHA-ANSWER has no installed copy under /tmp/bo4500b4_id_ys6eab12/layout/.leafcutter
```

Not checked (appended to the pass report, or after the failure lines):

```text
workflows/r1.js: block HAND-X not checked: hand-kept (declared)
workflows/r1.js: block ZETA not checked: unknown block (no source)
```

Fix for a drift line: reinstall the package. A hand edit inside an installed pair is overwritten by the next install, and the source is the only place to change a block.

---

## COMMIT-ANSWER Contract

`templates/workflows-js/_shared/commit-answer.js` defines `decideCommitAnswer(reply, history)`, a pure function: it reads no file and calls no engine primitive. The route dispatches the commit agent, passes the reply and the running history in, and acts on the returned decision. The commit step's own answer keys and statuses are in [Shared Commit Step](shared-commit-step.md).

### Reply keys the block reads

| Key | Use |
|---|---|
| `status` | Envelope status. Must be `ok` for `committed`, `handoff` for `hook_failed` with a `handoff` object, `blocker` otherwise; a disagreement is reported. |
| `commit_answer` | Required object. A reply without one is reported, with nothing inferred from prose. |
| `commit_answer.answer_version` | Must equal the installed `answer_version`; otherwise reported as a contract break. |
| `commit_answer.status` | One of `committed`, `refused`, `hook_failed`, `nothing_to_commit`. |
| `commit_answer.reason_code` | Matched against the installed reason-code families. |
| `commit_answer.reason`, `hook_name`, `failing_files` | Copied unchanged into the decision. |
| `commit_answer.handoff.handoff_target` | Name of the specialist to engage. |
| `commit_answer.handoff.remedy.disposition` | Must be `engage-specialist` to engage. |
| `commit_answer.handoff.remedy.demand` | Must be a non-empty list to engage. |

The block does not read the envelope's `earlier_answers`; it keeps its own `answers` in the history it returns.

### History

| Field | Description |
|---|---|
| `first_paths` | Path list of the first offer, re-offered unchanged. |
| `first_message_file` | Message file of the first offer, re-offered unchanged. |
| `answers` | Every `commit_answer` received so far. |
| `transient_retries_used` | Count of retries spent on `step_` refusals. |
| `specialist_engaged`, `specialist` | Whether and which specialist was engaged. |
| `specialist_reply` | The engaged specialist's reply, passed back in for the next decision. |

### The five decisions

| Decision | Condition |
|---|---|
| `continue` | `answer_version` matches and `commit_answer.status` is `committed`. |
| `retry` | A `refused` answer carries a `step` family code and `transient_retries_used` is below the ceiling; or the engaged specialist reported `ok`. The decision carries the identical `paths` and `message_file`. |
| `engage` | A `hook_failed` answer carries a `check` family code, names a `handoff_target`, has `remedy.disposition` `engage-specialist` with a non-empty `demand`, and no specialist was engaged yet. The route engages the target, then passes its reply back as `specialist_reply`. |
| `stop` | A `refused` answer carries a `policy` family code. No retry can succeed. |
| `report` | Everything else: `nothing_to_commit`, the ceiling reached, a `hook_failed` answer with no usable specialist or demand, a refusal that stands after a specialist was engaged, a specialist reply that is not `ok`, an envelope and answer that disagree, a reply with no `commit_answer`, and any status, reason code or `answer_version` outside the contract. |

A specialist is engaged at most once per commit, and only when the remedy disposition is `engage-specialist` with a usable demand. A refusal that stands after the engage is reported and never forced.

A reply that breaks the contract is reported with `contract_violation` set and the `offending_field` and `offending_value` named; nothing is retried. A reply that is not an object is quoted back up to 2048 bytes with the truncation marked.

### Configured values

The retry ceiling and the reason-code families are not typed in the block. The install fills them from `config/commit_step.json` (`max_transient_retries` and `reason_codes`), so a change to the file reaches every consuming route on the next install. A malformed or missing value fails the install ([unresolvable config placeholder](shared-block-install-failures.md#unresolved-config-placeholder)). The statement below is checked against the file by a test.

`max_transient_retries: 3`

#### Reason-code families

##### policy

- `policy_no_explicit_paths`
- `policy_path_not_a_file`
- `policy_path_outside_workspace`
- `policy_path_not_found`
- `policy_message_missing`
- `policy_message_not_found`
- `policy_message_unreadable`
- `policy_message_empty`
- `policy_protected_branch`
- `policy_detached_head`
- `policy_unattributed_supervised_call`
- `policy_unknown_option`

##### step

- `step_index_locked`
- `step_vcs_error`
- `step_config_unreadable`
- `step_parent_resolver_unavailable`
- `step_timed_out`

##### check

- `check_failed`
- `check_unsettled`

##### nothing

- `nothing_changed`

---

## Routes

| Route | Takes COMMIT-ANSWER |
|---|---|
| fast-lane-ship, plan-feature, quick-fix, finalize-feature, commit (depth-0 routes that commit) | No. No route holds a `COMMIT-ANSWER` marker pair yet. |
| build-feature, build-ticket | Never. They keep the BO-3000a phase-loop handoff routing (BO-3800a-1) and do not take the block. |

COMMIT-ANSWER is declared awaiting adoption in `templates/workflows-js/_shared/awaiting-adoption.json`. The adopting records named there are `BO-4500a-5-i`, `BO-4500a-5-ii`, `BO-4500a-5-iii`, `BO-4500a-5-iv` and `BO-4500b-1-ii`. When the first route adopts the block, the stale declaration fails the install until its entry is removed ([stale declaration](shared-block-install-failures.md#stale-awaiting-adoption-declaration)), and this table is updated in the same change.

---

## See Also

- [Install Failures](shared-block-install-failures.md) — every install failure message and its fix.
- [Shared Commit Step](shared-commit-step.md) — the commit step's own answer contract, which this page does not restate.
- [Workflow Authoring Contract](workflow-authoring-contract.md) — E2 workflow skeleton and the non-transparent edges that make build-time sharing necessary.
- [ADR-030](../architecture/adrs/ADR-030-dual-engine-workflow-support.md) — workflow bodies have no `require`, so sharing happens at build time.
- `scripts/build_shared_blocks.py` — the install-time fill.
- `scripts/build_shared_validation.py` — the install-time validation and its messages.
- `scripts/shared_block_identity.py` — the identity check.
- `config/commit_step.json` — the retry ceiling and reason-code families.
- `templates/workflows-js/_shared/README.md` — the index of block sources.
