---
title: "A known issue claiming the documentation-length check blocks every register edit is withdrawn, because the check does not do that"
date: "2026-09-15"
time: "11:40"
type: manual
components: 
  - commit_guardian
summary: "The entry claimed check-doc-length tests absolute size and refuses any commit touching a known-issues register, including a pure deletion. Measured against a 989-line doc: shrinking it while still far over the limit passes, growing it is refused. The gate ratchets on growth exactly as the file-size gate does for code, and the commit that prompted the entry was appending new entries, which is precisely what the ratchet exists to refuse."
description: "The observation behind the entry was real — a commit was blocked — but the mechanism inferred from it was the opposite of both the documented design and the measured behaviour, and was written up without running the one-minute experiment that separates the two: edit an oversized document downward and re-run. The configuration's own comment states that blocking is survivable only because the gate ratchets, and that 59 of 339 tracked documents are already over the limit, so an absolute block would freeze all of them. The genuine tension the entry was reaching for — append-only registers versus a growth ratchet, where every new entry is growth by construction — was real and was removed independently on the same day by the split of the known-issues tree into one file per issue: the commit-guardian index fell from 4,536 lines to 159, and a new entry is now a new small file rather than growth of an existing one, so the ratchet never fires and no exemption is needed. One observation from the entry is kept because it is true and general: this gate runs in no CI job, since the pipeline invokes only the six acceptance-criteria hooks, so the change from warning to refusing was invisible to every pull request. The entry is moved to the resolved set and kept rather than deleted, so the same wrong diagnosis is not filed again. This commit edits a register and the length check passed with no suppression, which is itself the demonstration."
commits: 
  - e464ca18
breaking: false
---

## Entry
