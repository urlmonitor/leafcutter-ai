"""Coordinator-owned Git actions; model processes never receive Git write authority."""

from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
from urllib.parse import quote, urlsplit

from .executors import ExecutorError, run_process
from .git_hooks import GitHookSandbox


class GitOps:
    def __init__(self, repo_root, settings, *, invoke=run_process):
        self.repo = Path(repo_root).resolve()
        self.settings = settings
        self.invoke = invoke

    def git(self, workspace, *args, timeout=120):
        if args and args[0] in {"status", "diff"}:
            from .git_extensions import assert_no_executable_filters

            assert_no_executable_filters(workspace, invoke=self.invoke)
        result = self.invoke(
            ["git", "-c", "core.fsmonitor=false", "--no-optional-locks", *args],
            cwd=workspace,
            timeout=timeout,
        ).stdout
        return result if "-z" in args else result.strip()

    def hooked_git(self, workspace, owned, *args, timeout=120):
        boundary = self.hook_boundary(owned)
        with boundary.invocation(workspace) as overrides:
            return self.git(workspace, *overrides, *args, timeout=timeout)

    def hook_boundary(self, owned):
        config = self.settings.get("hook_runtime", {})
        return GitHookSandbox(
            self.repo,
            owned,
            invoke=self.invoke,
            runtime_read_paths=config.get("read_paths", []),
            pre_commit_cache=config.get("pre_commit_cache"),
        )

    def head(self, workspace):
        return self.git(workspace, "rev-parse", "HEAD")

    def target_head(self):
        from .sources import refresh_target

        refresh_target(
            self.repo,
            self.settings.get("target_ref", "origin/main"),
            hook_runtime=self.settings.get("hook_runtime", {}),
        )
        return self.git(
            self.repo,
            "rev-parse",
            "--verify",
            self.settings.get("target_ref", "origin/main") + "^{commit}",
        )

    def publication_base(self, workspace):
        target = self.settings.get("target_ref", "origin/main")
        normalized = target.removeprefix("refs/remotes/")
        remotes = sorted(self.git(workspace, "remote").splitlines(), key=len, reverse=True)
        for remote in remotes:
            if normalized.startswith(remote + "/"):
                return normalized[len(remote) + 1 :]
        if target.startswith("refs/remotes/"):
            raise ExecutorError("Publication target remote is unavailable")
        if target.startswith("refs/") and not target.startswith("refs/heads/"):
            raise ExecutorError(
                "Publication requires a target branch, not a tag or other reference"
            )
        return target.removeprefix("refs/heads/")

    @staticmethod
    def github_repository(value):
        """Resolve explicit HTTPS/SSH Git URLs without exposing embedded credentials."""
        if re.match(r"^[^/]+@[^/:]+:[^/]+/[^/]+$", value):
            value = "ssh://" + value.replace(":", "/", 1)
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"https", "ssh"}
            or not parsed.hostname
            or parsed.password
            or parsed.query
            or parsed.fragment
            or (parsed.scheme == "https" and parsed.username)
        ):
            raise ExecutorError(
                "Publication requires an explicit credential-free HTTPS or SSH GitHub remote URL"
            )
        if parsed.scheme == "ssh" and parsed.port not in {None, 22}:
            raise ExecutorError("Custom SSH ports need an explicit GitHub publication mapping")
        parts = parsed.path.strip("/").removesuffix(".git").split("/")
        if len(parts) != 2 or any(
            not re.fullmatch(r"[A-Za-z0-9_.-]+", part) or part in {".", ".."} for part in parts
        ):
            raise ExecutorError(
                "Publication remote must identify exactly one GitHub owner/repository"
            )
        host = parsed.hostname.lower()
        if parsed.scheme == "https" and parsed.port not in {None, 443}:
            host += ":" + str(parsed.port)
        return "https://" + host + "/" + "/".join(parts)

    def publication_destination(self, workspace):
        """Remote targets bind directly; local branches use tracking or origin."""
        target = self.settings.get("target_ref", "origin/main")
        remotes = sorted(self.git(workspace, "remote").splitlines(), key=len, reverse=True)
        normalized = target.removeprefix("refs/remotes/")
        remote = next((name for name in remotes if normalized.startswith(name + "/")), None)
        base = self.publication_base(workspace)
        if remote is None:
            branch = target.removeprefix("refs/heads/")
            tracking = self.git(
                workspace, "config", "--get", "--default", "", f"branch.{branch}.remote"
            )
            merge = self.git(
                workspace, "config", "--get", "--default", "", f"branch.{branch}.merge"
            )
            remote = tracking or "origin"
            if tracking:
                if not merge.startswith("refs/heads/"):
                    raise ExecutorError(
                        "Local publication target requires one tracked remote branch"
                    )
                base = merge.removeprefix("refs/heads/")
        if remote not in remotes:
            raise ExecutorError(
                "Publication requires the target tracking remote or an origin remote for a local branch"
            )
        fetch = self.git(workspace, "remote", "get-url", "--all", remote).splitlines()
        push = self.git(workspace, "remote", "get-url", "--push", "--all", remote).splitlines()
        if len(fetch) != 1 or len(push) != 1:
            raise ExecutorError("Publication requires exactly one fetch and push repository URL")
        repository = self.github_repository(fetch[0])
        if self.github_repository(push[0]).lower() != repository.lower():
            raise ExecutorError(
                "Target fetch and push repositories differ; implicit fork publication is unsupported"
            )
        return {"remote": remote, "base": base, "repository": repository}

    def prepare(self, run):
        self._assert_hooks_safe(self.repo)
        branch = "codex/background-" + re.sub(r"[^a-zA-Z0-9-]", "-", run["id"])
        location = (self.repo / ".leafcutter" / "background-worktrees" / run["id"]).resolve()
        base = self.target_head()
        if location.exists():
            if self.git(location, "branch", "--show-current") != branch:
                raise ExecutorError("Existing worker worktree has unexpected branch")
            if self.head(location) != base or self.git(location, "status", "--porcelain"):
                raise ExecutorError(
                    "Interrupted worktree creation has changed contents/base; human reconciliation required"
                )
        else:
            location.parent.mkdir(parents=True, exist_ok=True)
            self.hooked_git(
                self.repo, location, "worktree", "add", "-b", branch, str(location), base, timeout=600
            )
        from .bootstrap import provision_runtime

        if provision_runtime(self.repo, location, self.invoke):
            self.hooked_git(location, location, "hook", "run", "--ignore-missing", "pre-commit", timeout=660)
        return {"workspace": str(location), "branch": branch, "base_sha": base}

    def verify_publication_base(self, workspace, destination, expected_base):
        from .sources import refresh_target

        target = destination["remote"] + "/" + destination["base"]
        refresh_target(self.repo, target, hook_runtime=self.settings.get("hook_runtime", {}))
        actual = self.git(workspace, "rev-parse", "refs/remotes/" + target + "^{commit}")
        if actual != expected_base:
            raise ExecutorError(
                "Publication remote base differs from the validated base; reconciliation required"
            )

    def assert_workspace(self, run):
        workspace = Path(run["workspace"]).resolve(strict=True)
        expected = (self.repo / ".leafcutter" / "background-worktrees" / run["id"]).resolve()
        if (
            workspace != expected
            or self.git(workspace, "branch", "--show-current") != run["payload"]["branch"]
        ):
            raise ExecutorError("Worker workspace/branch ownership changed")
        return workspace

    def commit(self, run, ac_id, *, timeout=660):
        from .git_deadline import commit_deadline

        with commit_deadline(self, timeout):
            return self._commit(run, ac_id)

    def _commit(self, run, ac_id):
        workspace = self.assert_workspace(run)
        # Hooks and coordinator checks run normally; never stage another checkout.
        changed = self.git(workspace, "status", "--porcelain", "--untracked-files=all")
        if changed:
            self._assert_hooks_safe(workspace)
            self.git(workspace, "diff", "--no-ext-diff", "--no-textconv", "--check")
            self.hooked_git(workspace, workspace, "add", "--all", "--", ".")
            self.hooked_git(
                workspace,
                workspace,
                "commit",
                "-m",
                f"feat: implement {ac_id} in background worker",
                timeout=660,
            )
        if self.git(workspace, "status", "--porcelain"):
            raise ExecutorError("Commit hooks left uncommitted changes; revalidation required")
        return self.head(workspace)

    def _assert_hooks_safe(self, workspace):
        self.hook_boundary(workspace).preflight(workspace)
        from .git_extensions import assert_no_executable_filters

        assert_no_executable_filters(workspace, invoke=self.invoke)

    def package(self, run, evidence):
        workspace = self.assert_workspace(run)
        if self.git(workspace, "status", "--porcelain"):
            raise ExecutorError("Review requires a clean committed worktree")
        return {
            "head_sha": self.head(workspace),
            "base_sha": run["payload"]["base_sha"],
            "ac_ids": run["plan"]["ac_ids"],
            "review_ac_ids": sorted(
                set(run["plan"]["ac_ids"])
                | set(run["plan"]["source_context"].get("obligations", {}))
            ),
            "source_context": run["plan"]["source_context"],
            "evidence": evidence,
            "diff": self.git(
                workspace,
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                run["payload"]["base_sha"],
                "HEAD",
                "--",
                ".",
            ),
        }

    def publish(self, run, expected_sha):
        workspace = self.assert_workspace(run)
        if self.head(workspace) != expected_sha or self.git(workspace, "status", "--porcelain"):
            raise ExecutorError("Head changed after checks/review; publication refused")
        branch = run["payload"]["branch"]
        destination = self.publication_destination(workspace)
        previous = run["payload"].get("publication_destination")
        if previous is not None and previous != destination:
            raise ExecutorError("Publication destination changed; explicit reconciliation required")
        self.verify_publication_base(workspace, destination, run["payload"].get("base_sha"))
        base, repository = destination["base"], destination["repository"]

        def existing():
            result = self.invoke(
                [
                    "gh",
                    "pr",
                    "list",
                    "--repo",
                    repository,
                    "--head",
                    branch,
                    "--state",
                    "all",
                    "--json",
                    "url,headRefOid,isDraft,state,baseRefName",
                ],
                cwd=workspace,
                timeout=60,
            )
            entries = json.loads(result.stdout)
            if len(entries) > 1:
                raise ExecutorError("Multiple publication records require human reconciliation")
            if entries:
                item = entries[0]
                if (
                    item["headRefOid"] != expected_sha
                    or not item["isDraft"]
                    or item["state"] != "OPEN"
                    or item["baseRefName"] != base
                ):
                    raise ExecutorError(
                        "Existing PR is not the exact reviewed draft; human reconciliation required"
                    )
                return item["url"]
            return None

        found = existing()
        if found:
            return found
        self._assert_hooks_safe(workspace)
        self.hooked_git(
            workspace,
            workspace,
            "push",
            "--set-upstream",
            destination["remote"],
            f"refs/heads/{branch}:refs/heads/{branch}",
        )
        context = run["plan"]["source_context"]
        repo_url = json.loads(
            self.invoke(
                ["gh", "repo", "view", repository, "--json", "url"], cwd=workspace, timeout=60
            ).stdout
        )["url"]
        if self.github_repository(repo_url).lower() != repository.lower():
            raise ExecutorError("GitHub CLI resolved a different publication repository")
        links = []
        for ac_id in sorted(context.get("obligations", {}) or run["plan"]["ac_ids"]):
            matches = list((self.repo / "docs" / "acceptance-criteria").rglob(ac_id + ".yaml"))
            if len(matches) == 1:
                relative = matches[0].relative_to(self.repo).as_posix()
                links.append(f"- [{ac_id}]({repo_url}/blob/{expected_sha}/{quote(relative)})")
            else:
                links.append(f"- {ac_id} (approved source revision recorded below)")
        details = json.dumps(
            {
                "ac_ids": run["plan"]["ac_ids"],
                "source_revision": context.get("source_revision"),
                "ac_revisions": context.get("ac_revisions", {}),
                "reference_revisions": context.get("adr_revisions", {}),
                "validated_sha": run["payload"].get("validated_sha"),
                "checks": run["payload"].get("package", {}).get("feature_checks", []),
                "evidence": run["payload"].get("evidence", {}),
                "review": run["payload"].get("review", {}),
            },
            indent=2,
        )
        if len(details) > 50000:
            raise ExecutorError(
                "Complete delivery evidence exceeds PR body limit; human packaging required"
            )
        body = (
            f"Implements {run['feature_id']} in an isolated accumulating worktree.\n\n"
            f"Reviewed head: `{expected_sha}`. Required project checks and the configured SDK review passed.\n\n"
            "Draft for human review and merge.\n\n"
            + "\n".join(links)
            + "\n\n```json\n"
            + details
            + "\n```\n"
        )
        with tempfile.TemporaryDirectory(prefix="leafcutter-pr-") as temporary:
            path = Path(temporary) / "body.md"
            path.write_text(body, encoding="utf-8")
            self.invoke(
                [
                    "gh",
                    "pr",
                    "create",
                    "--repo",
                    repository,
                    "--draft",
                    "--head",
                    branch,
                    "--base",
                    base,
                    "--title",
                    f"Implement {run['feature_id']}",
                    "--body-file",
                    str(path),
                ],
                cwd=workspace,
                timeout=120,
            )
        found = existing()
        if not found:
            raise ExecutorError("PR publication outcome uncertain; reconcile before retry")
        return found
