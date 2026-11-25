---
title: "Changelog entries read back exactly as written, even with backslashes, quotes or line breaks"
date: "2026-11-25"
time: "15:31"
type: manual
components: 
  - changelog
  - build_orchestration
summary: "The changelog writer (scripts/changelog/emit_entry.py) quoted text holding special characters but escaped only the double quote. A backslash, as in a Windows path like C:\\data, made the entry's frontmatter unreadable (\"unknown escape character\"), and a line break inside a quoted value was folded to a space when read back, so a multi-line description collapsed into one line. List items were never quoted, so an item holding \": \" was read back as a mapping, and text such as true, 123 or a date came back as a boolean, number or date. Every text value now reads back exactly as it was passed in. Callers must pass the real text: a caller that pre-encoded newlines or doubled backslashes to work around the old defect must stop doing so."
description: "BO-700a-4 (new L2 under BO-700a). scripts/changelog/emit_entry.py: new _yaml_scalar and _escape_char; _yaml_value routes list items through the same rule. A string is written plain only when it starts with a letter, holds only letters, digits, space and _ . / -, has no trailing space and is not a YAML 1.1 bool/null word; otherwise it is double-quoted with backslash, quote, C0/C1 controls, U+2028/U+2029, BOM, surrogates and U+FFFE/U+FFFF escaped. Still stdlib-only. New tests in unit_tests/build_orchestration/test_bo_700a_4.py.\nAdopter note: DIAGraph's scripts/changelog_emit_writer.py pre-encodes newlines (_escape_newlines_for_emit_entry); remove it when the pin includes this change."
breaking: false
---

## Entry

A changelog entry whose text held a backslash (such as a Windows path) could not be read back
at all, and a multi-line description was read back as one line. The changelog writer now
escapes every character that needs it, so whatever text goes in is exactly what comes back out.

If your project worked around the old behaviour by pre-encoding line breaks or doubling
backslashes before calling the writer, remove that workaround when you take this version:
the writer now does it itself, and pre-encoded text would be written back literally.
