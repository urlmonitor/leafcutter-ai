---
title: "KI-AR-004 now lists three ways to build the missing Opus escalation, with pros and cons"
date: "2026-10-12"
time: "13:30"
type: manual
components: 
  - agent_registry
summary: "The known issue for architect-review's and conflict-resolver's never-built Opus escalations now sets out three options side by side, so the decision can be made later."
description: "docs/known-issues/agent-registry/open-low-ki-ar-004.md: the follow-up section now compares three options, each with pros and cons: (1) two real deep agents; (2) the gatekeeper re-dispatching its own work on a stronger model through the Agent tool's model override; (3) a small Decision Kernel flow (LangGraph) with deterministic pre-checks, then Jev judging the rubric's known criteria, escalating on low confidence, and an Opus reasoning step only when warranted (ADR-052, ADR-053). No option is chosen; the base agents keep handling large and structural cases until one is."
---

## Entry
