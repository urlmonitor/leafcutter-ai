---
title: "The type checker can read the ticket generator's shared record type again"
date: "2026-09-21"
time: "16:30"
type: manual
components: 
  - ac_store
summary: "Ten modules of the ticket generator declared their shared record type in a way the type checker could not recognise, producing 72 spurious errors. They now declare it so both the type checker and the runtime agree, with no change to what the generator does."
description: "generate_ticket_from_ac.py's 22 _gtfa_* siblings resolve each other through importlib under a prefix computed from __name__, because the package must import both package-qualified and as a bare directory. Ten of them therefore picked up the shared AcRecord alias with a runtime attribute rebind (AcRecord = _gtfa_constants.AcRecord), which mypy reads as a variable rather than a type alias — 26 valid-type errors plus a 46-error attr-defined cascade, 72 in total. Each now carries a TYPE_CHECKING-guarded relative import alongside the unchanged runtime rebind, so the alias stays defined once in _gtfa_constants and the executed path is byte-identical. mypy goes 72 errors to 0 under CI's exact flags. Verified runtime-neutral: both import layouts bind AcRecord in a fresh process, and generating a real ticket from the on-disk store produces byte-identical stdout and stderr before and after."
breaking: false
---

## Entry
