---
title: "Set up the background AC worker in WSL"
description: "Install a dedicated Linux runtime and register the Windows worker launcher."
type: how-to
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - ac_driven_dev
related_code:
  - scripts/background_worker_cli.py
  - scripts/background_worker/wsl_runtime.py
related_docs:
  - docs/how-to/background-ac-worker.md
  - docs/reference/background-ac-worker.md
---

# Set up the background AC worker in WSL

Complete this runtime setup before [configuring and enabling the worker](background-ac-worker.md).

The dedicated runtime has passed real Codex filesystem-isolation probes and
sandboxed Git-hook tests, including the deployed guard bootstrap. The current
Linux worker regression passes with live inference disabled. These results prove
the tested setup and execution boundaries; complete live local-model delivery
acceptance remains in progress. They do not establish a completed GitHub draft
publication or a successful model run for a newly installed consumer repository.

## Use a dedicated WSL runtime from Windows

Install the dependencies once inside a dedicated Linux distro, outside consumer
repositories. The launcher expects `leafcutter-worker` and
`/opt/leafcutter-worker/venv/bin/python` by default; both are configurable.
The distro must have a configured non-root default user, Git, Codex, Ollama,
and the worker Python dependencies. Configure reviewer authentication inside
Linux. Windows credentials are not forwarded through `WSLENV`.

### Install the dedicated runtime

The following example uses Ubuntu 24.04 and x86-64 WSL2. Substitute a different
distribution name consistently if you already have a dedicated runtime. Do not
reuse Docker's internal distribution. Run in Windows PowerShell:

```powershell
wsl --list --online
wsl --install Ubuntu-24.04 --name leafcutter-worker --version 2 --no-launch
wsl --distribution leafcutter-worker --user root
```

The last command opens the Linux root shell. Provision the non-root worker user
and runtime tools there; skip `useradd` if first-launch setup already created it:

```bash
apt-get update
apt-get install -y git gh curl ca-certificates xz-utils zstd python3 python3-venv bubblewrap
useradd --create-home --shell /bin/bash leafcutter
mkdir -p /opt/leafcutter-worker
python3 -m venv /opt/leafcutter-worker/venv
chown -R leafcutter:leafcutter /opt/leafcutter-worker
curl -fL https://nodejs.org/dist/v24.21.0/node-v24.21.0-linux-x64.tar.xz -o /tmp/leafcutter-node.tar.xz
curl -fL https://nodejs.org/dist/v24.21.0/SHASUMS256.txt -o /tmp/leafcutter-node-SHASUMS256.txt
python3 -c 'import hashlib,pathlib; expected=next(line.split()[0] for line in pathlib.Path("/tmp/leafcutter-node-SHASUMS256.txt").read_text().splitlines() if line.endswith("node-v24.21.0-linux-x64.tar.xz")); assert hashlib.sha256(pathlib.Path("/tmp/leafcutter-node.tar.xz").read_bytes()).hexdigest()==expected, "Node checksum mismatch"'
tar -xJf /tmp/leafcutter-node.tar.xz --strip-components=1 -C /usr/local
npm install --global @openai/codex@0.156.1
curl -fL https://ollama.com/download/ollama-linux-amd64.tar.zst -o /tmp/leafcutter-ollama.tar.zst
tar --zstd -xf /tmp/leafcutter-ollama.tar.zst -C /usr
exit
```

Node 24.21.0, Codex 0.156.1 and Ollama 0.34.4 were the runtime versions inspected
for this setup. The Ollama download above follows its current Linux release;
record `ollama --version` when validating an installation. Use the upstream
[Node downloads](https://nodejs.org/en/download) and
[Ollama Linux instructions](https://docs.ollama.com/linux) for other architectures.
No Leafcutter job is enabled by these commands. The verified WSL environment
needed no AppArmor, sysctl or global WSL security changes; `bubblewrap` plus the
existing unprivileged namespace support was sufficient.

Back in PowerShell, set the non-root default and enter that runtime:

```powershell
wsl --manage leafcutter-worker --set-default-user leafcutter
wsl --distribution leafcutter-worker
```

Current WSL supports named distributions and default-user management; consult
`wsl --help` and the [WSL command reference](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)
if your installed version differs. The worker must run as the non-root user.

Install Leafcutter into a checkout that Linux Git can use. A full clone under a
Windows-mounted path such as `/mnt/c/projects/worker-project` supports the
Windows launcher below; create and initialize its Git metadata from Linux. A
Windows-created linked worktree with a drive-letter `.git` pointer is not
interchangeable with that clone. A native Linux filesystem checkout also works
when invoking the worker directly inside WSL. Install Linux project dependencies
and Linux-compatible hook entrypoints, then configure Git identity and remote authentication in the same runtime.

With Leafcutter deployed, use its installed dependency manifests:

```bash
/opt/leafcutter-worker/venv/bin/python -m pip install -r /mnt/c/projects/worker-project/.leafcutter/scripts/background_worker/requirements.txt
npm ci --prefix /mnt/c/projects/worker-project/.leafcutter/scripts/background_worker/reviewer_sdk
codex login
gh auth login
```

Authenticate the chosen reviewer inside Linux. For Codex SDK review the explicit
model in this example is `gpt-6-sol`; access must be available to that sign-in.
The local implementation uses Codex's OSS harness with Ollama, not that hosted
reviewer model. Use a separate terminal to run the loopback-only Ollama server:

```bash
OLLAMA_HOST=127.0.0.1:11434 OLLAMA_CONTEXT_LENGTH=65536 OLLAMA_NUM_PARALLEL=1 OLLAMA_NO_CLOUD=1 ollama serve
```

Then, in another Linux terminal:

```bash
ollama pull qwen3.5:9b-q4_K_M
ollama ps
```

Keep the server running while the worker runs, or configure its own Linux service
with those same environment settings. Do not bind Ollama to `0.0.0.0` to connect
the Windows app: this worker and Ollama run together inside WSL. A 65,536-token
context meets [Ollama's coding-agent guidance](https://docs.ollama.com/context-length).
On the validation machine this Qwen model used approximately 8.7 GB and CPU
inference; that is an observation, not a universal hardware requirement or speed
promise. `ollama ps` reports loaded models only after a call. Start with one
agent call and one Ollama inference slot; larger contexts and parallel calls
increase memory requirements.

### Register the Windows launcher

After installation, register the runtime for one disabled repository:

```powershell
python "C:\project\.leafcutter\scripts\background_worker_cli.py" --repo "C:\project" runtime configure-wsl --distribution leafcutter-worker --python /opt/leafcutter-worker/venv/bin/python
```

This checks Linux Python dependencies and Git access, then saves
`.leafcutter/background-worker/runtime.json`. It does not enable the worker,
start inference, or select backlog work. Existing enabled workers or active
execution leases must be drained before changing runtime. Runtime setup does
not replace the sandbox and model preflight performed when enabling work.

Continue using the same Windows CLI commands. Repository, entrypoint, and
`configure --config` paths are converted with `wslpath`, including paths with
spaces. Required checks in the configuration must use Linux executables and
paths, such as `/opt/leafcutter-worker/venv/bin/python`; Windows drive paths
are rejected. A repository must be readable by Linux Git. Windows-created Git
worktrees whose `.git` file points to a Windows-only absolute path need a
Linux-compatible checkout first.

The Linux service detaches from the launcher and logs to the repository worker
state directory, so closing the Windows invocation does not stop active work.
Use `off` to drain it. WSL shutdown or a host restart still requires normal
worker recovery. Native Linux invocations continue to run directly.

Return to [worker configuration and operation](background-ac-worker.md#prepare-execution).


### Windows-generated Git hooks

Prefer installing hooks with the Linux runtime when creating a Linux checkout.
Windows `pre-commit install` intentionally prepends `#!/bin/sh` before its Bash
shebang; reinstalling from Windows restores that prefix. The worker recognizes
that exact generated pre-commit header and runs the complete hook body with
`/bin/bash` inside its existing sandbox. CRLF line endings are normalized in a
private read-only copy mounted at the original hook path, preserving `$0` and
argument handling without modifying the installed hook. Other shell hooks retain their declared
interpreter. A Windows Python path embedded in a generated hook is unavailable
inside Linux; install `pre-commit` on the configured Linux runtime PATH so the
hook's standard fallback can resolve it. Missing dependencies fail the hook.
