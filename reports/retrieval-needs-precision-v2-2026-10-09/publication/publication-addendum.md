# Closed stage1b publication

The [stage1b review](../stage1b/review.html) records 16 accepted interpretations
and 16 finite contract passes. This is an isolated interpretation result, not
live Aura retrieval proof. The saved cases, gold, responses, results, summary,
HTML, closure and execution fingerprint have not been rewritten.

[source-preservation.json](source-preservation.json) preserves the exact three
v2 helper modules and two then-uncommitted runtime modules. Resolve historical
source by both original path and the consuming record SHA256; a path alone must
never select an older version. The original bytes are under `recorded-source/`.

The maintained controller adds only an error log containing the exception class
before the existing failure receipt. It preserves one-attempt behavior, batch
continuation and final environment cleanup. [Independent review](evaluator-review.json)
confirmed AST equivalence after removing that import and logging call.
[Current helper hashes](maintained-helpers.json) are publication metadata; they
do not replace the stage1b or prepared Aura execution fingerprints.

[local-only-artifacts.json](local-only-artifacts.json) records 16 unchanged SQLite
replay databases by original path, size and hash. They remain local and are
excluded from publication. The exported receipts remain available for review;
a clone must not claim to have verified or resumed the absent databases.

[scanner-classification.json](scanner-classification.json) records the individual
verification of 70 immutable path/hash metadata lines. Only their exact entropy
rule/path/line combinations are permitted by the normal scanner policy. No
credential-pattern rule or general directory exemption was changed.

Narrow Git attributes preserve the actual recorded bytes. Standard source and
commit checks remain required. The separately prepared Aura run has zero public
attempts and remains a pending live gate; its original preparation is retained.
A later authorized live run must use its own explicitly versioned preparation
pinned to the committed runtime, without replacing earlier fingerprints.
