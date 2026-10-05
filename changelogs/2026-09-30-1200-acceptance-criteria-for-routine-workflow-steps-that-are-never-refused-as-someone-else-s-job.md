---
title: "Acceptance criteria for routine workflow steps that are never refused as someone else's job"
date: "2026-09-30"
time: "12:00"
type: manual
components: 
  - build_orchestration
  - agent_registry
summary: "Adds BO-3200f (routine work goes to routes that do not decline it), BO-3200g (a refusal is reported as a refusal) and AR-200c (every agent states its limits), and reconciles them with main's pre-flight registry read."
description: "Three draft acceptance criteria for the defect behind about 40 workflow shell steps still sent to status-checker: BO-3200f, BO-3200g and AR-200c. BO-3200f now names two accepted routes: a fact knowable before the run starts is resolved then and passed in through args (ACD-2100b-5's pre-flight, e4ee392d), and a command step during a run goes to command-step-runner (BO-2400a-1-i). The 2026-09-16 narrowing of BO-3200a-1 and ACD-2100b-5, which had rejected the pre-resolve route, is withdrawn at the user's direction; both are back to main's approved versions. Notes on three resolved known issues are carried over, and KI-BO-20260901-1620 names the new ACs."
breaking: false
---

## Entry

Workflows still send about 40 routine shell, git and script steps to status-checker, an agent registered as not permitted to run them. When it declines, the step fails, and the decline can be read as a real answer. BO-3200f asks that routine work in every workflow go to a route that does not decline it. BO-3200g asks that any decline that still happens be reported as a decline, not as a broken file. AR-200c asks every agent to state its limits. All three are drafts awaiting approval.

BO-3200f names two accepted routes. A fact knowable before a run starts is resolved then and passed in, as the plan-feature skill already does for the agent registry (ACD-2100b-5). A command step during a run goes to command-step-runner. On 2026-09-16 the pre-resolve route had been rejected, and BO-3200a-1 and ACD-2100b-5 were narrowed to match. Main then built ACD-2100b-5 by that route, the user chose to keep it, and both records are back to main's approved text, with the reversal recorded in their history.
