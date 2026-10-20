---
title: "Identical relationships are collapsed before a knowledge publication instead of failing it"
date: "2026-10-14"
time: "15:00"
type: manual
components: 
  - knowledge_management
summary: "Knowledge publication now collapses relationships that are identical in every recorded property to one before anything is written, and reports each collapsed group with its source record, locator, target and copy count, stating 0 when nothing was collapsed."
description: "An AC record that listed the same test path twice under implemented_by produced two byte-identical relationships. The store merges relationships on a key derived from the whole relationship, so the two became one in the store while the count check still expected both, and every publication of the repository failed. Publication now collapses such copies before validation and before the first write, using the same identity the store merges on, so relationships that differ in any recorded property, including their source locator, stay distinct. The result's diagnostics name each collapsed group (relationship type, source record path, locator, target and number of copies) and always carry the total collapsed, 0 included. On the revision that held the duplicate, 28,815 loaded relationships become 28,814 with one group reported from TQ-600a-13-ix.yaml. The generation digest is still taken from the content as loaded, so a retry on a revision with a failed earlier attempt keeps its identity. Duplicate node ids are still refused."
---

## Entry
