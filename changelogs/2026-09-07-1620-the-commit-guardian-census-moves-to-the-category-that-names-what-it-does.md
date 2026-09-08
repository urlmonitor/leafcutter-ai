---
title: "The commit-guardian census moves to the category that names what it does"
date: "2026-09-07"
time: "16:20"
type: manual
components: 
  - ac-store
  - commit-guardian
summary: "BP-100n-4 and its two children become BP-1600a-2 under BP-1600 counted-from-reality, joining the settings-surface census as siblings; 224 references rewritten across 50 files, with folder-qualified paths handled before bare ids."
description: "BP-100n-4 (+ -i, -ii) is renamed to BP-1600a-2 (+ -2-i, -2-ii) and relocated from BP-100-reliable-builds/ to BP-1600-counted-from-reality/. It is the commit-guardian-surface census; its new sibling BP-1600a-1 is the settings-surface census. Same category -- the population a check walks is taken from reality, never from a list that can omit things -- which is what BP-1600 exists to name, whereas BP-100n's title is about absence-reporting. This is the deferred half of the split that landed earlier; the precondition was the census-ownership amendments merging so their five references to BP-100n-4 were visible to the sweep. Scope measured rather than assumed: 232 occurrences across 50 files, six more than the briefed figure, the extra ones in changelogs and a memory file outside the directories originally scanned; 224 rewritten. The old id is a clean prefix of both child ids, so a single textual pass maps all three correctly -- but 30 of the occurrences are folder-qualified doc_link paths, and a bare-id pass run first produces the right id under the wrong folder, so replacement ran longest-match-first. Stale ids inside amended_by and notes were rewritten, deliberately diverging from the precedent of leaving amendment history untouched: an id is an address rather than a claim, the content did not change, and a stale address preserves nothing while breaking the one thing it carried. Changelog entries keep the old name, because a changelog's subject is the historical event and rewriting it would describe a commit that never touched a file of that name. No covers-tag cites this record, so no criterion-to-code-to-green-test chain was disturbed. Both parents were staged: BP-100n now has four children and BP-1600a has two. No readiness, work_status, priority or criteria changed. Non-AC files touched are reference-sweep edits only: docs/reference/false-green-mechanisms.md, a memory file, two commit_guardian templates and one unit test, each carrying the old id in prose, a docstring or a comment."
---

## Entry
