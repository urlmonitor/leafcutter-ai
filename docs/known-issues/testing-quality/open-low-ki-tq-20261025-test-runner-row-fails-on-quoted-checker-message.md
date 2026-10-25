---
title: "KI-TQ-20261025-test-runner-row-fails-on-quoted-checker-message — the test-runner configured-database row fails report_names_no_address when the report relays the db_check checker's own 'invalid' message, which names the postgres:// scheme"
description: "low — the db_check checker's invalid message says 'expected postgres:// or postgresql:// with a safe host, port, and database segment'. report_names_no_address (scripts/evals/produced_tests_reports.py) treats any bare postgres:// or postgresql:// as an address the agent chose itself; its only exemption is a DSN made of <...> placeholders, and a scheme followed by a space is not a DSN token at all. So a test-runner report that relays the checker's message verbatim fails the configured-database row although its commands were clean and it reported the invalid status correctly. Seen in both the smoke run and the full run of the 2026-10-25 live before-score. The recorded gold report does not quote the message, so recorded scoring stays green."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20261024-produced-tests-db-scoring-residual-misreads.md
---

# KI-TQ-20261025-test-runner-row-fails-on-quoted-checker-message — relaying the checker's message reads as naming an address

> Filed 2026-10-25. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. One row, one assertion, one wording, and the failure is falsely red, never
  falsely green. Recorded gold scoring is unaffected. It does hold the test-runner live score
  below its 1.0 threshold whenever the agent quotes the checker.
- **Status:** open, no AC.
- **Occurrences:** 2, both in the live before-score on 2026-10-25 (Windows 11,
  `run_agent_eval.py --agent test-runner` without `--score-gold`): the one-row smoke run
  (results timestamp `2026-10-25T20:57:07Z`) and the full run (`2026-10-25T20:58:19Z`). In both,
  the `configured-database` row passed `commands_run_checker`, `commands_no_db_address` and
  `report_mentions` (`invalid`) and failed only `report_names_no_address` with
  "the report names an address of its own: 'postgres://'".
- **First seen:** 2026-10-25 · **Last seen:** 2026-10-25
- **Where** (line numbers at `origin/main` `5e5a37380`):
  - `scripts/db_check/_address.py`:54-58, `_INVALID_ADDRESS_MESSAGE`: "… is not a valid postgres
    connection URL (expected postgres:// or postgresql:// with a safe host, port, and database
    segment)." The checker returns it as the `message` of every `invalid` report
    (`scripts/db_check/checker.py`:268-279 `_invalid_report`, :346).
  - `scripts/evals/produced_tests_reports.py`:37-38, `ADDRESS_RE`: its first alternative
    `postgres(?:ql)?://` matches the bare scheme, with nothing after it required.
  - `scripts/evals/produced_tests_reports.py`:31-33 and :68-71, the placeholder exemption:
    `DSN_TOKEN_RE` (`postgres(?:ql)?://\S+`) finds DSN tokens, and `_is_placeholder_dsn` blanks a
    token only when what follows `//` is `<...>` placeholders and separators. `postgres:// or`
    has a space after `//`, so it is no DSN token, is not blanked, and `ADDRESS_RE` finds it.
  - `scripts/evals/produced_tests_reports.py`:74-81 `_address_in` and :84-87
    `report_names_no_address`, which turns the hit into the failure detail.
  - `scripts/evals/sets/test-runner.jsonl`:1, the `configured-database` row, which carries
    `report_names_no_address`; its recorded gold report
    (`scripts/evals/sets/test-runner/recorded/configured-database/report.md`) says the setting
    "is a placeholder, not a usable connection address" and never quotes the message, so
    `--score-gold` passes.

## Symptom

A live test-runner run fails the `configured-database` row on `report_names_no_address` with the
detail `'postgres://'` while every command check passes and the report states the `invalid`
status. The agent did what the row asks: it ran the shipped checker, chose no address of its own,
and relayed the checker's verdict.

## Mechanism

1. **The fixture's setting is a placeholder,** `postgresql://<user>:<password>@<host>:<port>/<database>`
   (`scripts/evals/sets/test-runner/projects/configured-database/.claude/skills_config.json`:4),
   so the checker reports `invalid` with the message above.
2. **A careful report quotes the checker.** The message names the expected schemes,
   `postgres://` and `postgresql://`, with no host.
3. **The address rule cannot tell a scheme name from an address.** The matched text is exactly
   `postgres://`, which only the checker's message supplies here: the setting value is
   `postgresql://…` and is blanked by the placeholder exemption. Probed at `5e5a37380`:
   `_address_in("The checker reported status invalid: " + message)` returns `'postgres://'`;
   the recorded gold report and the bare placeholder DSN return `None`.

## Detection

A `report_names_no_address` failure whose detail is a bare `'postgres://'` or `'postgresql://'`
(no host after it), on a row whose `commands_no_db_address` passed, is this issue. Read the
report for the checker's "expected postgres:// or postgresql://" wording.

## Workaround

Read such a failure by hand; if the only hit is the relayed checker message, count the row as
passing for the before-score. Do not reword the agent template to avoid quoting the checker.

## Suggested fix

Directions only; nothing here is applied.

- **Exempt the checker's own text.** Remove `_INVALID_ADDRESS_MESSAGE` (imported from
  `scripts/db_check/_address.py`, or matched by its fixed wording) from the report before
  `_address_in` searches it, the same way placeholder DSNs are blanked.
- **Or require a host.** Make the scheme alternative of `ADDRESS_RE` match only when something
  other than whitespace, punctuation or a placeholder follows `//`, so a scheme named without a
  host is not an address. This also covers paraphrases such as "expected a postgresql:// URL",
  which fails the same way today.
- Add a negative probe for the relayed message to the TQ-200d-4 report tests either way.

**Related.** The TQ-200d-2 sql-test-writer rows (`scripts/evals/sets/sql-test-writer.jsonl`) do
not carry `report_names_no_address`; per the lane, it was left out of them deliberately because a
report relaying the checker's `invalid` message would trip it. `KI-TQ-20261024-produced-tests-db-scoring-residual-misreads`
lists the other known misreads of the same address checks (`README.rst:10`, `3.11.2.5`,
"does not use localhost" read as addresses); this one was not in it.

**Pattern:** a "names no address" rule that matches the scheme alone, applied to a report whose
correct content includes a tool's message that names the scheme.
