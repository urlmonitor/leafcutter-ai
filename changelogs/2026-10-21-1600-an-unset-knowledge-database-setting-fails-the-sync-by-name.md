---
title: "An unset knowledge database setting fails the sync by name"
date: "2026-10-21"
time: "16:00"
type: manual
components: 
  - knowledge_management
summary: "The knowledge sync job no longer guesses the database name: an unset database name or writer username fails the job before any connection, naming each missing setting, and a rejected database name is reported with where it was read from."
description: "On a hosted Aura instance the database is named after the instance, so the old fallback to the literal name neo4j made a missing setting look like a backend failure. The sync job now refuses to start when LEAFCUTTER_NEO4J_DATABASE or the writer username is unset, naming each unset setting and substituting nothing. When the backend rejects the connection, the error states the database name that was requested and the configuration source it came from, without printing any credential. The GitHub sync workflow drops its 'neo4j' fallback for the database variable and checks it alongside the other required settings, and the operational how-to states that the database name and username are instance-specific and must be declared."
---

## Entry
