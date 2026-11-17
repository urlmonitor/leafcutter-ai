---
title: "TQ-200d-2-iii: the sql-test-writer eval reads a WHERE-filtered COUNT(*) as a non-NULL count"
date: "2026-11-04"
time: "12:00"
type: manual
components: 
  - testing_quality
summary: "sql_counts_rows_and_non_null accepts a filtered count(*) or count(1) asserted with an equality."
description: "TQ-200d-2-iii: sql_counts_rows_and_non_null now accepts a count(*) or count(1) whose own statement filters on <column> IS NOT NULL (alias allowed) and whose fetched result is asserted with an equality. A predicate in another statement, IS NULL, another column or a >= 0 assertion still fails. Resolves KI-TQ-20261102-sql-non-null-count-misses-count-star-where-not-null."
---

## Entry
