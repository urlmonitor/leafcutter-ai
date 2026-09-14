---
title: A shared test fixture wrote a config nothing ever read
date: "2026-09-08"
time: "08:06"
type: manual
components:
  - config_loader
  - build_pipeline
  - testing_quality
summary: "Fixes a portability test fixture that was silently ignoring a build option it exists to let callers vary, because the file it wrote sat somewhere the real config loader never looks."
description: "config_loader.py auto-detects skills_config.json only under a platform directory (.claude, .gemini, .cursor, .github, .cline) at the target root, with no top-level fallback; the shared _bp1500d1_harness.py fixture wrote it directly at the target's top level, so every build the fixture ran used defaults regardless of the output_root_name parameter it accepts specifically to let callers vary that value. Moved the write to <target>/.claude/skills_config.json and updated the one assertion that had described the inert placement. Also corrects an unrelated test failure message that overstated its own search scope."
commits:
  - 0c02cdae1
breaking: false
---

## Entry

### The write and the read disagreed, and nothing said so

`_bp1500d1_harness.py`, the shared out-of-package portability test fixture, wrote its
`skills_config.json` straight to `<target>/skills_config.json`. The real build's
`config_loader.py` auto-detects the file only at `<target>/<platform_dir>/skills_config.json`,
iterating `.claude`, `.gemini`, `.cursor`, `.github`, `.cline` — there is no top-level
fallback. So the file was written, never read, and every build the fixture ran proceeded
on defaults.

### Why it stayed hidden

The written config set `output_root` to the value the build already defaults to. A config
that is never read and one that is read produce byte-identical builds, silently, for
exactly as long as the configured value happens to match the default. It only became
visible once a caller varied it.

That mattered because the fixture takes `output_root_name` as a parameter precisely so
callers can vary it — BP-900h-4 requires that — and a caller varying it was silently
ignored. Differential, same call both sides:

- before: requesting `my_custom_output_root` landed outputs in `.leafcutter`
- after: requesting `my_custom_output_root` landed outputs in `my_custom_output_root`

### The fix

The config now lives at `<target>/.claude/skills_config.json`, the first platform
directory `config_loader.py` checks. `pre_build_target_files` moved from a top-level
`iterdir()` to a recursive file-only walk so the pre-build snapshot still names the exact
relative path instead of collapsing to a directory name, and `test_bp_1500d_1.py`'s
assertion — which had described the inert placement, correct only about the defect — now
follows the corrected path.

### Same shape, unrelated cause

`test_ge_120e_2.py`'s failure message claimed it "checked both templates/ source and the
scripts/ deployed copy." It uses a dotted `scripts.commit_guardian.*` import, which
resolves the deployed copy only — `templates/` is never consulted. A reader following that
message would have gone looking in two places when only one was ever examined. The message
now states what it actually checks.

### Scope note

The spec-side half of this — naming the config's expected location in the relevant AC
record so the silence that licensed the inert placement is closed for future readers —
ships in a separate PR, not this commit.
