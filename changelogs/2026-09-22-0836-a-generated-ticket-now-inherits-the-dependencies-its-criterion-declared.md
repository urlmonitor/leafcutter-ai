---
title: "A generated ticket now inherits the dependencies its criterion declared, and stops listing files its criterion forbids touching"
date: "2026-09-22"
time: "08:36"
type: manual
components: 
  - ac_driven_dev
summary: "A ticket generated from an acceptance criterion now carries the dependencies that criterion declared through its contract, instead of only the ones someone had also written out by hand. It also stops naming files the criterion explicitly says must not be edited."
description: "Two defects, both found by generating four real tickets and comparing them against the criteria they came from. The first: a criterion can declare what it needs from another criterion, and that declaration was never read when working out what the resulting ticket depends on. Only a second, hand-written list was read. So a dependency reached the ticket only when someone had recorded the same fact twice, in two different places, in two different vocabularies -- and where they had not, a build could start the consumer before the thing it consumes exists. Of four tickets generated in one pass, two lost their dependency this way. The second: the file list on a generated ticket is partly harvested from the criterion's own prose, and that harvesting did not read the sense of the sentence, so a line saying a file must NOT be touched put that file on the list of files to edit. Confirmed on a real record that names two such files, one of which is the very file that record exists to protect. Harvesting from prose is kept rather than removed: measured across every record in the store, deriving the file list from structured links alone would change 544 and empty 407, which is a migration rather than a fix. Instead a narrow rule now skips a harvested path when the sentence negates it just before. Across the whole store that removed 24 wrong entries and added none. Two gaps are left named rather than silently accepted: negation phrased after the path is still missed, and an instruction to run a script is still read as an instruction to edit it."
commits: 
breaking: false
---

## Entry
