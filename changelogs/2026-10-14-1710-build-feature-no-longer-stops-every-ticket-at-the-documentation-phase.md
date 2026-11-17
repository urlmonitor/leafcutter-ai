---
title: "/build-feature no longer stops every ticket at the documentation phase"
date: "2026-10-14"
time: "17:10"
type: manual
components: 
  - build_orchestration
summary: "/build-feature no longer halts every ticket at the documentation step: inside a build, that step now writes the required docs itself, following the matching specialist rules."
description: "BO-2200c-5-vii, commit 3dde0c665. In build-feature.js the documentation-expert dispatch prompt now carries a leaf-mode instruction: classify each required doc, read the chosen specialist template and canonical how-to, author the doc following its rules, and never hand off to a specialist absent from the ticket agents map. Behaviour-preserving removals bring build-feature.js under its size ratchet. New behavioural test runs the workflow through the engine harness and asserts on the prompt, with a pr-reviewer negative control."
commits: 
  - 3dde0c665
breaking: false
---

## Entry

Until now, any ticket in a /build-feature run that needed documentation stopped at the
documentation step, because a build cannot hand work on to another agent and the
documentation step could neither pass the job to a specialist nor write the doc itself.
Inside a build, that step now writes the required docs itself. It follows the rules of
the specialist that would normally have written each one, and it never hands off to a
specialist the ticket does not list.
