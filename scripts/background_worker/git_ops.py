"""Coordinator-owned Git actions; model processes never receive Git write authority."""

from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
from urllib.parse import quote

from .executors import ExecutorError, run_process


class GitOps:
    def __init__(self, repo_root, settings, *, invoke=run_process):
        self.repo = Path(repo_root).resolve()
        self.settings = settings
        self.invoke = invoke

    def git(self, workspace, *args):
        return self.invoke(["git", *args], cwd=workspace, timeout=120).stdout.strip()

    def head(self, workspace):
        return self.git(workspace, "rev-parse", "HEAD")

    def target_head(self):
        from .sources import refresh_target

        refresh_target(self.repo, self.settings.get("target_ref", "origin/main"))
        return self.git(
            self.repo,
            "rev-parse",
            "--verify",
            self.settings.get("target_ref", "origin/main") + "^{commit}",
        )

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
            self.git(self.repo, "worktree", "add", "-b", branch, str(location), base)
        return {"workspace": str(location), "branch": branch, "base_sha": base}

    def assert_workspace(self, run):
        workspace = Path(run["workspace"]).resolve(strict=True)
        expected = (self.repo / ".leafcutter" / "background-worktrees" / run["id"]).resolve()
        if (
            workspace != expected
            or self.git(workspace, "branch", "--show-current") != run["payload"]["branch"]
        ):
            raise ExecutorError("Worker workspace/branch ownership changed")
        return workspace

    def commit(self, run, ac_id):
        workspace = self.assert_workspace(run)
        # Hooks and coordinator checks run normally; never stage another checkout.
        changed = self.git(workspace, "status", "--porcelain", "--untracked-files=all")
        if changed:
            self._assert_hooks_safe(workspace)
            self.git(workspace, "diff", "--check")
            self.git(workspace, "add", "--all", "--", ".")
            self.git(workspace, "commit", "-m", f"feat: implement {ac_id} in background worker")
        if self.git(workspace, "status", "--porcelain"):
            raise ExecutorError("Commit hooks left uncommitted changes; revalidation required")
        return self.head(workspace)

    def _assert_hooks_safe(self, workspace):
        # Git resolves core.hooksPath here. Hook programs can import model-written
        # files; invoking them outside the model sandbox would bypass isolation.
        hooks = Path(self.git(workspace, "rev-parse", "--git-path", "hooks"))
        if not hooks.is_absolute():
            hooks = Path(workspace) / hooks
        if hooks.is_dir() and any(
            path.is_file() and not path.name.endswith(".sample") for path in hooks.iterdir()
        ):
            raise ExecutorError(
                "Repository Git hooks require sandboxed coordinator support. This worker will not execute "
                "hooks outside its filesystem boundary or skip them; use manual delivery for this repository."
            )

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
            "diff": self.git(workspace, "diff", run["payload"]["base_sha"], "HEAD", "--", "."),
        }

    def publish(self, run, expected_sha):
        workspace = self.assert_workspace(run)
        if self.head(workspace) != expected_sha or self.git(workspace, "status", "--porcelain"):
            raise ExecutorError("Head changed after checks/review; publication refused")
        branch = run["payload"]["branch"]
        target = self.settings.get("target_ref", "origin/main")
        base = target.removeprefix("origin/")

        def existing():
            result = self.invoke(
                [
                    "gh",
                    "pr",
                    "list",
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
        self.git(workspace, "push", "--set-upstream", "origin", branch)
        context = run["plan"]["source_context"]
        repo_url = json.loads(
            self.invoke(["gh", "repo", "view", "--json", "url"], cwd=workspace, timeout=60).stdout
        )["url"]
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
