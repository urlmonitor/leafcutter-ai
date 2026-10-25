---
title: "A plain build no longer copies Claude Code workflow scripts into the Gemini workflows folder, where they blocked every commit (BP-1500g-2-ii)"
date: "2026-10-25"
time: "20:00"
type: manual
components:
  - build_pipeline
  - commit_guardian
summary: "Fixed a build step that copied the nine Claude Code workflow scripts into .gemini/workflows/, where check-output-drift reported them as gaps no rebuild cleared."
description: "1 commit (fix). scripts/build_capability_merge.py: _sibling_capability_dir now carries a contested item to <output_root>/gemini/<family>/ only when the package's own output there already holds that name. Before, a plain build over a copy-strategy maker workspace merged into the real .claude/workflows directory and copied all nine *.js scripts into gemini/workflows (antigravity's commands-family markdown). The next copy build put them in .gemini/workflows, and check-output-drift refused every commit with gaps=9. New AC BP-1500g-2-ii (child of BP-1500g-2); tests unit_tests/portability/test_bp_1500g_2_ii.py; known issue KI-CG-20261023-output-drift-gaps-on-gemini-workflow-scripts filed as resolved."
commits:
breaking: false
---

## Entry

In a workspace made by the workspace maker, running a plain build and then rebuilding the
maker's way used to leave nine Claude Code workflow scripts in the Gemini workflows folder.
The output-drift check then refused every commit, and no rebuild cleared it.

A plain build now copies an item to the Gemini side only when the package has its own copy of
that item there. Skills, agents and hooks the adopter changed still win on both platforms. A
workspace built before this fix still needs `.leafcutter/gemini/workflows/*.js` and
`.gemini/workflows/*.js` deleted by hand.
