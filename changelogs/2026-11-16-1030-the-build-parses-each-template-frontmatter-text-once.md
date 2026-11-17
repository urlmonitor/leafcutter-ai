---
title: "The build parses each template's frontmatter text once"
date: "2026-11-16"
time: "10:30"
type: manual
components: 
  - build_pipeline
summary: "The build asked for the same template frontmatter about nine times over and parsed it again each time. It now parses each distinct text once and hands every caller its own copy, so a fresh-consumer build uses about 10 CPU seconds less and every parsed result is unchanged."
description: "perf(build), BP-900g-8-v, -vi and -vii (parent BP-900g-8). template_compiler.parse_frontmatter made 1,606 calls over 176 distinct texts in one fresh-consumer build, about half of the build's CPU time in the pure-Python YAML stack. The YAML step now sits behind a size-bounded in-process memo (functools.lru_cache, 1024 entries, keyed on the frontmatter text itself, nothing written to disk) and parse_frontmatter returns a deep copy of the stored parse, so callers that edit what they receive cannot affect a later parse. The libyaml loader was measured and rejected: it parses about seven times faster but accepts a tab next to a colon or comma, which yaml.SafeLoader rejects, so a hand-typo'd template would parse into a populated dict instead of the empty one (TQ-600a-11 already records this). Measured on a loaded host, back to back and interleaved: build.py into a docs/ + project.txt fixture took 29.4 s CPU (40.4 s wall) and 26.6 s CPU (36.4 s wall) before vs 18.3 s CPU (21.3 s wall) and 16.0 s CPU (19.0 s wall) after; parse_frontmatter alone over 1,606 calls took 8.3-8.6 s CPU before vs 0.9-1.0 s after. The two fixture output trees differ only in the build manifest's package_root, the log-root paths in knowledge_sink.json and the lock file's timestamp. New test unit_tests/test_bp_900g_8_v_frontmatter_reuse.py (red before: one load per call, no bound). The saving on CI is unmeasured until this change's own CI run completes."
adrs: []
commits: []
breaking: false
---

## Entry
