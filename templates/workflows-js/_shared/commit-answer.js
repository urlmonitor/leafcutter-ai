// COMMIT-ANSWER block (BO-4500b-3). Single source; the build copies it between the
// COMMIT-ANSWER marker pair of every consuming route. Edit here, never in a route.
//
// PROVENANCE (BO-4500 standing rule: start from the hardened copy, move its KI regressions here)
//   - Engage-then-re-offer loop: taken from templates/workflows-js/commit.js (the /commit route),
//     BO-3800a-2: a specialist is engaged at most once, a standing refusal is reported and never
//     forced, the re-offer is the same commit, and a handoff is engaged only when its remedy
//     disposition is engage-specialist with a usable demand (commit.js:77). The engage happens in
//     a depth-0 script because the commit agent's own Agent call is dropped (ADR-019;
//     KI-BO-20260914-autofix-re-dispatch-is-specified-at-a-depth-that-cannot-execute). No known
//     issue was filed for the engage-once bound itself; it comes from the BO-3800a-2 spec.
//   - Reply reading: modelled on the commit-reply reading in templates/workflows-js/fast-lane-ship.js
//     (commitOk: any status other than ok is not success; nothing is inferred from prose), against
//     KI-BO-007 (a phase counted completed when the agent did not do it, yielding status ok).
//     Not taken from copies that fall back to ok on an unreadable reply (analysis C2, 2026-09-25).
//
// The DECISION is a pure function of (reply, attempt history, installed values). It calls no
// engine primitive and reads no file; the route-side dispatch around it is the route's job.
// Installed values come from config/commit_step.json at build time; none is typed here.
const COMMIT_ANSWER_VERSION = {{config.commit_step_answer_version}}
const COMMIT_ANSWER_MAX_TRANSIENT_RETRIES = {{config.commit_step_max_transient_retries}}
const COMMIT_ANSWER_REASON_CODES = {
  policy: {{config.commit_step_reason_codes_policy}},
  step: {{config.commit_step_reason_codes_step}},
  check: {{config.commit_step_reason_codes_check}},
  nothing: {{config.commit_step_reason_codes_nothing}},
}
const COMMIT_ANSWER_QUOTE_BYTES = 2048
const COMMIT_ANSWER_TRUNCATION_MARK = '...[truncated]'

function commitAnswerByteLength(s) {
  let n = 0
  for (const ch of s) {
    const c = ch.codePointAt(0)
    n += c < 0x80 ? 1 : c < 0x800 ? 2 : c < 0x10000 ? 3 : 4
  }
  return n
}

// Quote what was received, at most 2 KB (2048 bytes), the truncation marked.
function commitAnswerQuote(value) {
  let text = ''
  if (typeof value === 'string') {
    text = value
  } else if (value !== undefined && value !== null) {
    try { text = JSON.stringify(value) } catch (e) { text = String(value) }
    if (typeof text !== 'string') text = String(value)
  }
  if (commitAnswerByteLength(text) <= COMMIT_ANSWER_QUOTE_BYTES) return { received: text, truncated: false }
  let budget = COMMIT_ANSWER_QUOTE_BYTES - commitAnswerByteLength(COMMIT_ANSWER_TRUNCATION_MARK)
  let out = ''
  for (const ch of text) {
    const w = commitAnswerByteLength(ch)
    if (w > budget) break
    out += ch
    budget -= w
  }
  return { received: out + COMMIT_ANSWER_TRUNCATION_MARK, truncated: true }
}

function commitAnswerIsObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v)
}

function commitAnswerHistory(history) {
  const h = commitAnswerIsObject(history) ? history : {}
  return {
    first_paths: Array.isArray(h.first_paths) ? h.first_paths.slice() : [],
    first_message_file: typeof h.first_message_file === 'string' ? h.first_message_file : null,
    answers: Array.isArray(h.answers) ? h.answers.slice() : [],
    transient_retries_used: Number.isInteger(h.transient_retries_used) ? h.transient_retries_used : 0,
    specialist_engaged: h.specialist_engaged === true,
    specialist: typeof h.specialist === 'string' ? h.specialist : null,
    specialist_reply: h.specialist_reply === undefined ? null : h.specialist_reply,
  }
}

function commitAnswerFamily(code) {
  for (const family of Object.keys(COMMIT_ANSWER_REASON_CODES)) {
    if (COMMIT_ANSWER_REASON_CODES[family].indexOf(code) !== -1) return family
  }
  return null
}

function commitAnswerDecision(decision, h, extra) {
  return Object.assign({
    decision: decision, specialist: null, paths: null, message_file: null,
    status: null, reason_code: null, reason: null, hook_name: null, failing_files: [],
    answers: null, received: null, truncated: false, envelope_status: null, answer_status: null,
    contract_violation: false, offending_field: null, offending_value: null, message: '',
    history: h,
  }, extra)
}

// Fields of the reply's commit_answer, copied unchanged.
function commitAnswerFields(ca) {
  return {
    status: ca.status === undefined ? null : ca.status,
    reason_code: ca.reason_code === undefined ? null : ca.reason_code,
    reason: ca.reason === undefined ? null : ca.reason,
    hook_name: ca.hook_name === undefined ? null : ca.hook_name,
    failing_files: Array.isArray(ca.failing_files) ? ca.failing_files : [],
  }
}

function commitAnswerReport(h, ca, message, extra) {
  return commitAnswerDecision('report', h, Object.assign(commitAnswerFields(ca), { answers: h.answers.slice(), message: message }, extra))
}

function commitAnswerContractBreak(h, ca, field, value) {
  return commitAnswerReport(h, ca, 'The reply breaks the commit answer contract: ' + field + ' ' + JSON.stringify(value) + ' is not allowed here. Nothing was retried.',
    { contract_violation: true, offending_field: field, offending_value: value === undefined ? null : value })
}

function commitAnswerExpectedEnvelope(ca) {
  if (ca.status === 'committed') return 'ok'
  if (ca.status === 'hook_failed' && commitAnswerIsObject(ca.handoff)) return 'handoff'
  return 'blocker'
}

// Decision after the engaged specialist's report: re-offer the identical commit, or report.
function commitAnswerAfterSpecialist(h) {
  const reply = h.specialist_reply
  const next = Object.assign({}, h, { specialist_reply: null })
  if (commitAnswerIsObject(reply) && reply.status === 'ok') {
    return commitAnswerDecision('retry', next, {
      specialist: h.specialist, paths: h.first_paths.slice(), message_file: h.first_message_file,
      answers: h.answers.slice(), message: 'The specialist reported ok; re-offering the identical commit.',
    })
  }
  const q = commitAnswerQuote(reply)
  return commitAnswerDecision('report', next, {
    specialist: h.specialist, answers: h.answers.slice(), received: q.received, truncated: q.truncated,
    message: "The specialist '" + h.specialist + "' did not return an ok result; the commit was not re-attempted and nothing was forced.",
  })
}

function commitAnswerForRefused(h, ca) {
  const family = commitAnswerFamily(ca.reason_code)
  if (family === 'policy') {
    return commitAnswerDecision('stop', h, Object.assign(commitAnswerFields(ca), {
      message: 'The commit step refused by policy; this cannot succeed on another attempt.' }))
  }
  if (family !== 'step') return commitAnswerContractBreak(h, ca, 'reason_code', ca.reason_code)
  if (h.transient_retries_used >= COMMIT_ANSWER_MAX_TRANSIENT_RETRIES) {
    return commitAnswerReport(h, ca, 'The transient failure persisted after ' + h.transient_retries_used + ' retries.')
  }
  const next = Object.assign({}, h, { transient_retries_used: h.transient_retries_used + 1 })
  return commitAnswerDecision('retry', next, Object.assign(commitAnswerFields(ca), {
    paths: h.first_paths.slice(), message_file: h.first_message_file, answers: h.answers.slice(),
    message: 'Transient step failure; re-offering the identical commit.' }))
}

function commitAnswerForHookFailed(h, ca) {
  if (commitAnswerFamily(ca.reason_code) !== 'check') return commitAnswerContractBreak(h, ca, 'reason_code', ca.reason_code)
  const target = commitAnswerIsObject(ca.handoff) && typeof ca.handoff.handoff_target === 'string' ? ca.handoff.handoff_target : ''
  const remedy = commitAnswerIsObject(ca.handoff) ? ca.handoff.remedy : null
  const engageable = commitAnswerIsObject(remedy) && remedy.disposition === 'engage-specialist' &&
    Array.isArray(remedy.demand) && remedy.demand.length > 0
  if (target === '' || !engageable) return commitAnswerReport(h, ca, 'A pre-commit check failed and the reply named no usable specialist or demand; nobody was engaged.')
  if (h.specialist_engaged) {
    return commitAnswerReport(h, ca, "The refusal stands after '" + h.specialist + "' was engaged; a specialist is engaged at most once per commit.", { specialist: h.specialist })
  }
  const next = Object.assign({}, h, { specialist_engaged: true, specialist: target })
  return commitAnswerDecision('engage', next, Object.assign(commitAnswerFields(ca), {
    specialist: target, paths: h.first_paths.slice(), message_file: h.first_message_file, answers: h.answers.slice(),
    message: "Engage '" + target + "', then re-offer the identical commit." }))
}

function commitAnswerForAnswer(h, ca) {
  if (ca.answer_version !== COMMIT_ANSWER_VERSION) return commitAnswerContractBreak(h, ca, 'answer_version', ca.answer_version)
  if (ca.status === 'committed') {
    return commitAnswerDecision('continue', h, Object.assign(commitAnswerFields(ca), { answers: h.answers.slice(), message: 'Committed.' }))
  }
  if (ca.status === 'refused') return commitAnswerForRefused(h, ca)
  if (ca.status === 'hook_failed') return commitAnswerForHookFailed(h, ca)
  if (ca.status === 'nothing_to_commit') {
    if (commitAnswerFamily(ca.reason_code) !== 'nothing') return commitAnswerContractBreak(h, ca, 'reason_code', ca.reason_code)
    return commitAnswerReport(h, ca, 'There was nothing to commit.')
  }
  return commitAnswerContractBreak(h, ca, 'status', ca.status)
}

function decideCommitAnswer(reply, history) {
  const h = commitAnswerHistory(history)
  // No reply after an engage is the specialist's missing report; it is reported by name.
  if ((reply === null || reply === undefined) && (h.specialist_reply !== null || h.specialist_engaged)) return commitAnswerAfterSpecialist(h)
  const ca = commitAnswerIsObject(reply) ? reply.commit_answer : undefined
  if (!commitAnswerIsObject(ca)) {
    const q = commitAnswerQuote(reply)
    return commitAnswerDecision('report', h, { answers: h.answers.slice(), received: q.received, truncated: q.truncated,
      message: 'The commit agent reply is not one structured envelope with a commit_answer object; nothing is inferred from prose.' })
  }
  const withAnswer = Object.assign({}, h, { answers: h.answers.concat([ca]) })
  const envelopeStatus = reply.status === undefined ? null : reply.status
  if (envelopeStatus !== commitAnswerExpectedEnvelope(ca)) {
    const q = commitAnswerQuote(reply)
    return commitAnswerReport(withAnswer, ca, "The envelope status '" + envelopeStatus + "' disagrees with the commit_answer status '" + ca.status + "'.",
      { received: q.received, truncated: q.truncated, envelope_status: envelopeStatus, answer_status: ca.status === undefined ? null : ca.status })
  }
  return commitAnswerForAnswer(withAnswer, ca)
}
