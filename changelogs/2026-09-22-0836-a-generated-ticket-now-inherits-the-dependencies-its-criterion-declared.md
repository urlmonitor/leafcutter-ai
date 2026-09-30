---
title: "A generated ticket now inherits the dependencies its criterion declared through its contract"
date: "2026-09-22"
time: "08:36"
type: manual
components: 
  - ac_driven_dev
summary: "A ticket generated from an acceptance criterion now carries the dependencies that criterion declared through its contract, instead of only the ones someone had also written out by hand."
description: "A criterion can declare what it needs from another criterion, and that declaration was never read when working out what the resulting ticket depends on. Only a second, hand-written list was read. So a dependency reached the ticket only when someone had recorded the same fact twice, in two different places, in two different vocabularies -- and where they had not, a build could start the consumer before the thing it consumes exists. Of four tickets generated in one pass, two lost their dependency this way. A second defect found alongside it -- the file list on a generated ticket harvests paths out of the criterion's prose without reading the sense of the sentence, so a line saying a file must NOT be touched puts that file on the list of files to edit -- was NOT fixed here. A fix was written and then withdrawn: measured against every record in the store, the rule it used removed 25 path entries, of which 5 were wrong, and left two records naming no file to edit at all. The criterion governing this area already ranks a wrongly-dropped file as the worse of the two errors, and a better mechanism for the same problem shipped earlier and is already in use. That defect stays recorded and open rather than half-fixed."
commits: 
breaking: false
---

## Entry
