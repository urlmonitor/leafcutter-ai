---
title: "Fix native knowledge and retrieval type annotations"
date: "2026-10-02"
time: "17:30"
type: fix
components:
  - knowledge_management
summary: "Make native metadata, retrieval, assessment and kernel integration contracts pass the informational type check."
description: "Replace generic object annotations with concrete records and structural ports, preserve transaction result types, narrow optional values, and correct native test comments misread as Python type annotations. Check changed production modules in CI; keep the full pytest job disabled."
tickets:
  - tickets/00_inbox/TICKET-20261002-KM-400a-3-i-annotation-maintenance.md
---

The follow-up checks the original native-data PR targets together with every
changed Python module. Raising validation helpers now declare that they never
return, allowing optional and union values to narrow correctly. CLI credentials
retain their fixed constructor shape, and composed retrievers expose their cleanup
contract. Recursive JSON annotations retain strict value and whitespace validation.

Native test coverage tags remain intact. Their descriptive `# type:` comments use
`# test type:` so mypy does not mistake them for executable type comments. Focused
behavior checks cover metadata, retrieval, query admission, configuration and
assessment. The full pytest CI job remains disabled.
