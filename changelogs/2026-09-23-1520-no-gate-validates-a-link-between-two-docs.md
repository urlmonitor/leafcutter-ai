---
title: "Filed: no commit-guardian gate validates a markdown link between two docs"
date: "2026-09-23"
time: "15:20"
type: manual
components:
  - commit_guardian
  - documentation_system
summary: "One known issue filed against commit-guardian: nothing in the hook family resolves a relative markdown link from one doc to another. check_doc_links covers the code-to-doc direction only, correctly and by design, so the doc-to-doc direction is unowned. Demonstrated by a live case — splitting docs/reference/ac-schema.md produced two links to files that have never existed plus a same-file anchor the split itself orphaned, and every gate passed. Register header counts recounted from disk; the high bucket was stale by one independently of this entry. No hook code changes."
description: "Docs-only. A second candidate KI was WITHDRAWN before writing rather than filed: the claim that PR #861 shipped an unmirrored templates/scripts/commit_guardian/ was checked against origin/main with git ls-tree, which returns nothing for that path — scripts/commit_guardian/ is untracked build output, so there was nothing to mirror and no defect. The local symptom was a stale deploy layer that build.py --force-breaking fixed correctly. Filing it would have put a fabricated defect in the register. WHAT THE FILED ENTRY IS AND IS NOT. It is not a defect in check_doc_links. That hook is registered as 'Check Doc Links Bidirectional Traceability' (commit_guardian.json:1338) and its _comment at line 325 reads 'Code-to-doc traceability link validation' — its job is verifying a code file's DOC_LINKS point at real docs, so get_staged_files() returning only .py and .sql (check_doc_links.py:286) is right for that job. The finding is the other direction. EVIDENCE THAT NOTHING OWNS IT: across templates/scripts/commit_guardian/check_*.py exactly one file contains markdown link syntax at all — check_doc_length.py, in the suggestion text it prints, not in any validation. Several hooks read .md (check_doc_frontmatter, check_doc_coverage, check_adr_cross_reference, check_architecture_scaffolds, check_mermaid_*) and each checks one narrow property; none resolves a link target. WHAT IT LET THROUGH: the ac-schema.md split emitted two See Also links to ac-store-hooks.md and ac-agent-integration.md, neither of which has ever existed anywhere in the repo, and orphaned the same-file anchor #covered_by--scope-convention by moving the heading it pointed at into the child doc. That last one is the instructive case, because check-doc-length's own refusal message pushes authors toward exactly the extraction operation that creates it. All three were caught only because the splitting agent hand-wrote a throwaway checker; check_doc_links ran in the same commit and passed, correctly, having inspected the staged .py files. FIX DIRECTION RECORDED WITH TWO TRAPS: resolve relative paths against the linking file's directory and skip absolute URLs and mailto:; and match GitHub's anchor slug rules, which do NOT collapse consecutive spaces — '## covered_by — Scope Convention' slugs to '#covered_by--scope-convention' with a double hyphen, and a checker that collapses whitespace false-positives on correct links, which is worse than no checker. Recommended severity: warn to start, since 654 tracked .md files under docs/ have never been link-checked. Graded medium, which buckets to low in the filename per this register's convention. REGISTER COUNTS: the header read 'Open: 68 (6 blocker, 25 high, 37 low)'; disk before this entry held 6/26/37 = 69, so the high bucket was already stale by one. Now 6/26/38 = 70, counted from the directory rather than incremented. Resolved: 7, unchanged and correct."
commits:
breaking: false
---

## Entry

One known issue filed against `commit-guardian`. No hook code changed.

### The gap

Nothing in the commit-guardian family resolves a relative markdown link from one
doc to another. `check_doc_links` is the code→doc arm and is correct as written —
it verifies that a **code** file's `DOC_LINKS` point at real docs, which is why it
only reads staged `.py` and `.sql`. The doc→doc arm simply does not exist.

Across all `check_*.py` hooks, exactly one contains markdown link syntax at all,
and only inside the advice text it prints.

### What it let through

Splitting `docs/reference/ac-schema.md` produced two `See Also` links to files that
have never existed, plus a same-file anchor that the split itself orphaned by moving
the target heading into the child doc. `check_doc_links` ran on that commit and
passed. The breakage was caught only because the splitting agent wrote a throwaway
checker by hand.

The orphaned anchor is the sharp case: `check-doc-length`'s refusal message actively
recommends the extraction operation that creates it.

### A second candidate was withdrawn

The claim that a recent PR shipped an unmirrored `templates/scripts/commit_guardian/`
did not survive checking — `git ls-tree origin/main` returns nothing for that path
because `scripts/commit_guardian/` is untracked build output. There was no defect;
the local symptom was a stale deploy layer. It is not filed.

### Register counts

Recounted from the directory: **70 open** (6 blocker, 26 high, 38 low). The header
had read 68 with 25 high — stale by one in the high bucket before this entry.
