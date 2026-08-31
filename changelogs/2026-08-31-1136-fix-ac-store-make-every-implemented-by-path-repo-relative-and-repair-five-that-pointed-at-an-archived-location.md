---
title: "fix(ac-store): make every implemented_by path repo-relative, and repair five that pointed at an archived location"
date: "2026-08-31"
time: 1136
type: manual
components: 
  - ac_store
  - ac_driven_dev
summary: "Forty links from requirements to the tickets that implemented them were written as paths on one particular machine. They now work everywhere, and five that had quietly gone stale were repointed."
description: "The epic generator stamps each requirement with a link back to the ticket that implements it, and it writes that link as a full filesystem path beginning with the home directory of whoever generated it. Those links are committed and read by everyone, and they resolve on exactly one computer. Forty such links across thirty-six requirement records are now written relative to the repository, which is what every other path in the store already does. No requirement text, status, priority or any other field is touched; the change is confined to the link lines, and that was verified by reading the diff rather than trusting the edit. Checking that each rewritten link actually points at something turned up a second and separate problem the sweep would otherwise have hidden. Five records in one family named tickets under the inbox folder, which is where those tickets sat when the links were written; the tickets have since been archived and the inbox folder no longer exists at all. Simply removing the machine prefix would have produced five tidy-looking links that still pointed nowhere. Two of the five were part of this sweep and three were already relative and already broken before it, and all five are repointed at the archive, because leaving three knowingly broken beside two repaired ones would be worse than either. Six absolute paths remain in the store and are deliberately left alone: each sits inside requirement prose where the path is the subject of the sentence rather than a link — an example shell command, a description of a deleted working copy, a note about where a particular checkout lives. Rewriting those would alter requirement text to fix a link problem they do not have. The generator itself is unchanged and will keep producing these; that is recorded separately and is the reason this repair is expected to be needed again."
breaking: false
---

## Entry
