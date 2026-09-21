---
title: "A commit-guardian hook that no registry invokes is now a test failure, not a discovery six review rounds later"
date: "2026-09-14"
time: "13:45"
type: manual
components: 
  - commit_guardian
  - testing_quality
summary: "KI-TQ-007 records six rounds of adversarial review that each verified a gate by importing it or running it directly, and none of which asked what registered it — the answer was nothing. Nothing in the suite could distinguish that gate from one never wired up, because nothing in it looked at a registry. An inventory test now asks disk -> manifest for every hook script, and it found 18 that no hooks_manifest entry invokes."
description: "Test-only change plus the known-issue entry it corrects; no production file is touched. Two corrections to the remedy as filed. First, KI-TQ-007 says to assert the hook id appears in the deployed .pre-commit-config.yaml — that file is gitignored build output emitted by build.py and absent in a fresh clone, so asserting against it verifies the generator's last local run rather than the committed registry; a first pass did exactly that and produced five phantom unregistered ids that were only local build staleness. The test reads hooks_manifest.hooks in commit_guardian.json instead. Second, a registration test per hook AC has to be remembered by the author of the next hook, and not remembering is the defect class, so this is one inventory over the whole guardian directory, scoped by the repo's own hook_parity.hook_script_patterns so it cannot drift from check_hook_parity.py. Measured on this base: 18 hook scripts no manifest entry invokes, nine of which carry a settings block in both config.py and commit_guardian.json while being run by nothing — KI-CG-021's shape, and the configuration reads to a reviewer as evidence of registration. They are held in a shrink-only ratchet baseline, so the test is green now and red on the nineteenth; triaging the 18 is not done and is recorded as the remaining work. Neither existing gate covered this: check_hook_trigger_reachability iterates the registry asking whether any tracked path can fire each gate, so a script absent from the registry is invisible to it, and check_hook_parity compares scripts across directories and ids across manifests without asking whether a script on disk is named by any entry. All three failure paths were mutation-tested rather than trusted green — a planted orphan goes red, a removed baseline script reports the baseline stale, a moved registered script reports an unresolvable entry — and each mutation was reverted."
commits: 
  - 8fad2dda5
breaking: false
---

## Entry
