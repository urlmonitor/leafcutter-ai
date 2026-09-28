---
title: "A registered capability that no automation runs refuses the change"
date: "2026-09-27"
time: "17:00"
type: manual
components:
  - build_orchestration
  - commit_guardian
  - build_pipeline
summary: "New check-reachability hook and blocking CI job: a CLI subcommand that no automation script invokes is reported and the change is refused, with two named ways forward (add the invocation, or record a reasoned exemption). Also fixes the build's closure guard, which reported a symlinked helper's sibling imports as undeployed."
description: "EPIC-ARegisteredCapabilityThatNoAutomation: BO-2900b-1 and BO-2900b-1-i. The capability inventory comes from the built argparse parser, callers are real invocations in automation scripts, a reasoned exemption in config/reachability_exemptions.yaml suppresses a finding, and a malformed exemption registry fails closed. ADR-050 records the refuse-not-warn decision. The closure-walk fix in scripts/build_referential_integrity_closure.py recurses on the path as reached instead of its resolved form (KI-BP-20260927 tracks the missing regression test)."
commits:
breaking: false
---

## Entry

A command-line capability that nothing runs can no longer be added quietly. If a change registers
a subcommand that no automation invokes, the commit and the CI job are refused. The message names
the two ways forward: add the invocation in the same change, or record an exemption with a stated
reason. Adding a capability together with its caller passes.

The same change fixes a build defect: on Linux, after an in-place build, the build's
deployed-dependency check followed a symlink and reported helper modules as undeployed, which
aborted every later build.
