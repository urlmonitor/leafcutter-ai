---
title: Three slow test files stop rebuilding the package once per test
date: "2026-10-07"
time: "17:30"
type: manual
components: 
  - testing_quality
summary: "Several tests used to each rebuild the whole package from scratch and then check a different thing about the identical result. They now build it once per group and share the result, while still proving exactly what they proved before."
description: "Implements TQ-600a-9, TQ-600a-9-i and TQ-600a-9-ii. One test file drops from ten real package builds to one, another from sixteen to ten, and a third from three to two, measured by a real counter rather than by mocking: the shared harness now emits a deploy signal after every genuine build subprocess, and every assertion reads that signal, because a mocked build is not a build. Measured in one sitting against a checkout of the merge-base, the three files take roughly twelve, a hundred and eight, and seventy-three seconds against baselines of a hundred and three, a hundred and seventy, and a hundred and ten. Each ratio is expressed against a baseline measured alongside it, never against a number written down earlier, because this machine varies by ten to twenty per cent between runs of identical code. No assertion was weakened, skipped or deleted. A test that writes to its shared preparation still receives its own private copy, and breaking any one member's subject still reddens exactly that member and no other, which is what stops four assertions about one build decaying into one assertion and three restatements. The build guard that exists to prove the self-targeting bootstrap path keeps building the expensive way, because testing that path is its entire purpose. Two pre-existing bugs were fixed because the new tests could not otherwise run: a generated plugin imported a module before its directory was on the import path, and a helper called a patchable public function internally so that patching it reddened two tests where one was required. TQ-600a-9-iii is deliberately not included; it would revise a decision another author recorded and needs their agreement first."
---

## Entry
