---
title: "A pull request that claims to fix main's red post-merge run now has to prove it on its own commit"
date: "2026-10-09"
time: "23:00"
type: manual
components: 
  - testing_quality
summary: "A new fix-proof workflow runs the red run's failing tests against a pull request that declares it fixes them, using main's test selection and judgement, in a job that holds no credentials. Only a pass lets the hold exempt the pull request."
description: "When main's post-merge suite is red, a pull request may say in its description that it fixes the open post-merge-red issue. A new workflow, Post-merge fix proof, then checks that claim: it runs exactly the tests that failed in the red run against the pull request's own commit, or the whole correctness lane when the red run did not finish, and passes only if every one of them passed. Which tests run and how the result is judged always come from main, so a pull request cannot make its own proof pass by editing the test harness, pytest.ini or its plugins. A whole-lane proof also fails if any test that main's lane contains is missing from the pull request. The job that runs the pull request's code holds no token and no secret, and the job that reads the red run holds read-only access and runs only main's code. A pull request without a declaration starts no proof. The proof stays advisory until a live run confirms that its job's token is refused a write."
---

## Entry
