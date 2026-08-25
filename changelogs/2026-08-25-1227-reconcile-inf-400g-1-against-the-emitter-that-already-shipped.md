---
title: "Reconcile INF-400g-1 against the emitter that already shipped"
date: "2026-08-25"
time: "12:27"
type: manual
components: 
  - infrastructure
summary: "Marks INF-400g-1 done against the emit_event.py delivered in #528, and makes the file executable as that AC requires."
description: "PR #528 built templates/skills/agent-telemetry/scripts/emit_event.py and reconciled BP-400a-1 and BP-400a-1-i, but INF-400g-1 specifies the same artifact at the same deployed path and was left at work_status: todo. That is the drift this repo exists to prevent -- an AC reading todo for work that shipped -- and it was introduced by the very PR that closed the sibling ACs. Marks INF-400g-1 done with implemented_by and covered_by populated. INF-400g-1's criteria also require the deployed script to be executable; the file shipped mode 644 while carrying a #!/usr/bin/env python3 line, which is incoherent on its own terms even though every call site invokes it as 'python <path>'. Its it_requirements accept 'chmod +x OR shebang line', so the weaker reading was arguably already satisfied, but an AC marked done on the weaker reading is a claim nobody can check later. Sets the executable bit and adds a test asserting it, so the mode survives a future rewrite; build.py copies with shutil.copy2, which preserves it, verified against a real deploy target showing -rwxr-xr-x. Parent INF-400g stays todo: g-2 through g-9 are all still unfinished, so no false composite. Note the AC store carries further unreconciled drift in this family -- INF-400c-1, c-2 and c-3 are done-in-fact against ADR-011 and harvest_learnings.py while still reading todo -- which is deliberately NOT touched here and remains open."
breaking: false
---

## Entry
