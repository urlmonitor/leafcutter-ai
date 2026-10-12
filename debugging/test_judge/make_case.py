"""Build one labelled evaluation case from git, verbatim, without touching the work tree.

Every file is taken with `git show <sha>:<path>`, so a case can never contain a
hand-edited test. The label and its evidence are yours to supply -- they must
quote a commit message, ticket, retrospective or doc, never an opinion.

  python make_case.py --repo <repo> --out <cases-dir> --case-id bo1700_bad \
      --sha 50e28cc1^ --test unit_tests/x/test_y.py --test-function TestY.test_z \
      --code scripts/x/y.py --label vacuous --incident "BO-1700 fail-open gate" \
      --gate "if not freshness_ok:" --ticket-intent "..." --evidence "50e28cc1 message: ..." \
      --why "never feeds a stale hook through run_checks()"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def git_show(repo: Path, sha: str, path: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(repo), "show", f"{sha}:{path}"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        sys.exit(f"git show {sha}:{path} failed to run: {exc}")
    if r.returncode != 0:
        sys.exit(f"git show {sha}:{path} failed: {r.stderr.strip()}")
    return r.stdout


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True, help="cases directory")
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--sha", required=True, help="commit the test AND code are taken from")
    ap.add_argument("--test", required=True, help="repo path of the test file")
    ap.add_argument("--test-function", required=True, help="ClassName.test_name or test_name")
    ap.add_argument("--code", action="append", required=True, help="repo path of code under test (max 3)")
    ap.add_argument("--label", required=True, choices=["vacuous", "discriminating"])
    ap.add_argument("--incident", required=True, help="same string for both halves of a pair")
    ap.add_argument("--gate", action="append", default=[], help="condition verbatim from the code")
    ap.add_argument("--ticket-intent", required=True, help="identical text for both halves of a pair")
    ap.add_argument("--evidence", required=True, help="quote + source proving the label")
    ap.add_argument("--why", required=True)
    args = ap.parse_args(argv)

    repo = Path(args.repo)
    if len(args.code) > 3:
        sys.exit("at most 3 code files -- keep only what the test exercises")
    folder = Path(args.out) / args.case_id
    (folder / "code").mkdir(parents=True, exist_ok=True)
    test_text = git_show(repo, args.sha, args.test)
    if args.test_function.rpartition(".")[2] not in test_text:
        sys.exit(f"{args.test_function} not found in {args.test} at {args.sha}")
    (folder / "test.py").write_text(test_text, encoding="utf-8", newline="")
    for path in args.code:
        text = git_show(repo, args.sha, path)
        (folder / "code" / Path(path).name).write_text(text, encoding="utf-8", newline="")
    code_blob = "\n".join((folder / "code" / Path(p).name).read_text(encoding="utf-8") for p in args.code)
    missing = [g for g in args.gate if " ".join(g.split()) not in " ".join(code_blob.split())]
    if missing:
        print(f"WARNING: gate(s) not found verbatim in the code at {args.sha}: {missing}", file=sys.stderr)
    try:
        rev_parse = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", args.sha],
                                   capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError) as exc:
        sys.exit(f"git rev-parse --short {args.sha} failed to run: {exc}")
    sha = rev_parse.stdout.strip()
    meta = {
        "case_id": args.case_id, "incident": args.incident, "label": args.label,
        "test_function": args.test_function, "gates": args.gate,
        "ticket_intent": args.ticket_intent, "commit": sha, "test_path": args.test,
        "code_paths": args.code, "evidence": args.evidence, "why": args.why,
    }
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
