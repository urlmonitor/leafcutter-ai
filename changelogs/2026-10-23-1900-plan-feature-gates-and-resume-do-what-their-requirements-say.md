---
title: "/plan-feature's covered gate, hand-back resume, gate messages and triage rules do what their requirements say"
date: "2026-10-23"
time: "19:00"
type: manual
components:
  - ac_driven_dev
summary: "A request that is already covered now shows each covering requirement with its title. 'amend' tells the planner which records to amend, and --force runs the full pipeline. A run resumed after the hand-back test-design commit no longer designs and commits the batch a second time. Commit errors keep the hook's own message, cancel messages list each draft's real path, and the final gate lists held requirements apart from the approvable ones. Its abort after a second edit names the test-design stage."
description: >-
  ACD-300a-1/-2: the ac-triage template names the signals behind the
  strategic and behavioral routes, and the rationale names the deciding
  signal. ACD-300a-3: the covered-route gate reads titles through
  read-covering-ac-titles and asks the exact question; amend passes
  amend_acs to it-po; --force on a covered triage routes as strategic.
  ACD-2500a-2-ix-a (new): the resume scan maps
  plan-feature(TEST-DESIGN-HANDBACK) to its own key; the test-design step
  recovers the ids from that commit, skips the designer and the round-1
  commit, and always runs the itpo-handback check before the final gate.
  If recovery fails it falls back to a normal design run. ACD-300g-1-i:
  formatCommitError keeps commitOutcome.message. ACD-300g-4:
  buildCancelMessage matches draft ids to the rule-check report's
  records_to_commit by exact filename stem. ACD-300c-5: the final-gate
  max-retries abort names test-design. ACD-300c-3: held ids are listed
  apart with their reason; an invalid priority value falls back to medium,
  and an approve with no priority stays paused (BO-2300d-1-iii).
  Requirement texts ACD-300c-1/-2/-3/-5 and ACD-300e-1 were amended to
  match the code, and the plan-feature.js header comment describes the
  current stages. plan-feature.js stays over its size limit for this
  change (user-approved hook skip);
  TICKET-20261023-PlanFeatureJsBackUnderSizeLimit pays it back.
breaking: false
---

## Entry
