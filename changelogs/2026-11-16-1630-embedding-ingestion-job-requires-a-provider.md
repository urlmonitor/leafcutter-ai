---
title: "The embedding ingestion job requires a provider, and says so in its signature"
date: "2026-11-16"
time: "16:30"
type: manual
components: 
  - knowledge_management
summary: "knowledge.embedding_jobs.embed_snapshot declared its provider as EmbeddingProvider | None but read provider.model, provider.dimensions and provider.embed unconditionally, so a None provider always raised AttributeError. The provider is now declared as a required EmbeddingProvider. No caller passed None, so no call site changes. The 9 mypy union-attr errors in the file are gone, with no type-ignore, cast or Any."
description: "fix(knowledge), KM-400c-4-i. The provider parameter of embed_snapshot is now EmbeddingProvider, without '| None'. It never had a default. Its docstring now says it is required. Why required rather than giving None a defined result: the only callers, knowledge/examples/synthetic_demo.py and tests/knowledge/test_embedding_jobs.py, always pass a constructed provider; docs/how-to/run-knowledge-retrieval.md names the API embed_snapshot(writer,snapshot,provider,cache={}) and says no provider calls run unless embeddings are enabled, so a caller with embeddings disabled does not call the job; no AC, ticket or document defines a result for ingestion without a provider. The query side keeps accepting None: QueryEmbeddings and KnowledgeService report a missing provider as not ready, unchanged. New L3 AC KM-400c-4-i under KM-400c-4, which lists it in covered_by and records the amendment. New tests/knowledge/test_km_400c_4_i.py: one test reads the declared types with typing.get_type_hints and the signature with inspect, and fails before the fix because the provider type admitted None; the other runs synthetic_demo.run_demo with only the Neo4j backend replaced by a recording writer and asserts the real embed_snapshot received the demonstration's FixtureEmbeddings, embedded 3 records with model synthetic-fixture-v1 and 2 dimensions, and wrote them. mypy --ignore-missing-imports --explicit-package-bases on knowledge/embedding_jobs.py: 9 errors before, 0 after."
adrs: []
commits: []
breaking: false
---

## Entry
