---
title: "The ticket generator behind acceptance criteria splits into 22 files with no behavior change, and generated tickets stop pointing at an empty shell"
date: "2026-09-15"
time: "15:00"
type: manual
components: 
  - ac_store
  - build_orchestration
  - build_pipeline
  - testing_quality
  - ticket_creation_pipeline
summary: "The tool that turns acceptance criteria into engineering tickets was split into smaller, easier-to-maintain files with no change in what it produces, and tickets it generates now point engineers at the real implementation files instead of an empty placeholder."
description: "scripts/ac_store/generate_ticket_from_ac.py (4,035 lines, 10x the repo file-size cap) is split into a 386-line re-export shell plus 22 _gtfa_* sibling modules, each 393 lines or fewer. Behavior is unchanged, verified by dir() parity against the pre-split module and by running 123 sampled ACs through both the old and new generator from a deployed layout with 0 stdout/exit divergences. A new test pins the dependency closure the shell derives via importlib at runtime, which static analysis could not see and which left the deploy-manifest build guard blind to the whole generator. 32 not-done ACs that declared the shell as their edit surface are re-pointed to the real sibling modules, so a ticket generated from them now sends a coder to the actual implementation file rather than a file of re-export assignments."
commits: 
  - a202258a
  - a0ae5cba
  - 94d6b2dc
breaking: false
---

## Entry

### The generator was 10x over the file-size limit

`scripts/ac_store/generate_ticket_from_ac.py` — the script that turns an
acceptance criterion into a ready-to-work engineering ticket — had grown to
4,035 lines, ten times the repository's 400-line cap for Python files. It is
now a 386-line re-export shell sitting over 22 new `_gtfa_*` sibling modules,
each at or under 393 lines.

### Nothing about what it produces has changed

This is a pure reshaping, not a rewrite. No function was renamed, no private
helper was made public, and no generated ticket comes out one byte different
than before. That was verified two ways before the split was committed:
comparing the full set of names exposed by the old and new module (zero
removed, zero mismatched), and running 123 acceptance criteria sampled across
the 4,031-record store through both the old and the new generator from a
deployed installation, with zero differences in output or exit code. The
generator's most complex functions also got simpler in the process — for
example the function that builds the agent-assignment section of a ticket
dropped from 455 lines to 92.

### A blind spot in the build system's dependency check was closed

The new shell loads its 22 siblings by a name it computes at runtime, a
pattern the build system's static dependency checker cannot see through. Left
alone, that would have made the checker think the ticket generator depended on
nothing at all, silently defeating the safeguard that is supposed to catch a
generator being deployed without the files it actually needs. A new test now
pins that dependency list explicitly, so the safeguard has something real to
check going forward.

### Tickets generated from 32 acceptance criteria now point at the right file

Separately, 32 not-yet-implemented acceptance criteria had recorded the old
single-file generator as the file their implementation belongs in. Because
that path still technically exists as the re-export shell, nothing caught
this — but a ticket generated from any of those criteria would have sent
whoever picked it up to a file of pass-through assignments instead of the
real code. Each of the 32 has been re-pointed to the actual sibling module (or
modules) its work belongs in, so tickets generated from them now land on
real, workable code from the start. Ten further affected criteria were left
untouched deliberately, because they carry unrelated, pre-existing data
problems that are out of scope for this change and are tracked separately.
