const WV_RUNNER_SCHEMA = { type: "object", properties: { command: { type: "string" }, workspace: { type: "string" }, exit_status: { type: "integer" },
  stdout: { type: "string" }, stderr: { type: "string" }, declined: { type: "boolean" }, step: { type: "string" }, agent: { type: "string" }, reason: { type: "string" } } };
const wvRoot = () => String(resolvedTarget.worktree_path).replace(/\\/g, "/");
const wvPy = (script, args) => `python "${wvRoot()}"/{{config.output_root}}/scripts/build_orchestration/${script}.py ${args}`;
const wvBad = (...vals) => vals.flat().filter((s) => typeof s !== "string" || !/^[A-Za-z0-9._-]+$/.test(s)).concat(/["$`\n\r]/.test(wvRoot()) ? [wvRoot()] : []);
async function wvStep(label, command, workKey) {
  try {
    const reply = await agent(JSON.stringify({ step: label, command, target: { workspace: resolvedTarget.worktree_path, run_id: workKey } }),
      { agentType: "command-step-runner", schema: WV_RUNNER_SCHEMA, label, phase: "Wrong-Version Runs" });
    return parseStepJson(reply.stdout);
  } catch { return null; }
}
async function wvRecover(workKey) {
  const unsafe = wvBad(workKey);
  if (unsafe.length) return { step: "input-check", detail: unsafe, message: `Wrong-version inputs are not plain values, no command was run: ${JSON.stringify(unsafe)}` };
  const recovered = await wvStep(`${WV}-wv-recover`, wvPy("wrong_version_runner", "recover"), workKey);
  return !recovered || recovered.ok !== true ? { step: "recover", detail: recovered, message: `Wrong-version recover step did not pass: ${JSON.stringify(recovered)}` } : null;
}
async function wvRuns(workKey, ids) {
  const flags = `--ac-root "${wvRoot()}/${AC_STORE_REL_PATH}" --test-root "${wvRoot()}" --base-ref HEAD`, idArg = ids.length ? `--ac-ids "${ids.join(",")}" ` : "";
  const halt = (step, detail) => ({ halt: { step, detail, message: `Wrong-version ${step} step did not pass: ${JSON.stringify(detail)}` }, outcome: null });
  const unsafe = wvBad(workKey, ids);
  if (unsafe.length) return halt("input-check", unsafe);
  let reply = "";
  if (ids.length) {
    const listed = await wvStep(`${WV}-wv-list`, wvPy("wrong_version_writer", `list --work-key "${workKey}" ${idArg}${flags}`), workKey);
    if (!listed || !Array.isArray(listed.owed) || !Array.isArray(listed.to_prepare) || listed.error !== null) return halt("list", listed);
    if (listed.to_prepare.length) {
      try {
        const raw = await agent(`Prepare the owed wrong versions. Input: ${JSON.stringify({ work_key: workKey, repo_root: resolvedTarget.worktree_path, requirement_ids: ids, wrong_versions: listed.to_prepare })}`,
          { agentType: "test-breaker", label: `${WV}-wv-test-breaker`, phase: "Wrong-Version Runs" });
        reply = typeof raw === "string" ? raw : raw ? JSON.stringify(raw) : "";
      } catch { reply = ""; }
    }
  }
  let delim = "WV_REPLY_EOF";
  while (reply.includes(delim)) delim += "_X";
  const fin = await wvStep(`${WV}-wv-finish`, `${wvPy("wrong_version_gate", `finish --work-key "${workKey}" --reply - ${idArg}${flags}`)} <<'${delim}'\n${reply}${reply ? "\n" : ""}${delim}`, workKey);
  if (!fin || typeof fin.gate_passed !== "boolean" || !fin.gate_passed) return halt("finish", fin);
  const verdict = fin.verdict || {};
  return { halt: null, outcome: verdict.outcome === undefined ? null : verdict.outcome };
}
const wvStem = (p) => String(p).replace(/\\/g, "/").split("/").filter(Boolean).pop().replace(/\.md$/i, "");
const wvHaltFields = (h) => ({ gate: "wrong_version_gate", wrong_version_step: h.step, wrong_version_detail: h.detail });
