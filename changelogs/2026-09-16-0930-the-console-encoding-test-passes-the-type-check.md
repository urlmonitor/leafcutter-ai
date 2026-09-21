---
title: "The console-encoding test passes the type check"
date: "2026-09-16"
time: "09:30"
type: manual
components: 
  - build_pipeline
summary: "The BP-100f-4 test read its captured output through stream.buffer.getvalue(). The stream's buffer is typed as a generic binary buffer, which has no getvalue(), so the informational mypy job on PR #826 reported attr-defined. The helper now narrows the buffer to io.BytesIO before reading it. Test behaviour is unchanged."
description: "Follow-up to the fix for the build.py crash on cp1252 consoles (#826). mypy flagged unit_tests/build_guards/test_bp_100f_4_console_encoding.py:100 with '\"_WrappedBuffer\" has no attribute \"getvalue\"' because TextIOWrapper.buffer is typed as a generic binary buffer. _read_decoded() now asserts that the buffer is an io.BytesIO, which is how the test builds the stream, before calling getvalue(). The fix narrows the type rather than suppressing the error. If the stream were ever built differently, the test would fail loudly instead of reading the wrong buffer."
commits: []
breaking: false
---

## Entry
test(build-pipeline): narrow the captured buffer type in the BP-100f-4 test
