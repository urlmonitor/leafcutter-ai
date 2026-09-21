---
title: "The test-tag gate no longer crashes on Python 3.14 when a test function opens with a docstring"
date: "2026-09-16"
time: "20:00"
type: manual
components: 
  - testing_quality
summary: "check-test-ac-tags refused every commit whose staged tests included a function starting with a docstring, on Python 3.14, by crashing instead of checking. It now reads the docstring the way every supported Python version allows."
description: "The check-test-ac-tags pre-commit hook looks for a covers tag in a test function's docstring by reading ast.Constant.s. That attribute was a deprecated alias and Python 3.14 removed it, so on 3.14 any staged test file with a docstring-first test function made the hook raise AttributeError: 'Constant' object has no attribute 's' and exit 1. The commit was refused by a crash, not a verdict. Earlier commits only got through because none of their test functions opened with a docstring. The hook now reads ast.Constant.value, which exists on every supported Python, and reaches the same verdict it does on 3.13 (TQ-100b-4-iii). A new test runs the hook against a docstring-first function with and without a tag; it fails with the crash on the old hook and passes on the fixed one, and restoring the old attribute read turns it red again."
commits: 
breaking: false
---

## Entry
