/**
 * commit.js — Claude Code Workflow script (depth 0)
 *
 * The /commit surface. Dispatches the commit agent and, when it returns a
 * `status: "handoff"` for a refusal whose remedy is `engage-specialist`, engages
 * the declared specialist and then re-offers the very same commit (BO-3800a-2).
 *
 * WHY A SCRIPT: the commit agent runs at depth 1, where an Agent call is silently
 * dropped (ADR-019). It cannot bring the specialist in itself; it returns the handoff
 * payload that remedy_handoff.py built, and this depth-0 script consumes it. The
 * hold is simply that nothing here touches the working tree or the index: no reset,
 * stash, checkout or restore runs, and the re-offered commit runs the same hook chain.
 *
 * Bound: the specialist is engaged at most once per run. A refusal that stands after
 * that is reported as-is and the commit is not forced.
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 */

export const meta = {
  name: 'commit',
  description: 'Confirmation-gated commit; a complexity refusal brings in the restructuring specialist, then re-offers the commit',
  phases: [
    { title: 'Commit', detail: 'commit agent attempts the commit; a handoff names the specialist' },
    { title: 'Specialist', detail: 'declared specialist puts the file right; the change is untouched' },
    { title: 'Re-offer', detail: 'the same commit is attempted again against the same hooks' },
  ],
}

const MAX_SPECIALIST_ENGAGEMENTS = 1

const COMMIT_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string' },
    message: { type: 'string' },
    handoff_target: { type: 'string' },
    remedy: { type: 'object' },
  },
  required: ['status'],
}

const SPECIALIST_SCHEMA = {
  type: 'object',
  properties: { status: { type: 'string' }, message: { type: 'string' } },
  required: ['status'],
}

function stop(message, extra = {}) {
  return { status: 'blocked', message, ...extra }
}

function usableDemand(remedy) {
  return Boolean(remedy) && Array.isArray(remedy.demand) && remedy.demand.length > 0
}

function commitPrompt(userArgs, reoffer) {
  const note = reoffer
    ? 'The restructuring specialist has since run. Attempt the SAME commit again with the same message and files; run every hook, skip none, and change nothing in the working tree or index first.'
    : 'Show the planned commit message and file list, then commit.'
  return `${note} On a pre-commit refusal whose hook declares engage-specialist, do NOT dispatch anyone: run remedy_handoff.py with the hook output on stdin and return its JSON unchanged (status "handoff"). Arguments: ${userArgs}`
}

function specialistPrompt(payload) {
  const remedy = payload.remedy
  const skills = Array.isArray(remedy.skills) ? remedy.skills : []
  return `Hook '${remedy.hook_id}' refused a commit. Put the file(s) right so the demand is met. Apply the skill(s): ${skills.join(', ') || '(none declared)'}. Demand (reproduced as given): ${JSON.stringify(remedy.demand)}. Do not reset, stash, checkout or restore anything, do not raise any limit, and do not commit; the commit is re-offered afterwards.`
}

const userArgs = (typeof args !== 'undefined' && args && typeof args.arguments === 'string') ? args.arguments : ''

let attempt = await agent(commitPrompt(userArgs, false), { agentType: 'commit', label: 'commit', schema: COMMIT_SCHEMA, phase: 'Commit' })
let engagements = 0

while (attempt && attempt.status === 'handoff') {
  const target = typeof attempt.handoff_target === 'string' ? attempt.handoff_target.trim() : ''
  if (target === '' || !usableDemand(attempt.remedy) || attempt.remedy.disposition !== 'engage-specialist') {
    return stop(`The commit agent handed off but the payload named no usable party or demand (target ${JSON.stringify(attempt.handoff_target)}). Nobody was engaged and the commit was not re-attempted.`, { handoff: attempt })
  }
  if (engagements >= MAX_SPECIALIST_ENGAGEMENTS) {
    return stop(`The refusal by '${attempt.remedy.hook_id}' stands after '${target}' was engaged ${engagements} time(s). Whatever it changed remains in place; the commit was not forced and no standard was relaxed.`, { handoff: attempt, specialist_engagements: engagements })
  }
  engagements += 1
  const done = await agent(specialistPrompt(attempt), { agentType: target, label: target, schema: SPECIALIST_SCHEMA, phase: 'Specialist' })
  if (!done || done.status !== 'ok') {
    return stop(`'${target}' could not be engaged to a result (status ${JSON.stringify(done && done.status)}). The commit was not re-attempted and nothing was forced.`, { specialist_engagements: engagements })
  }
  attempt = await agent(commitPrompt(userArgs, true), { agentType: 'commit', label: 'commit', schema: COMMIT_SCHEMA, phase: 'Re-offer' })
}

return attempt || stop('The commit agent returned no result.')
