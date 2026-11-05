---
title: A test-free record can carry a typed verification record
date: "2026-11-05"
time: "10:00"
type: manual
components: 
  - build_orchestration
  - ac_store
summary: "New validator scripts/ac_store/_verification_record.py decides whether a record's verified_by names a complete check or inspection, and the store schema now accepts the verified_by key. Nothing calls the validator yet; the done rule (BO-2500f-4) wires it in."
description: "BO-2500f-1 and BO-2500f-1-i, PR 1 of wave 2 (ADR-076). validate_verification_record(record) returns {valid, method, problems} and never raises; each problem names the record id and the part. Check form needs check and wired_as (pre-commit:<id> or build-phase:<name>); inspection form needs gate_run, statement and a non-empty inspected list of {path, 40-hex blob}; a part of the other method is refused; an inspection is allowed only for change_target docs, prompt or config, and a missing change_target fails closed. config/ac_store_schema.json declares verified_by permissively (validity is decided at mark time, so unfinished records stay editable). The module is in AC_STORE_DEPLOY_MAP. Switch-dependent specs move to the done-gate PR; BO-2500f-1-i's derived-kind clause waits for BO-3500c-2. Both records stay in progress."
breaking: false
---

## Entry

Wave 2 replaces the free-text test waiver with a typed verification record. This first PR adds
only the shared validator and lets the store accept the new `verified_by` key. No commit or mark
step reads it yet, so nothing that passes today is refused; BO-2500f-4's done rule will use it.
