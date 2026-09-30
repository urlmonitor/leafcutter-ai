"""Prototype: triage tests for vacuity with Jev (TypeSafe System One).

Picks tests / code / ticket, asks Jev a set of literal judgement questions per
test function (N repeats, in parallel), aggregates the answers, and prints which
attacks to run first. It does NOT decide whether a test is solid -- only a
mutation run can do that. See docs/analysis/2026-09-25-test-writers-prove-failure-not-discrimination.md.

Examples
  python judge.py --test path/to/test_x.py --repo <repo> --dry-run
  python judge.py --ticket path/to/ticket.md --repo <repo> --runs 3
  python judge.py --changed-since origin/main --repo <repo> --runs 3 --parallel 8
  python judge.py --samples --runs 3
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import secrets
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

import collect
import questions as Q

API_URL = "https://api.typesafe.ai/v1/systemone"
PRICE_PER_INPUT_TOKEN = 42e-9  # $42 per billion input tokens; output is free
HERE = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------- api key

def load_api_key(env_file: Path | None) -> str | None:
    for var in ("JEV_API_KEY", "TYPESAFE_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    if env_file and env_file.is_file():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key.strip().removeprefix("export ").strip() in ("JEV_API_KEY", "TYPESAFE_API_KEY"):
                return value.strip().strip("'\"")
    return None


# ------------------------------------------------------------------- request

def build_request(test: collect.TestUnit, code: list[collect.CodeUnit],
                  ticket: str | None, model: str, max_test_chars: int,
                  max_code_chars: int, wiring: bool = False, abstain: bool = False,
                  callers: dict | None = None) -> tuple[dict, dict]:
    """Return (request body without uid, attack map keyed like the questions).

    abstain: ask the ticket and gate questions as yes/no/need_* choices (questions.as_abstain_choice).
    callers: {function: call sites} from callers.find_callers, added to the state as `production_callers`.
    """
    state = {
        "test": {
            "file": Path(test.file).name,
            "name": test.name,
            "source": test.source[:max_test_chars],
            "fixtures": {k: v[:max_test_chars // 2] for k, v in test.fixtures.items()},
        },
        "code_under_test": [
            {"file": c.file, "is_diff": c.from_diff,
             "excerpt": collect.narrow(c, "\n".join([test.source, *test.fixtures.values()]),
                                       max_code_chars)}
            for c in code],
    }
    qs = dict(Q.TEST_QUESTIONS)
    if wiring:
        qs.update(Q.WIRING_QUESTIONS)
    if ticket:
        state["ticket_intent"] = ticket
        qs.update(Q.TICKET_QUESTIONS)
    for c in code:
        for i, gate in enumerate(c.gates):
            qs[f"gate:{Path(c.file).name}:{i}"] = Q.gate_question(gate)
    if callers is not None:
        state["production_callers"] = callers
    if abstain:
        qs = {k: ((Q.as_abstain_choice(q), a) if Q.abstain_weak_is_no(k) and q["type"] == "noul" else (q, a))
              for k, (q, a) in qs.items()}
    body = {"model": model, "state": state, "questions": {k: q for k, (q, _) in qs.items()}}
    return body, {k: attack for k, (_, attack) in qs.items()}


def call_jev(client: httpx.Client, key: str, body: dict, run: int, retries: int = 5) -> dict:
    body = json.loads(json.dumps(body))
    # Fresh throwaway field per repeat, as in TypeSafe's self-consistency cookbook.
    body["state"]["uid"] = f"{run}:{secrets.token_hex(4)}"
    delay = 1.0
    for attempt in range(retries + 1):
        r = client.post(API_URL, json=body, headers={"Authorization": f"Bearer {key}"})
        if r.status_code in (429, 529) or r.status_code >= 500:
            if attempt == retries:
                r.raise_for_status()
            wait = float(r.headers.get("retry-after", delay))
            time.sleep(wait + random.random() * 0.5)
            delay = min(delay * 2, 30)
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
        return r.json()
    raise RuntimeError("unreachable")


# ----------------------------------------------------------------- aggregate

def weak_value(key: str, answer: dict) -> float | None:
    """Map one answer onto 0..1 where 1 = points at weakness."""
    t = answer.get("type")
    if t == "noul":
        v = answer["noul"]
        return 1 - v if (key in Q.INVERTED or key.startswith("gate:")) else v
    if t == "score":
        levels = max(len(answer.get("legend", {})) - 1, 1)
        return answer["score"] / levels
    if t == "choice":
        p = answer["probabilities"]
        if "no" in p:  # --abstain yes/no/need_* choice: weak = P(no)
            return p["no"]
        # test_kind: weak-ish when it is only a smoke/characterization test
        return p.get("smoke", 0) + p.get("characterization", 0)
    return None


def abstain_parts(answer: dict) -> tuple[float, float] | None:
    """For a yes/no/need_* choice: (need mass, P(no | decided)). None for any other answer."""
    p = answer.get("probabilities") or {}
    if answer.get("type") != "choice" or "no" not in p:
        return None
    need = sum(v for k, v in p.items() if k.startswith("need_"))
    decided = p.get("yes", 0) + p["no"]
    return need, (p["no"] / decided if decided > 0 else 0.5)


def aggregate(key: str, answers: list[dict]) -> dict:
    vals = [v for v in (weak_value(key, a) for a in answers) if v is not None]
    out: dict = {"runs": len(vals)}
    if not vals:
        return out
    lo, hi = Q.UNCERTAIN_BAND
    mean = statistics.fmean(vals)
    out.update(weak=round(mean, 3), spread=round(max(vals) - min(vals), 3))
    out["stable"] = out["spread"] <= 0.15 and not (min(vals) < 0.5 < max(vals))
    out["reading"] = "weak" if mean >= hi else ("uncertain" if mean > lo else "ok")
    if answers[0].get("type") == "choice":
        votes = [a["choice"] for a in answers]
        out["choice"] = max(set(votes), key=votes.count)
        out["confidence"] = round(statistics.fmean(a["confidence"] for a in answers), 3)
    return out


def verdict_v1(static: dict, agg: dict) -> str:
    """Rule written BEFORE any real data (2026-09-25 samples only). Kept for comparison."""
    if static.get("skipped") or static.get("no_assertions") or static.get("trivially_true"):
        return "SUSPECT (static)"
    signals = {k: a for k, a in agg.items() if k not in Q.TRIAGE_ONLY}
    weak = [k for k, a in signals.items() if a.get("reading") == "weak"]
    if static or len(weak) >= 2 or any(k.startswith("gate:") for k in weak):
        return "ATTACK FIRST"
    if weak or any(a.get("reading") == "uncertain" or a.get("stable") is False for a in signals.values()):
        return "UNCERTAIN -> escalate"
    return "no flags (still unproven)"


def verdict_v2(static: dict, agg: dict) -> str:
    """Rule revised AFTER the 13-case bybit-trader evaluation -- therefore fitted to it.

    Pre-registered for the next, out-of-sample run: flag on a hard static finding,
    on exercises_ticket_scenario >= 0.40, or on any gate >= 0.70. has_control_case
    and the triage-only questions are ignored (they misfired). Do not retune it on
    the data it is being tested against.
    """
    if static.get("skipped") or static.get("no_assertions") or static.get("trivially_true"):
        return "SUSPECT (static)"
    w = lambda k: agg.get(k, {}).get("weak") or 0.0  # noqa: E731
    if w("exercises_ticket_scenario") >= 0.40 or any(
            a.get("weak", 0) >= 0.70 for k, a in agg.items() if k.startswith("gate:")):
        return "ATTACK FIRST"
    if w("exercises_ticket_scenario") >= 0.20 or w("weakness") >= 0.60:
        return "UNCERTAIN -> escalate"
    return "no flags (still unproven)"


VERDICT_RULES = {"v1": verdict_v1, "v2": verdict_v2}
verdict = verdict_v2


def readings(weak: dict) -> dict:
    """Rebuild aggregate-like dicts from stored mean weak values (for re-scoring)."""
    lo, hi = Q.UNCERTAIN_BAND
    return {k: {"weak": v, "reading": "weak" if v >= hi else "uncertain" if v > lo else "ok", "stable": True}
            for k, v in weak.items() if v is not None}


# ---------------------------------------------------------------------- main

def pick(args) -> collect.Bundle:
    repo = Path(args.repo).resolve()
    ticket_text = None
    test_paths = [Path(p).resolve() for p in args.test]
    code_paths = [Path(p).resolve() for p in args.code]
    if args.ticket:
        ticket_text, files = collect.read_ticket(Path(args.ticket))
        t, c = collect.split_tests_and_code([repo / f for f in files if (repo / f).is_file()])
        test_paths += t
        code_paths += c
    if args.changed_since:
        t, c = collect.split_tests_and_code(collect.changed_files(repo, args.changed_since))
        test_paths += t
        code_paths += c
    if not code_paths:
        for tp in test_paths:
            code_paths += [p for p in collect.resolve_code_for_test(tp, repo) if p not in code_paths]
    only = set(args.only) if args.only else None
    tests = [u for p in dict.fromkeys(test_paths) for u in collect.extract_tests(p, only)]
    code = [collect.code_unit(p, repo, args.diff_base or args.changed_since, args.max_code_chars)
            for p in dict.fromkeys(code_paths)]
    manual = json.loads((repo / "gates.json").read_text()) if args.samples else {}
    for c in code:
        c.gates += manual.get(Path(c.file).name, []) + list(args.gate)
    if ticket_text:
        ticket_text = ticket_text[: args.max_ticket_chars]
    return collect.Bundle(tests, code, ticket_text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".", help="repo root used to resolve paths and git diffs")
    ap.add_argument("--test", action="append", default=[], help="test file (repeatable)")
    ap.add_argument("--code", action="append", default=[], help="code-under-test file (repeatable; default: from imports)")
    ap.add_argument("--ticket", help="ticket .md: adds its intent and its files_touched")
    ap.add_argument("--changed-since", help="git ref: pick changed tests and code, gates from the diff")
    ap.add_argument("--diff-base", help="git ref to diff code against (for gate extraction)")
    ap.add_argument("--only", action="append", help="only these test function names")
    ap.add_argument("--gate", action="append", default=[], help="a condition to check the fixture reaches (repeatable)")
    ap.add_argument("--samples", action="store_true", help="run the bundled bad/good sample pairs")
    ap.add_argument("--runs", type=int, default=3, help="repeats per test function")
    ap.add_argument("--parallel", type=int, default=6, help="concurrent requests")
    ap.add_argument("--model", default="jev-latest")
    ap.add_argument("--max-code-chars", type=int, default=12000)
    ap.add_argument("--max-test-chars", type=int, default=8000)
    ap.add_argument("--max-ticket-chars", type=int, default=4000)
    ap.add_argument("--env-file", default=".env", help="fallback for JEV_API_KEY")
    ap.add_argument("--dry-run", action="store_true", help="build requests, print sizes, send nothing")
    ap.add_argument("--show-request", action="store_true", help="with --dry-run: print the first request body")
    ap.add_argument("--out", help="write the full JSON report here")
    args = ap.parse_args(argv)

    if args.samples:
        args.repo = str(HERE / "samples")
        args.test = [str(p) for p in sorted((HERE / "samples").glob("test_*.py"))]
    bundle = pick(args)
    if not bundle.tests:
        print("No test functions found.", file=sys.stderr)
        return 2

    # Per test function: the code that file resolves to (samples pair by stem).
    jobs = []
    for t in bundle.tests:
        code = bundle.code
        if args.samples:
            stem = Path(t.file).stem.removeprefix("test_").rsplit("_", 1)[0]
            code = [c for c in bundle.code if Path(c.file).stem == stem]
        body, attacks = build_request(t, code, bundle.ticket_intent, args.model,
                                      args.max_test_chars, args.max_code_chars)
        jobs.append((t, body, attacks))

    total_chars = sum(len(json.dumps(b)) for _, b, _ in jobs)
    est_tokens = total_chars // 4 * args.runs
    print(f"{len(jobs)} test function(s) x {args.runs} run(s) = {len(jobs) * args.runs} request(s); "
          f"~{est_tokens:,} input tokens (~${est_tokens * PRICE_PER_INPUT_TOKEN:.4f})")
    for t, b, _ in jobs:
        print(f"  {t.name:<60} {len(json.dumps(b)):>7,} chars  {len(b['questions'])} questions"
              f"  static={list(t.static_flags) or '-'}")
    if args.dry_run:
        if args.show_request:
            print(json.dumps(jobs[0][1], indent=2)[:20000])
        return 0

    key = load_api_key(Path(args.env_file))
    if not key:
        print("No JEV_API_KEY / TYPESAFE_API_KEY in the environment or --env-file.", file=sys.stderr)
        return 2

    results: dict[int, list[dict]] = {i: [] for i in range(len(jobs))}
    usage_tokens, errors, started = 0, [], time.perf_counter()
    with httpx.Client(timeout=60) as client, ThreadPoolExecutor(args.parallel) as pool:
        futs = {pool.submit(call_jev, client, key, body, r): i
                for i, (_, body, _) in enumerate(jobs) for r in range(args.runs)}
        for f in as_completed(futs):
            try:
                resp = f.result()
                results[futs[f]].append(resp)
                usage_tokens += resp.get("usage", {}).get("input_tokens", 0)
            except Exception as e:  # keep going; report at the end
                logger.warning("call_jev failed for %s: %s", jobs[futs[f]][0].name, e)
                errors.append(f"{jobs[futs[f]][0].name}: {e}")
    elapsed = time.perf_counter() - started

    report = []
    for i, (t, body, attacks) in enumerate(jobs):
        agg = {k: aggregate(k, [r["answers"][k] for r in results[i] if k in r.get("answers", {})])
               for k in body["questions"]}
        weak_keys = [k for k, a in agg.items() if a.get("reading") in ("weak", "uncertain")]
        report.append({
            "test": t.name, "file": t.file, "verdict": verdict(t.static_flags, agg),
            "static_flags": t.static_flags, "answers": agg,
            "attacks_first": [attacks[k] for k in sorted(weak_keys, key=lambda k: -agg[k]["weak"])],
            "model": results[i][0]["model"] if results[i] else None,
        })

    for r in report:
        print(f"\n== {r['test']}  [{r['verdict']}]")
        for k, v in r["static_flags"].items():
            print(f"   static  {k:<30} {v}")
        for k, a in r["answers"].items():
            if "weak" in a:
                extra = f" choice={a['choice']}" if "choice" in a else ""
                flag = "" if a["stable"] else "  (unstable across runs)"
                print(f"   jev     {k:<30} weak={a['weak']:.2f} spread={a['spread']:.2f} {a['reading']}{extra}{flag}")
        for att in r["attacks_first"][:4]:
            print(f"   -> {att}")
    print(f"\n{sum(len(v) for v in results.values())} response(s) in {elapsed:.1f}s, "
          f"{usage_tokens:,} input tokens (${usage_tokens * PRICE_PER_INPUT_TOKEN:.5f})")
    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
