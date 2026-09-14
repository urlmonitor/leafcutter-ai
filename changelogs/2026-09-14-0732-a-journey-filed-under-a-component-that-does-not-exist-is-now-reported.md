---
title: "A journey filed under a component that doesn't exist is now reported"
date: "2026-09-14"
time: "07:32"
type: manual
components: 
  - ux_prototyping
summary: "The product-truth checker now checks each journey's component label against the project's registered components and its tags against a declared shape, pointing out the intended label when one is only mistyped."
description: "A journey's component and tags are how it is found, and both were free text, so a typo filed a journey under a component that doesn't exist and nothing said so. The checker now resolves each journey's component label against the components registered in docs/acceptance-criteria/index.yaml and checks each tag is lowercase words joined by hyphens (UXP-700e-3). A label that differs from a registered one only by case or spacing -- 'UX Prototyping' -- is reported as 'ux-prototyping' having been meant, rather than as a new component. The run states resolved_labels on its result line, so a record with no labels is distinguishable from one whose labels all resolved. Findings are warnings rather than commit blocks, since labels were free text until now. The AC left open which of the project's two component registries labels resolve against; they resolve against index.yaml, the registry every existing journey already uses -- all 14 journeys' components resolve there and none would against docs/components.json, and on this repository all 69 labels now resolve with no findings. The checker's main file also comes back under its size limit (371 lines) as its logging helpers move beside the outcome rules they report."
commits: 
breaking: false
---

## Entry
