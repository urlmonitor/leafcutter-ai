---
title: "feat(guardrail-engine): generate EPIC-SuppressionNarrowsNeverDisables from GE-123"
date: "2026-08-31"
time: 0947
type: manual
components: 
  - guardrail_engine
  - commit_guardian
  - security_scanner
  - ticket_lifecycle
summary: "Turns the approved GE-123 requirements into 27 buildable tickets. Generating them surfaced four separate defects in the epic generator, every one of which would have shipped a broken epic."
description: "Runs the goal-to-epic path over GE-123, producing one ticket per approved leaf requirement in dependency order, with the build order derived from the requirement graph rather than authored by hand. All twenty-seven leaves had been approved beforehand, so the readiness gate cleared on its own rather than being waved through. Nothing is built by this: every requirement remains to-do and the commit only scaffolds the work. The generator's output needed four corrections, and none of them is specific to this epic. The epic name was derived by truncating the goal's title at a character count, producing a name that ended mid-phrase on a dangling article, because the summariser it would normally call was unavailable and the script offers no way to supply a name. Each requirement was stamped with an absolute filesystem path into a local working copy, in files that are committed and read by everyone; sixty records across the store already carry such paths, so only the twenty-seven created here were corrected and the rest are filed rather than swept. The generated plan document was missing every frontmatter field the repository's own ticket guard requires, which means the one existing plan document that passes was hand-corrected too and this has been quietly taxing every generated epic. And the dependency links between tickets referenced filenames without the numeric prefix the generator itself adds, so not one of the eight resolved — an epic whose entire build order rests on those links shipped with all of them dangling. Three of the four were caught by the repository's own hooks rather than by review, which is the encouraging half; the discouraging half is that nobody has fixed the generator, so each new epic pays the same cost by hand. A fifth conflict is recorded rather than fixed: the promise-versus-claim gate reads staged tickets and refuses any whose requirements promise a proof no test yet claims, which no freshly generated epic can satisfy, since its tests are written later during each ticket's own drive. It is a completion-time check firing at creation time, and it makes every generated scaffold unlandable until it is skipped."
breaking: false
---

## Entry
