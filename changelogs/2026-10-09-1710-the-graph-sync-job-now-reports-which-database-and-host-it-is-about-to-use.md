---
title: "The graph sync job now reports which database and host it is about to use"
date: "2026-10-09"
time: "17:10"
type: manual
components: 
  - knowledge_management
summary: "Before connecting, the knowledge-sync job prints the database name, host, repository and source revision it resolved, and whether each required secret is present — so a failed run can be diagnosed from its own log."
description: "The job that keeps the knowledge graph current now states its own configuration before it tries to use it. It prints the database name it resolved and where that name comes from, the host and scheme taken from the connection address, the repository identity and the exact source revision, and for each required secret whether it is present, absent, or set to an empty value that counts as absent. Secret values are never printed; only their presence and length. When the database name is not the leading part of the host, the job says so and names that mismatch as the usual cause of a database-not-found error, because the hosted service names a database after its instance and the two normally match. This report runs before the configuration is validated, so it appears even on runs that then fail. It exists because sixty-one consecutive failures of this job reported nothing beyond the words \"backend unavailable\", and the two separate causes behind them — a database name left pointing at a replaced instance, and a store that had been switched to read-only — were indistinguishable from each other and from a wrong password."
---

## Entry
