---
title: "Product-truth validator names the module that failed to import instead of blaming jsonschema"
date: "2026-10-08"
time: "17:30"
type: manual
components: 
  - ux_prototyping
summary: "When a dependency such as referencing cannot be imported, the product-truth validator now says which module failed and, for referencing, that the installed jsonschema is too old, instead of claiming jsonschema is not installed."
description: "The validator wrapped import jsonschema and the product_truth_contracts import in one try/except, so a missing referencing module (which jsonschema older than 4.18 does not ship, for example Debian 4.10.3) was reported as jsonschema not installed. The refusal now names the module that actually failed, states the installed jsonschema version, and explains the version problem when referencing is the cause. A genuinely missing jsonschema keeps its original message. Every case still refuses and exits 2 before any store I/O. The dependency handling moved to a new sibling module, product_truth_dependencies.py, to keep validate_product_truth.py under its size limit, and the build smoke phase now re-imports it fresh. Covered by the new acceptance criterion UXP-300-4."
---

## Entry
