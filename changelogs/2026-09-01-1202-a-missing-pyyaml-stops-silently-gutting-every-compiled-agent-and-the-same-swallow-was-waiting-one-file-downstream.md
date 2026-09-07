---
title: "A missing pyyaml stops silently gutting every compiled agent, and the same swallow was waiting one file downstream"
date: "2026-09-01"
time: "12:02"
type: manual
components: 
  - build_pipeline
summary: "Fixed a build defect where a missing pyyaml dependency silently stripped every compiled agent of its name, description, model and tools while the build reported success, then closed a second copy of the same swallow that review found waiting in the registry validator."
description: "2 commits (22d3b08e8, 5dbe6fb65) on build_pipeline, closing KI-BP-019. template_compiler.py caught ImportError on yaml and set a module-level flag with no output on any stream; parse_frontmatter then returned {} for every template, so every compiled agent silently lost name, description, model and tools, the sign-off and verification blocks that key off those fields never appeared, and skills that should have been withheld by internal or deprecated flags shipped anyway — while the build printed its usual file count and exited 0, the largest silent degradation in the pipeline and invisible in the one place anyone would look. Fixed with a hard, unguarded import yaml (pyyaml is already a hard dependency per requirements-dev.txt, just never enforced). Of the three consumers of the removed _YAML_AVAILABLE flag, two — parse_frontmatter's silent {} fallback and _build_output_header's hand-rolled key:value YAML-lite serialiser — existed only to prop up the degraded path and were deleted; the third, compile_skill_template's `if fm and _YAML_AVAILABLE`, had a second legitimate job unrelated to yaml — an empty header when a skill template carries no frontmatter at all — and was narrowed to `if fm:` rather than deleted outright, since a naive flag deletion would have broken that path silently.

A follow-up review found the first fix had relocated the defect rather than closed it: registry_validator.validate_produces_field() caught the same import failure as a bare ImportError, printed one stderr warning, and returned its errors list unchanged — and ModuleNotFoundError subclasses ImportError, so in exactly the pyyaml-missing environment the fix exists for, the frontmatter validator silently checked nothing and reported clean. Now narrowed to ModuleNotFoundError and branched on exc.name: template_compiler itself being absent from the path stays a legitimate warning-and-skip, while any other name (e.g. yaml) means template_compiler is reachable but its own dependency is missing, which now appends a real validation error naming the missing dependency rather than passing silently. A structurally identical swallow in build_glossary.py was checked and left alone, confirmed unreachable because build.py hard-imports template_compiler at module scope before wire_glossary_claude_md() could ever run. The generalisable point: changing a raise site is half a fix — the catch sites for that exception class are the other half, and the first pass did not audit them."
commits: 
  - 22d3b08e8
  - 5dbe6fb65
breaking: false
---

## Entry
