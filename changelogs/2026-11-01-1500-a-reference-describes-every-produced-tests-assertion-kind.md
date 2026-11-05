---
title: "A reference describes every produced-tests assertion kind, kept in step with the scorers and agent templates"
date: "2026-11-01"
time: "15:00"
type: manual
components:
  - testing_quality
summary: "New docs/reference/produced-tests-eval-assertion-kinds.md (hub) plus four family pages (test-writer, database-setting, sql-test-writer, test-designer) give each of the 31 registered assertion kinds one entry: which sets use it, what it reads, when it passes and fails, a passing and a failing example, and the agent-template sentence it checks, quoted word for word. scripts/evals/README.md links the hub instead of listing kind names; docs/reference/README.md lists the hub."
description: "TQ-200d-1-ii. Hub plus family pages by the user's OQ-1 decision (one page would exceed the 300-line document limit). Drift tests in unit_tests/evals/tq200d1ii/ (5) fail when a registered kind has no entry, a stale entry remains, a kind sits on two pages, a quoted template sentence no longer appears verbatim in the template it names, an entry lacks a part, the README lists kind names inline, or the index does not list the hub once; the kind-to-page mapping is derived from the registering module. The hub states that the pass/fail descriptions and examples are not tested. A pr-reviewer probed about 70 inputs against the real scorers; six entries were corrected (test_fails_on_wrong_result, report_silent_on_setting, report_states_outcome, report_names_no_address, counts_rows_and_non_null, the hub's drift guarantee). Wrong-version gate: all 6 named versions caught."
commits:
breaking: false
---

## Entry

Every check the produced-tests evals run on an agent's output now has a reference entry: what it
looks at, what makes it pass or fail, an example of each, and the sentence in the agent's instructions
it holds the agent to. A hub page explains what these checks are and points to one page per agent
family. Tests keep the pages and the scorers in step, so a check added or removed without its entry,
or a quote that drifts from the template, fails the build.
