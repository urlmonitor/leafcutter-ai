---
title: "Agents treat a failing Post-merge suite status check as an external hold, not their own failure"
date: "2026-10-12"
time: "15:00"
type: manual
components: 
  - testing_quality
summary: "The runbooks that read pull-request checks now share one rule: a failing Post-merge suite status is reported as an external hold with its message, run and notice, never 'fixed' with diff edits, empty commits or re-run loops, while every other failing check is handled as before."
description: "Agents react to failing checks by debugging their own change. For the Post-merge suite status check that is the wrong reflex: it holds every pull request while main's post-merge lane is not green, and the pull request did not cause it. The building-epics skill now holds the one canonical rule (section 3.6): recognise the check by name, report it as an external hold quoting its message, run link and the open post-merge-red notice, do not edit the diff, push empty commits or re-run it in a loop, never touch the post-merge workflows, scripts/ci, the ruleset or the notices, and add a fix declaration only when the change really touches the notice's failing tests. ticket-supervisor, pull-request, epic-supervisor, build-single-ticket and quick-fix point to it at the place they handle failing checks. The pull-request agent's merge poll no longer treats BLOCKED as mergeable and now fetches each check's description. A recorded evaluation gave each of the six runbooks a pull request where this check was the only failure and one where it failed beside a real test failure; all six reached the intended decision."
---

## Entry
