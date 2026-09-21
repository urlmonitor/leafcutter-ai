---
title: "Extract knowledge build phases so build_phases.py can shrink under the GE-127b-1 ratchet"
date: "2026-09-09"
time: "13:19"
type: manual
components: 
  - build_pipeline
  - template_compiler
summary: "Reorganized internal build script code to fit under an automated file-size growth check, with no change in behavior."
description: "Moves build_knowledge_scripts and build_knowledge_sink_declaration out of scripts/build_phases.py into a new scripts/build_phases_knowledge.py, re-exported so scripts/build.py needs no edit. Brings build_phases.py from 2753 to 2709 content lines, satisfying the GE-127b-1 no-growth ratchet and unblocking INF-400c-4-iii and INF-400c-4-i. This satisfies the ratchet only, not the 400-line limit -- build_phases.py remains well over it, as do 17 other files in scripts/."
commits: 
  - f1e0aba76
breaking: false
---

## Entry
