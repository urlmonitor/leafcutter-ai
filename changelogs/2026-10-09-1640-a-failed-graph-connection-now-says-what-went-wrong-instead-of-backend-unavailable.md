---
title: "A failed graph connection now says what went wrong instead of \"backend unavailable\""
date: "2026-10-09"
time: "16:40"
type: manual
components: 
  - knowledge_management
summary: "Every knowledge-graph connection failure used to report the same six words. It now names the error class, the database's own error code, and the server's explanation."
description: "When the knowledge graph could not be reached, every possible cause reported the identical message, \"backend unavailable\". A missing database, a store that had been switched to read-only, a refused login, a connection that timed out and a transaction that ran too long were indistinguishable from one another, and the real explanation the database had already supplied was discarded before anyone could read it. The scheduled job that keeps the graph current failed sixty times in a row emitting that one message, and two entirely different causes sat behind it the whole time: the job was addressing a database name that did not exist, and the store itself had been switched to read-only after filling up. Neither was visible without instrumenting the code by hand. The message now names the kind of failure, the database's own error code where it supplies one, and the explanation the server gave, shortened to one line and capped in length. Failures that carry no error code, such as an unreachable host, are reported without inventing one. The connection address and password are never included. Everything that reads these failures programmatically is unaffected: the reported category is still \"unavailable\", the failure is still marked as worth retrying, and the original error is still chained underneath for anyone reading a stack trace."
---

## Entry
