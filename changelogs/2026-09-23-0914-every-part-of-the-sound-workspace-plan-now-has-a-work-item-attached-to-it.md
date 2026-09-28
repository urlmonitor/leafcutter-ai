---
title: "Every part of the sound-workspace plan now has a work item attached to it"
date: "2026-09-23"
time: "09:14"
type: manual
components: 
  - ac_driven_dev
summary: "The plan for making new workspaces sound by construction is now fully broken down into work items — 23 more were written from the approved criteria, completing a set that previously covered only one of its five parts."
description: "The sound-workspace plan has five parts: work always starts from the current shared line rather than an older copy of it; a workspace is judged on what you changed rather than what it borrowed; you can tell which workspaces are finished with and which still hold something; the workspace you are told you got is the one you actually got; and a workspace the list cannot see is still accounted for and still removable. Only the fourth part had work items. The remaining 23 were written from the already-approved criteria in one pass, so all five parts are now actionable. They were deliberately held until an earlier fix landed: until then, a work item did not inherit the dependencies its criterion declared through its contract, and generating these earlier would have reproduced the same missing links that the fourth part's items had to have repaired by hand. That fix is confirmed working here on real records rather than test fixtures. Before anything was written, all 23 were checked and reported ready, each naming at least one file to change and drawing that list from the criterion's structured links rather than from its prose — which means a known weakness in reading file names out of prose cannot affect this set. Nothing is being built by this change; every item is unstarted."
commits: 
  - 6f1257a2
breaking: false
---

## Entry
