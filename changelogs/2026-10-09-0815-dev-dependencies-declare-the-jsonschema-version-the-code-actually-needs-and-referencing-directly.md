---
title: "Dev dependencies declare the jsonschema version the code actually needs, and referencing directly"
date: "2026-10-09"
time: "08:15"
type: manual
components: 
  - infrastructure
summary: "requirements-dev.txt raises the jsonschema floor from 4.0 to 4.18 and declares referencing directly, so an environment can no longer install cleanly and still fail at runtime."
description: "product_truth_contracts.py imports referencing.exceptions.Unresolvable directly, and referencing is only a jsonschema dependency from 4.18 onward. The declared floor of jsonschema 4.0 therefore permitted an environment that installs without error and then fails when the product-truth validator runs, which is what happened on a host carrying Debian jsonschema 4.10.3. The floor is now 4.18, and referencing is declared as a direct dependency at jsonschema own floor of 0.28.4 rather than relied on as a transitive. The file header, which listed only pyyaml and jsonschema as runtime imports, now names referencing too. No code changed; this corrects the dependency declaration behind UXP-300-4."
---

## Entry
