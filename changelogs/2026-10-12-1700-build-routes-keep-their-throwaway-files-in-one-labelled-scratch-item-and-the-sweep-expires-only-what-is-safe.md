---
title: "Build routes keep their throwaway files in one labelled scratch item, and the sweep expires only what is safe"
date: "2026-10-12"
time: "17:00"
type: manual
components: 
  - build_orchestration
  - testing_quality
summary: "The single-ticket build, the epic build, the quick fix and the fast lane each obtain a labelled scratch item at the start of the run and tell every process-starting step to set TMPDIR, TEMP and TMP to it. A new sweep removes expired scratch and the commit-check tool's old stash patch files, and never touches scratch whose owning run is still going."
description: "Throwaway files from the build routes landed in the project root, in durable log folders and in the system temp folder. Each route workflow (build-ticket, build-feature, quick-fix, fast-lane-ship) now starts with one shell step that runs scratch.py new-item, recording the long-lived process that runs the drive as the item's owner. Its gate, test-writer, coder, test-runner and review dispatches carry a note pointing TMPDIR, TEMP and TMP at that item. The quick fix keeps its mutation-proof revert files and its pull-request body there instead of /tmp. If no item can be obtained, the run continues as before. scratch.py gains a sweep command. It removes exactly what the expiry rule calls expired, among the scratch location's items and pre-commit's patch<digits> stash files in PRE_COMMIT_HOME or the user cache folder, and counts removals under the scratch kind. Scratch owned by a run that is still going is kept however old it is. pre-commit's installed hook environments and its database are never candidates. To keep the workflow files within the file-size ratchet, decorative separator comment lines were deleted from build-ticket and build-feature, and one explanatory comment run each in fast-lane-ship and quick-fix was turned into a block comment, with no behaviour change. BO-4400f-1, BO-4400f-1-i and BO-4400f-1-ii are marked done."
---

## Entry
