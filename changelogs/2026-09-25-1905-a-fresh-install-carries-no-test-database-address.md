---
title: "A fresh install carries no test database address"
date: "2026-09-25"
time: "19:05"
type: manual
components:
  - infrastructure
  - testing_quality
summary: "config/skills_config.default.json no longer ships a default for testing_context.db_connection_test, and the schema no longer declares one. A project that never set it resolves no address and gets a not-configured report; a project's own setting is left byte-identical on upgrade."
description: "INF-1100d-1 and INF-1100d-1-i (fast lane, manually orchestrated). The adopter address that shipped as the default is removed from the defaults file and the schema; the schema description now shows a placeholder form. The upgrade migration never merges package defaults into a project's settings, so no code change was needed there; tests pin that behaviour. The address still appears as an example in some agent templates and docs, which INF-1100d-2 and INF-1100d-5 cover."
commits:
breaking: false
---

## Entry

Leafcutter no longer installs a ready-made test database address. A project that wants
database tests sets its own address; one that has not is told the setting is missing
instead of connecting to an address that belonged to another project.
