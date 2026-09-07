---
title: "spec(ticket-creation): record the rejected approach on TKT-600a-1 so it is not rebuilt"
date: "2026-08-31"
time: 1408
type: manual
components: 
  - ticket_creation_pipeline
  - ac_store
summary: "An automated attempt at this requirement was rejected in review. Rather than let that reasoning sit in a workflow transcript, the evidence is written into the requirement itself so the next implementer does not rebuild the same thing."
description: "The requirement asks that a generated ticket name only real edit surfaces, never file paths that merely appear inside narrative prose. An automated build produced an implementation that kept harvesting paths out of prose and added a list of nine English phrases — do not edit, context only, illustrates, example path and similar — that would cause a whole sentence to be skipped. Its own review blocked it, and measuring the attempt against the real inputs showed the objection understated the problem twice over. First, it did not fix the failure that stopped the epic: the sentence that produced three bare directory names contains none of those phrases, being an ordinary instruction, so the filter never engaged and the output was unchanged. Second, it silently discarded genuine edit surfaces — one sentence mentioning a script for reference, another beginning with the word illustrates, both lost their real file. That is the same defect the requirement exists to remove, running in the opposite direction. Guessing an author intent from English phrasing is not a mechanism, and the requirement already named the alternative: take the surface from the structured fields that exist for the purpose. One rule is added that the original wording did not state, namely that a path with no file extension is not an edit surface, because the existing on-disk check waves directories through for the simple reason that directories exist. The note also records what a correct fix will not achieve, so it is not mistaken for a complete repair: for all ten records whose surface is currently wrong, the structured fields yield nothing at all, because those records never declared an edit surface in the first place. An honest empty answer is the right outcome there, and the missing declarations are being repaired separately; the note asks that the generator refuse to emit a ticket with no surface rather than quietly emitting one, so the gap appears when the ticket is created instead of when someone tries to build it."
breaking: false
---

## Entry
