---
title: "The decision kernel detects bundled requests and proposes a split (off by default)"
date: "2026-10-10"
time: "16:00"
type: manual
components:
  - decision_kernel
summary: "A request that bundles several separate questions can now be detected at routing and offered as a split: the host proposes two to five parts, each quoting your words, and the run waits at a split gate for a person. The feature ships switched off (split.enabled false) until DK-400 E3."
description: "DK-400 E1, detection and proposal (ADR-067). At routing, the kernel checks whether the subject bundles several separate questions, under three triggers: no capability matched it, routing could not choose one, or routing would accept it as one decision. A single question, one listing alternatives or constraints, or a caller-supplied decision request is never split. A bundled subject gets a split record, and the host operation host.decompose_goal proposes parts that each quote the subject. Deterministic code checks every part: a part whose quote is not in the subject is set aside with its reason, a proposal with circular or unknown dependencies is refused and repaired by the host, at most five parts are offered with the rest listed as not covered, and fewer than two parts means the request goes ahead as one question. The run then waits at the split gate, with no part run until a person answers. Approving, rejecting and running the parts arrive in E2 and E3. The epic also adds the c3-023 component diagram and the reference page docs/reference/decision-kernel-splits.md, and publishes two decisions: dec-59d0ba46c140cf0c moves DK-400a-1-ii to E2, and dec-b10271ebb40b9eaa authorises a recorded scaffold-free pass for diagrams until the INF-1300 scaffold exists."
commits: [14c8d225b, daafc8b67, 43871df9f, 687c42dab, fd2b7974b, 26b6a401b, 65c9987b0, 6f42b28bc, c0c1f830e, 40d1775c8, b7be15b43, 85ebfc608]
breaking: false
---

## Entry
