---
title: "Tests can name the wrong versions they must catch, and discrimination is a test kind"
date: "2026-09-25"
time: "19:00"
type: manual
components:
  - testing_quality
  - ac_store
summary: "Acceptance criteria can now ask for a discrimination test (one that goes red under a named plausible wrong implementation, not only when code is missing) and can list the wrong versions a test must catch in must_catch, which reaches the generated ticket word for word. The commit gate names the offending entry and rule when either is malformed."
description: "TQ-500f-1, TQ-500f-1-i, TQ-500f-2-i and the python-coder part of TQ-500f-2 (fast lane, manually orchestrated). discrimination is added to both angle enums (ac_store_schema.json, test_requirements.schema.json), the generator's angle mirror and the taught set in test-writer.md as a conditional angle; the BP-1100g-1 lockstep test is widened to a three-way check that names the list missing a kind. must_catch is an optional non-empty list of non-blank strings on test_spec[] items, copied verbatim onto generated test entries and never added on the fallback route. Entry-naming validation messages run in both validate_ac_schema.py and the real check-ac-schema commit hook (via a bridge that prints a WARNING if the shared validator cannot be imported)."
commits:
breaking: false
---

## Entry

An acceptance criterion can now say which believable mistakes its tests must catch, such as
"revert the fix" or "drop the second condition", and that list travels unchanged to the
ticket the test writer reads. A new test kind, discrimination, asks for a test that fails
against a plausible wrong implementation, not just against missing code. When either is
written wrongly, the commit is refused with a message that names the entry and the rule.
