---
title: "Resolving an AC-id collision during a merge no longer demands credit for someone else's criteria"
date: "2026-09-28"
time: "18:30"
type: manual
components: 
  - commit_guardian
  - ac_store
summary: "When two branches independently minted the same acceptance-criterion id, resolving the clash by keeping the other branch's record made the governance check demand an amended_by entry for criteria the committer had never written. The only ways past it were to sign the other branch's work as your own or to switch the gate off for the whole commit. The check now asks which version the commit is actually amending from, so a record copied verbatim from the other branch is recognised as unchanged and passes, while a genuine edit made during a merge is refused exactly as before."
description: "Resolves the ACS-400c-2 false refusal observed on PR #862. check_ac_governance decided whether a protected field changed by diffing the staged record against HEAD; during a merge HEAD is only one parent, so a path can hold different content than HEAD without this commit having authored any change. New templates/scripts/commit_guardian/_ac_governance_baseline.py resolves the baseline as the first merge parent whose committed blob is byte-identical to the staged one, else HEAD, and _load_head_content delegates to it. Outside a merge the parent list is [HEAD] alone so behaviour is unchanged; an edit matching no parent also falls through to HEAD; only bytes equal to a parent's are excused, which is proof rather than judgement. Comparison is git diff --cached against the INDEX, and any comparison that cannot be performed resolves to the strict answer. Merge-parent discovery reuses _file_size_ratchet.resolve_parent_revisions, which is octopus-safe and fails closed, rather than a second copy free to get both wrong. Covered by ACS-400c-2-ii and three behavioral tests against a real git repository with a real collision and a real merge in progress; the pre-existing governance tests all run HOOK_NO_GIT=1 and cannot reach this path. Non-vacuity proven against the unfixed hook: the collision case fails with the verbatim production message, the two guard cases pass unchanged. Extracting the git I/O also took check_ac_governance.py from 520 to 503 content lines against its 400-line cap, so the growth ratchet passes without a skip."
commits: []
breaking: false
---

## Entry

Two branches can each invent the same acceptance-criterion id without knowing
about the other. Merging them means picking one record and renumbering the
other — an ordinary thing to have to do.

Until now, picking the other branch's record made the governance check accuse
you of rewriting its criteria. It compared what you were committing against
your own branch's history only, so a file that arrived intact from the other
side looked like an edit you had made. It then asked you to add your name to
the record's list of amenders.

Neither way out was acceptable. Adding your name would put you on record as
the author of wording someone else wrote on another branch, in the very field
that exists to say who wrote what. Switching the check off got the merge
through at the cost of leaving every record in that commit unexamined.

The check now asks a better question: which version is this commit actually
changing something relative to? During a merge that is whichever side the
staged file matches. A file identical to the other branch's is recognised as
untouched and passes without comment. A record you genuinely edited while
merging matches neither side, and is held to the same standard as always — as
is every ordinary commit, where nothing about this changes at all.
