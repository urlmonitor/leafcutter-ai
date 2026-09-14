---
title: The new whole-store check could not start, and now can
date: "2026-09-07"
time: "08:20"
type: manual
components: 
  - ac_store
  - build_pipeline
summary: "The check that inspects every requirement record shipped yesterday and failed on its very first run, before examining anything, because it needed an identity the automated environment does not provide. It now supplies one, refuses loudly rather than continuing if that ever fails again, and is covered by a test that reproduces the bare environment."
description: "The check that examines every requirement record whenever work lands was added yesterday. Its first real run failed immediately, before looking at a single record. To make the automated environment treat the whole store as newly arrived — the trick that lets the underlying checks see everything rather than nothing — it creates a throwaway marker, and creating one requires an author name and address. A developer's own machine always has those configured; a fresh automated environment has none, so the step that worked everywhere it was tried failed the first time it ran for real. Nothing could have caught this earlier, and that is worth stating rather than glossing: the check only runs when work lands on the main line, so no pre-merge review can ever execute it. It passed every local test and every pre-merge check because none of them were capable of running it. The gap was written down before the change was accepted, and this is that gap arriving rather than a surprise. Two details made it worse than a one-line fix deserves. The failure message pointed at the wrong thing — the missing identity produced an empty value, which was passed along to the next command, which then complained about the empty value rather than about the identity. And the surrounding step would have carried on regardless: had the marker been created but matched nothing, the checks would have examined zero records and reported success, which is precisely the false reassurance this whole piece of work exists to eliminate. Both are now closed. The step supplies the identity directly without altering any saved settings, and it stops with a stated reason if either the marker cannot be created or the set of records to examine comes out empty. Two tests cover it: one recreates a bare environment with every identity source removed and confirms both that the old form genuinely fails there and that the new form succeeds, since only the pair shows the fix is what makes the difference; the other confirms the running configuration actually uses the new form, because a remedy that is correct in a test and missing from the thing that runs is how this reached the main line in the first place."
breaking: false
---

## Entry
