---
title: "The build writes exactly the bytes it was given, so a Windows install matches what was tested"
date: "2026-09-14"
time: "05:52"
type: manual
components: 
  - build_pipeline
summary: "On Windows, scripts the build deployed no longer diverge from their templates by line endings, and a rebuild now repairs a file that did instead of calling it unchanged."
description: "The build's shared text writer, _write() in scripts/build_phases.py, wrote in text mode, which on Windows turns every line feed into a carriage return plus line feed. Every commit-guardian script, config and manifest it deployed therefore landed byte-different from the template it was built from, and check-hook-parity blocked commits over the difference. Its compare-before-write guard could not see the problem either: it read the existing file back in text mode, which normalises line endings on every platform, so the damaged file compared equal and was counted unchanged -- no rebuild, forced or not, could repair it. The writer and the guard now both work on the exact UTF-8 bytes, so the deployed file matches its template on every platform and a line-ending-only divergence is rewritten rather than skipped (BP-1000a-7). To stay within the file-size ratchet, one small stateless helper moved out of build_phases.py into build_phases_self_description.py with no change in behaviour. Not yet covered: about twenty other build writers share the same text-mode defect -- agent cards, LEAFCUTTER_VERSION, the CLAUDE.md injections and the scaffold writers -- so a fresh Windows build still shows those tracked files as modified by line endings alone. That is recorded in KI-BP-20260910-1240, which this change also corrects: it had claimed a forced rebuild repaired the divergence, which was never true."
commits: 
  - 3f0d1ba1
breaking: false
---

## Entry
