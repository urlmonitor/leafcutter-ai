"""Score the judge's questions against a labelled set of real tests.

A case folder holds `test.py`, `code/<files>`, and `meta.json` with
`label` ("vacuous" | "discriminating"), `test_function`, `gates`, `ticket_intent`.

  python eval.py --cases <dir> --strip-comments --runs 5 --out jev.json      # run Jev
  python eval.py --cases <dir> --strip-comments --export <dir>               # blind req_NN files + mapping
  python eval.py --cases <dir> --strip-comments --from-answers a1.json --from-answers a2.json                  --mapping <dir>_mapping.json --answers-model haiku --out haiku.json
  python eval.py --cases <dir> --score jev.json --score haiku.json

Use the SAME flags (--strip-comments, --wiring, --no-ticket) for the run, the export
and the import, or the question sets will not line up.

Scoring: per question, AUC = share of (vacuous, discriminating) pairs where the
vacuous test's "weak" value is higher by more than MARGIN (ties count half);
0.5 = no signal. "pairs won" does the same only within one incident. Verdict
rules v1 (pre-data) and v2 (fitted on bybit-trader) are reported as flag counts.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

import callers as callers_mod
import collect
import judge
import questions as Q


def load_case(folder: Path, max_code_chars: int) -> tuple[dict, collect.TestUnit, list[collect.CodeUnit]]:
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    cls, _, fn = meta["test_function"].rpartition(".")
    units = [u for u in collect.extract_tests(folder / "test.py", {fn})
             if not cls or u.name == meta["test_function"]]
    if not units:
        raise ValueError(f"{folder.name}: test function {meta['test_function']} not found")
    code = []
    for p in sorted((folder / "code").glob("*")):
        text = p.read_text(encoding="utf-8", errors="replace")
        code.append(collect.CodeUnit(file=p.name, excerpt=text[:max_code_chars], full_text=text,
                                     gates=list(meta.get("gates", []))))
    return meta, units[0], code


def strip_py(src: str) -> str:
    """Drop comments and docstrings, so a test cannot describe its own quality."""
    import io
    import textwrap
    import tokenize
    try:
        code = textwrap.dedent(src)
        out, prev = [], tokenize.INDENT
        for tok in tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type == tokenize.COMMENT:
                continue
            if tok.type == tokenize.STRING and prev in (tokenize.INDENT, tokenize.NEWLINE, tokenize.DEDENT):
                prev = tok.type
                continue  # a docstring / bare string statement
            out.append(tok)
            if tok.type not in (tokenize.NL, tokenize.COMMENT):
                prev = tok.type
        text = tokenize.untokenize(out)
        return "\n".join(ln.rstrip() for ln in text.splitlines() if ln.strip() not in ("", "\\"))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return src


def build(folder: Path, args) -> tuple[dict, dict, collect.TestUnit]:
    meta, test, code = load_case(folder, args.max_code_chars)
    if getattr(args, "strip_comments", False):
        test.source = strip_py(test.source)
        test.fixtures = {k: strip_py(v) for k, v in test.fixtures.items()}
    callers = None
    if getattr(args, "callers", False):
        callers = callers_mod.find_callers(args.repo, meta["commit"], [test.source, *test.fixtures.values()],
                                           [(c.file, c.full_text) for c in code])
    body, _ = judge.build_request(test, code, meta.get("ticket_intent") if args.ticket else None,
                                  args.model, args.max_test_chars, args.max_code_chars,
                                  wiring=getattr(args, "wiring", False),
                                  abstain=getattr(args, "abstain", False), callers=callers)
    return meta, body, test


def abstain_extras(key: str, answers: list[dict]) -> dict:
    """need:<key> = mean need_* mass; decided:<key> = mean P(no | yes-or-no). Empty for other questions."""
    parts = [p for p in (judge.abstain_parts(a) for a in answers) if p is not None]
    if not parts:
        return {}
    return {f"need:{key}": round(statistics.fmean(n for n, _ in parts), 3),
            f"decided:{key}": round(statistics.fmean(d for _, d in parts), 3)}


def run_jev(cases: list[Path], args) -> dict:
    key = judge.load_api_key(Path(args.env_file))
    if not key:
        sys.exit("No JEV_API_KEY / TYPESAFE_API_KEY")
    built = {c.name: build(c, args) for c in cases}
    answers: dict[str, list[dict]] = {k: [] for k in built}
    tokens, started = 0, time.perf_counter()
    with httpx.Client(timeout=60) as client, ThreadPoolExecutor(args.parallel) as pool:
        futs = {pool.submit(judge.call_jev, client, key, body, r): name
                for name, (_, body, _) in built.items() for r in range(args.runs)}
        for f in as_completed(futs):
            resp = f.result()
            answers[futs[f]].append(resp["answers"])
            tokens += resp.get("usage", {}).get("input_tokens", 0)
    elapsed = time.perf_counter() - started
    out = {"model": args.model, "runs": args.runs, "input_tokens": tokens,
           "cost_usd": tokens * judge.PRICE_PER_INPUT_TOKEN, "seconds": round(elapsed, 2), "cases": {}}
    for name, (meta, body, test) in built.items():
        weak = {k: judge.aggregate(k, [a[k] for a in answers[name] if k in a]).get("weak")
                for k in body["questions"]}
        for k in body["questions"]:
            weak.update(abstain_extras(k, [a[k] for a in answers[name] if k in a]))
        out["cases"][name] = {"weak": weak, "static": test.static_flags}
    return out


def from_answers(cases: list[Path], args, answers_files: list[Path], model: str) -> dict:
    """Turn another model's raw answers {case: [ {qkey: answer}, ... ]} into a result file.

    Answers use Jev's shapes: {"type":"noul","noul":p}, {"type":"choice","choice":..,
    "probabilities":{..},"confidence":..}, {"type":"score","score":x,"legend":{..}}.
    """
    mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8")) if args.mapping else {}
    raw: dict[str, list] = {}
    for f in answers_files:  # each file is one run; keys are req_NN (with --mapping) or case names
        for k, v in json.loads(f.read_text(encoding="utf-8")).items():
            raw.setdefault(mapping.get(k, k), []).extend(v if isinstance(v, list) else [v])
    out = {"model": model, "runs": None, "cases": {}}
    for c in cases:
        if c.name not in raw:
            continue
        _, body, test = build(c, args)
        runs = raw[c.name] if isinstance(raw[c.name], list) else [raw[c.name]]
        out["runs"] = len(runs)
        out["cases"][c.name] = {
            "weak": {k: judge.aggregate(k, [r[k] for r in runs if k in r]).get("weak")
                     for k in body["questions"]},
            "static": test.static_flags,
        }
    return out


def export(cases: list[Path], args, dest: Path) -> None:
    """Write label-free, SHUFFLED, ANONYMISED requests (req_01.json ...) plus mapping.json.

    Case folder names carry the label (x_bad / x_good) -- never hand them to a
    model. The mapping file stays with you; the answering model must not read it.
    """
    import random
    dest.mkdir(parents=True, exist_ok=True)
    names = [c.name for c in cases]
    random.Random(args.seed).shuffle(names)
    by_name = {c.name: c for c in cases}
    mapping = {}
    for i, name in enumerate(names, 1):
        anon = f"req_{i:02d}"
        _, body, _ = build(by_name[name], args)
        (dest / f"{anon}.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
        mapping[anon] = name
    (dest.parent / f"{dest.name}_mapping.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    print(f"wrote {len(cases)} blind request(s) to {dest} (mapping: {dest.name}_mapping.json, keep it away "
          f"from the answering model)")


MARGIN = 0.05  # differences smaller than this are noise, counted as ties


def auc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    wins = sum(1.0 if p - n > MARGIN else 0.0 if n - p > MARGIN else 0.5 for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def question_family(key: str) -> str:
    prefix, sep, rest = key.partition(":")
    if prefix in ("need", "decided") and sep:  # abstain extras: need:gate:x.py:0 -> need:gate
        return f"{prefix}:{question_family(rest)}"
    return "gate" if key.startswith("gate:") else key


def rule_inputs(weak: dict) -> dict:
    """Verdict rules see only the real question answers, never the need:/decided: extras."""
    return {k: v for k, v in weak.items() if not k.startswith(("need:", "decided:"))}


def score(cases: list[Path], result_files: list[Path]) -> None:
    metas = {c.name: json.loads((c / "meta.json").read_text(encoding="utf-8")) for c in cases}
    labels = {k: m["label"] for k, m in metas.items()}
    for rf in result_files:
        res = json.loads(rf.read_text(encoding="utf-8"))
        print(f"\n### {rf.name}  model={res.get('model')} runs={res.get('runs')} "
              f"cost=${res.get('cost_usd', 0):.5f} time={res.get('seconds')}s")
        fam: dict[str, dict[str, list[float]]] = {}
        for name, r in res["cases"].items():
            if name not in labels:
                continue
            for k, v in r["weak"].items():
                if v is None:
                    continue
                f = question_family(k)
                bucket = fam.setdefault(f, {"vacuous": [], "discriminating": []})
                bucket[labels[name]].append(v)
            if "static" in r:  # static checks: 1 if any flag, else 0
                bucket = fam.setdefault("STATIC(any flag)", {"vacuous": [], "discriminating": []})
                bucket[labels[name]].append(1.0 if r["static"] else 0.0)
        # Paired: within one incident, does each vacuous case beat each fixed case by > MARGIN?
        pairs: dict[str, list[int]] = {}
        by_inc: dict[str, dict[str, list[str]]] = {}
        for name, m in metas.items():
            if name in res["cases"]:
                by_inc.setdefault(m.get("incident", name), {}).setdefault(m["label"], []).append(name)
        for inc, grp in by_inc.items():
            for v in grp.get("vacuous", []):
                for d in grp.get("discriminating", []):
                    wv, wd = res["cases"][v]["weak"], res["cases"][d]["weak"]
                    for k in set(map(question_family, wv)) | {"STATIC(any flag)"}:
                        if k == "STATIC(any flag)":
                            a, b = float(bool(res["cases"][v]["static"])), float(bool(res["cases"][d]["static"]))
                        else:
                            av = [x for kk, x in wv.items() if question_family(kk) == k and x is not None]
                            bv = [x for kk, x in wd.items() if question_family(kk) == k and x is not None]
                            if not av or not bv:
                                continue
                            a, b = max(av), max(bv)
                        pairs.setdefault(k, [0, 0])
                        pairs[k][0] += a - b > MARGIN
                        pairs[k][1] += 1
        print(f"{'question':<32}{'AUC':>6}{'pairs won':>11}{'mean weak: vacuous':>22}{'discriminating':>16}{'n':>7}")
        for f, b in sorted(fam.items()):
            a = auc(b["vacuous"], b["discriminating"])
            mv = statistics.fmean(b["vacuous"]) if b["vacuous"] else float("nan")
            md = statistics.fmean(b["discriminating"]) if b["discriminating"] else float("nan")
            pw = pairs.get(f)
            pws = f"{pw[0]}/{pw[1]}" if pw else "-"
            print(f"{f:<32}{(f'{a:.2f}' if a is not None else '  - '):>6}{pws:>11}{mv:>22.2f}{md:>16.2f}"
                  f"{len(b['vacuous']):>4}/{len(b['discriminating'])}")
        for rule_name, rule in judge.VERDICT_RULES.items():
            tp = fp = nv = nd = 0
            for name, r in res["cases"].items():
                if name not in labels:
                    continue
                flagged = rule(r["static"], judge.readings(rule_inputs(r["weak"]))).startswith(("SUSPECT", "ATTACK"))
                if labels[name] == "vacuous":
                    nv += 1
                    tp += flagged
                else:
                    nd += 1
                    fp += flagged
            print(f"verdict {rule_name}: flags {tp}/{nv} vacuous, {fp}/{nd} discriminating (false alarms)")
        print("\nper case (weak values; V = vacuous, D = discriminating):")
        keys = sorted({question_family(k) for r in res["cases"].values() for k in r["weak"]})
        print(f"{'case':<26}{'L':>2} " + " ".join(f"{k[:9]:>9}" for k in keys))
        for name in sorted(res["cases"]):
            if name not in labels:
                continue
            r = res["cases"][name]
            vals = {}
            for k, v in r["weak"].items():
                if v is not None:
                    vals.setdefault(question_family(k), []).append(v)
            row = " ".join(f"{max(vals[k]):>9.2f}" if k in vals else f"{'-':>9}" for k in keys)
            print(f"{name:<26}{labels[name][0].upper():>2} {row}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--export", help="write label-free request bodies to this dir and exit")
    ap.add_argument("--score", action="append", type=Path, help="score result file(s) and exit")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--model", default="jev-latest")
    ap.add_argument("--wiring", action="store_true", help="add the pre-registered wiring questions")
    ap.add_argument("--abstain", action="store_true",
                    help="ask ticket/gate questions as yes/no/need_* choices (development pass)")
    ap.add_argument("--callers", action="store_true",
                    help="add `production_callers` (git grep at the case commit) to the state; needs --repo")
    ap.add_argument("--repo", help="git repo the cases were built from (for --callers)")
    ap.add_argument("--strip-comments", action="store_true", help="remove comments/docstrings from the test")
    ap.add_argument("--no-ticket", dest="ticket", action="store_false", help="omit ticket_intent from state")
    ap.add_argument("--max-code-chars", type=int, default=12000)
    ap.add_argument("--max-test-chars", type=int, default=8000)
    ap.add_argument("--env-file", default=".env")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--from-answers", type=Path, action="append",
                    help="another model's raw answers (repeat once per run) -> result file")
    ap.add_argument("--answers-model", default="other")
    ap.add_argument("--mapping", help="req_NN -> case mapping written by --export")
    ap.add_argument("--seed", type=int, default=7, help="shuffle seed for --export")
    args = ap.parse_args(argv)
    cases = sorted(p for p in Path(args.cases).iterdir() if (p / "meta.json").is_file())
    if args.export:
        export(cases, args, Path(args.export))
        return 0
    if args.score:
        score(cases, args.score)
        return 0
    if args.from_answers:
        res = from_answers(cases, args, args.from_answers, args.answers_model)
        args.out.write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(f"converted {len(res['cases'])} case(s) -> {args.out}")
        return 0
    res = run_jev(cases, args)
    if args.out:
        args.out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"{len(cases)} case(s) x {args.runs} run(s): {res['input_tokens']:,} tokens, "
          f"${res['cost_usd']:.5f}, {res['seconds']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
