---
title: "Quick-fix flags a not-opened pull request as an outstanding action (BP-600d-5)"
date: "2026-09-08"
time: "11:33"
type: manual
components: 
  - build_pipeline
summary: "Made /quick-fix clearly flag when a pull request still needs to be opened by hand, instead of silently reporting the run as fully complete."
description: "AC BP-600d-5: quick-fix.js and SKILL.md now report a run that ends with no PR opened as an explicit action_required=true plus a structured outstanding_action object (type, owner, reason, branch, compare_url, command) in the terminal result, not only in prose; the existing PR confirmation gate is unchanged. Covered by 4 new behavioral tests in unit_tests/workflows/test_bp_600d_5.py. A nested-backtick template-literal syntax defect in the push-and-pr prompt was found and fixed in the same change."
---

## Entry

### What shipped

`/quick-fix` used to end a run that opened no pull request exactly as though
nothing were outstanding: `status: "ok"`, `pr_url: ""`, and a `/quick-fix
complete.` report whose eighth line read `PR: none — not opened`. This was
observed live on 2026-09-08: the fix, AC, test, changelog and commit all
landed correctly, the run reported `ok`, and the PR simply never existed —
the gap was found only by reading the raw payload's empty `pr_url` field.

Fixed under AC `BP-600d-5`. When a run now ends without a PR, the terminal
result carries `action_required: true` plus a structured `outstanding_action`
object (`type`, `owner`, `reason`, `branch`, `compare_url`, `command`), and
the completion message gains an explicit `*** ACTION REQUIRED ***` block. A
caller reading only the structured result — never the prose — can now tell
an action is owed, and has what it needs to act (branch, compare URL, and
the exact `gh pr create` command).

Two points worth stating precisely:

- **The confirmation gate is unchanged and deliberate.** `/quick-fix` still
  does not open a PR unattended — outward-facing actions stay behind
  explicit confirmation. This change only alters how the not-opened ending
  is *reported*.
- **The two `pr_opened: false` endings are now distinguished.** A PR that
  already existed (`pr_url` populated) is done and is NOT flagged as
  outstanding; only the genuinely-no-PR case sets `action_required`.

The change lands on both surfaces — `templates/workflows-js/quick-fix.js`
and `templates/skills/quick-fix/SKILL.md` — per the skill's own dual-surface
rule: a behavioural change made only in the JS leaves the skill file lying
to the next reader.

Covered by four behavioral tests in `unit_tests/workflows/test_bp_600d_5.py`,
each driving the real script through the E2 workflow-engine harness rather
than grepping source: the structured-marker case, the branch/compare-url/
command payload, the three neighbouring paths (PR opened, PR already
exists, push failed) staying unchanged, and the live push-and-pr prompt
still gating on confirmation.

### Also found and fixed

While making the tests pass, a genuine syntax defect was found in the same
change: three pairs of unescaped backticks nested inside a template literal
in the push-and-pr prompt. Raw backticks cannot nest — each pair silently
closed and reopened the enclosing string, corrupting the `agent(...)` call
so the workflow script could not be parsed by the engine at all.

Two things had hidden it, and both generalise:

- `node --check` **passed** on the broken file. CommonJS's implicit module
  wrapper supplies the function scope this script's top-level `return`s
  need, producing a different parse that masked the corruption. Only
  `vm.runInContext()` — how the engine actually loads the script — surfaced
  the error.
- A plain `pytest` run reported `4 xfailed`, not failures:
  `pytest_ac_enforcement` downgrades failures on an AC that is not yet
  `done`, so the tests could not report red without `AC_ENFORCE_STRICT=1`.

### Not changed

`/quick-fix` still does not open pull requests on its own. The
scope-expansion escalation gate that flagged this two-surface change as
over-scope for a single `/quick-fix` run is itself unmodified — it is in
fact what caught the syntax defect above before it could be committed.
