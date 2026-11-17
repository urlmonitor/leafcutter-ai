"""KM-400d-4-i: cold retrieval fits the default deadline when the graph host's IPv6 name lookup stalls.

Every test runs the real retrieval path in a fresh subprocess (see ``_km_400d_4_support``): the
resolver is a recording double that answers IPv4-only lookups quickly and blocks (``time.sleep``, not
cancellable) for ``family=0`` lookups. Implementation target: lookups made inside the graph adapter's
own calls ask for IPv4 first, fall back to the normal lookup on failure (logged), remember each
``(name, port)`` for the process lifetime, and leave every lookup outside the adapter untouched.
"""

import socket

from tests.knowledge import _km_400d_4_support as support
from tests.knowledge._km_400d_4_support import (
    PORT,
    READER,
    SERVER,
    fake,
    lookups_of,
    run_outside_lookups,
    run_requests,
    run_retrieve,
    run_third_party_wrap,
    tree,
)

V4 = int(socket.AF_INET)
STALLED_IPV6 = dict(v4_delay=0.05, any_delay=15.0, lookup_reader=True)
FAMILY_SETTING = "LEAFCUTTER_NEO4J_ADDRESS_FAMILY"


def test_km_400d_4_i_cold_retrieve_returns_ok_when_ipv6_lookup_stalls(tmp_path):
    # covers: KM-400d-4-i
    # angle: discrimination
    """Both server names are looked up IPv4-first, so the 15 s family=0 stall never bites: ok with evidence."""
    run = run_retrieve(tmp_path, fake(**STALLED_IPV6))
    answer = run.answer
    assert answer["status"] == "ok", (answer["status"], answer["warnings"])
    assert len(answer["evidence"]) == 1
    # Control for the reader name: it was reached (a stall there would also be unavailable).
    assert lookups_of(run, READER), "the reader name was never looked up"


def test_km_400d_4_i_cold_retrieve_duration_is_below_the_default_deadline(tmp_path):
    # covers: KM-400d-4-i
    # angle: criterion
    """stats.duration_ms is below 10000 and the subprocess ends well before the 15 s stall."""
    run = run_retrieve(tmp_path, fake(**STALLED_IPV6))
    assert run.stats["duration_ms"] < 10000
    assert run.answer["status"] == "ok"
    assert run.returned_at - run.retrieval_start < 9


def test_km_400d_4_i_both_server_names_are_looked_up_ipv4_first(tmp_path):
    # covers: KM-400d-4-i
    # angle: discrimination
    """The first lookup of the configured name AND of the different reader name is IPv4-only."""
    run = run_retrieve(tmp_path, fake(v4_delay=0.0, any_delay=0.0, lookup_reader=True))
    for name in (SERVER, READER):
        calls = lookups_of(run, name)
        assert calls, f"{name} was never looked up"
        assert calls[0]["family"] == V4, f"{name} first lookup asked family {calls[0]['family']}"
    assert run.resolver[0]["family"] == V4, "a family=0 lookup came before the IPv4-first ones"


def test_km_400d_4_i_failed_ipv4_lookup_falls_back_to_the_normal_lookup_address(tmp_path):
    # covers: KM-400d-4-i
    # angle: failure
    """The IPv4 lookup of the server fails; the connect receives the family=0 (IPv6) address."""
    config = fake(v4_fail=[SERVER], any_answer="ipv6")
    run = run_retrieve(tmp_path, config)
    handed = [e for e in run.driver if e["event"] == "lookup" and e["name"] == SERVER]
    assert handed, f"the driver was never handed an address: {run.driver}"
    assert all(e["addresses"] == ["2001:db8::1"] for e in handed), handed
    assert not [e for e in run.driver if e["event"] == "lookup_error"], run.driver
    assert [c["family"] for c in lookups_of(run, SERVER)][:2] == [V4, 0]


def test_km_400d_4_i_failed_ipv4_lookup_is_not_reported_unavailable_and_is_logged(tmp_path):
    # covers: KM-400d-4-i
    # angle: failure
    """ok and exit 0 after the failed IPv4 lookup, and the failure is logged, not swallowed."""
    run = run_retrieve(tmp_path, fake(v4_fail=[SERVER], any_answer="ipv6"))
    assert run.answer["status"] == "ok"
    assert run.returncode == 0
    logged = [line for line in run.stderr.splitlines() if "ipv4" in line.lower()]
    assert logged, f"no log line names the failed IPv4 lookup; stderr={run.stderr!r}"


def test_km_400d_4_i_lookups_outside_the_adapter_keep_the_callers_family(tmp_path):
    # covers: KM-400d-4-i
    # angle: discrimination
    """Outside lookups (main and another thread; unrelated name and the server's own) ask family 0."""
    result, outside = run_outside_lookups(tmp_path)
    assert len(outside) == 4, outside  # two threads x two names, exactly
    assert {r["family"] for r in outside} == {0}, outside
    assert {r["name"] for r in outside} == {"unrelated.example.test", SERVER}
    assert set(result["calls"]) == {"main", "second"}


def test_km_400d_4_i_a_third_party_wrapping_getaddrinfo_later_causes_no_recursion(tmp_path):
    # covers: KM-400d-4-i
    # angle: discrimination
    """A resolver wrapper installed after the adapter's policy neither recurses nor changes the caller's family."""
    verdict, outside = run_third_party_wrap(tmp_path)
    assert verdict["adapter"] == "ok", verdict
    assert verdict["outside"] == "ok", verdict
    assert verdict["wrapper_saw_outside"] == 2, verdict  # the third party still sits in front
    families = [r["family"] for r in outside if r["name"] == "unrelated.example.test"]
    assert families == [0, int(socket.AF_INET6)], outside


def test_km_400d_4_i_a_failed_connect_evicts_the_remembered_address(tmp_path):
    # covers: KM-400d-4-i
    # angle: discrimination
    """After a refused connect the name is resolved again; once it connects it is remembered again."""
    results, run = run_requests(tmp_path, 3, fake(refuse_first_connect=True))
    assert [r["status"] for r in results] == ["unavailable", "ok", "ok"], results
    v4 = [c for c in lookups_of(run, SERVER) if c["family"] == V4]
    assert len(v4) == 2, v4  # the refused address was forgotten; the new one is kept


def test_km_400d_4_i_outside_lookup_is_not_served_from_remembered_lookups(tmp_path):
    # covers: KM-400d-4-i
    # angle: discrimination
    """After the adapter remembered the server, an outside lookup reaches the resolver and gets its new address."""
    result, _ = run_outside_lookups(tmp_path)
    import json

    records = [json.loads(line) for line in (tmp_path / "resolver.jsonl").read_text().splitlines()]
    before_outside = records[: next(i for i, r in enumerate(records) if r.get("mark"))]
    adapter_lookups = [r for r in before_outside if r["name"] == SERVER]
    # Precondition: the adapter really did remember the name (three transactions, one lookup).
    assert len(adapter_lookups) == 1, f"the adapter did not remember the server name: {adapter_lookups}"
    assert result["again"] == ["198.51.100.9"], result["again"]
    assert result["resolver_calls_added"] == 1, result["resolver_calls_added"]


def test_km_400d_4_i_opt_out_any_restores_family_zero_lookups(tmp_path):
    # covers: KM-400d-4-i
    # angle: boundary
    """With LEAFCUTTER_NEO4J_ADDRESS_FAMILY=any every lookup asks family 0; the unset control is IPv4-first."""
    config = fake(lookup_reader=True)
    (tmp_path / "default").mkdir()
    (tmp_path / "any").mkdir()
    control = run_retrieve(tmp_path / "default", config)
    assert control.resolver[0]["family"] == V4, "the default is not IPv4-first, so the opt-out proves nothing"
    opted = run_retrieve(tmp_path / "any", config, extra_env={FAMILY_SETTING: "any"})
    for name in (SERVER, READER):
        calls = lookups_of(opted, name)
        assert calls, f"{name} was never looked up"
        assert {c["family"] for c in calls} == {0}, calls


def test_km_400d_4_i_unrecognised_family_value_warns_and_acts_as_ipv4_first(tmp_path):
    # covers: KM-400d-4-i
    # angle: boundary
    """"ipv6" is reported as a configuration warning naming the setting and acts as the default."""
    run = run_retrieve(tmp_path, fake(**STALLED_IPV6), extra_env={FAMILY_SETTING: "ipv6"})
    answer = run.answer
    assert answer["status"] == "ok", (answer["status"], answer["warnings"])
    assert any(FAMILY_SETTING in warning for warning in answer["warnings"]), answer["warnings"]
    assert lookups_of(run, SERVER)[0]["family"] == V4


def test_km_400d_4_i_each_name_and_port_is_looked_up_at_most_once_over_three_requests(tmp_path):
    # covers: KM-400d-4-i
    # angle: boundary
    """Three requests through one retriever make exactly one IPv4-first lookup per (name, port)."""
    results, run = run_requests(tmp_path, 3, fake(lookup_reader=True))
    assert [r["status"] for r in results] == ["ok", "ok", "ok"]
    for name in (SERVER, READER):
        v4 = [c for c in lookups_of(run, name) if c["family"] == V4 and c["port"] == PORT]
        assert len(v4) == 1, f"{name}:{PORT} looked up {len(v4)} times over three requests"


def test_km_400d_4_i_a_second_process_looks_each_name_up_again_and_writes_no_file(tmp_path):
    # covers: KM-400d-4-i
    # angle: real_artifact
    """A second fresh process looks both names up again, and no remembered-lookup file appears."""
    config = fake(lookup_reader=True)
    first = run_retrieve(tmp_path, config)
    assert first.answer["status"] == "ok"
    (tmp_path / "resolver.jsonl").rename(tmp_path / "resolver_first.jsonl")
    before = tree(tmp_path)
    second = run_retrieve(tmp_path, config)
    assert second.answer["status"] == "ok"
    for name in (SERVER, READER):
        assert [c for c in lookups_of(second, name) if c["family"] == V4], f"{name} not looked up again"
    allowed = {"entry.py", "two_requests.py", "outside.py", "third_party.py", "km_fake_prelude.py", ".env", "home",
               "request.json", "resolver.jsonl", "resolver_first.jsonl", "driver.jsonl", "start.jsonl"}
    stray = [p for p in tree(tmp_path) if p.split("/")[0] not in allowed and not p.startswith("__pycache__")]
    assert stray == [], f"files written beyond the test's own: {stray}"
    new = [p for p in tree(tmp_path) if p not in before and not p.startswith("__pycache__")]
    assert new == ["resolver.jsonl"], f"the second run left new files: {new}"


def test_km_400d_4_i_ipv4_first_is_reachable_through_the_retrieve_cli(tmp_path):
    # covers: KM-400d-4-i
    # angle: reachability
    """Through the real CLI the first recorded lookup of the server name is IPv4-only; exit 0, status ok."""
    run = run_retrieve(tmp_path, fake(**STALLED_IPV6))
    assert run.returncode == 0
    assert run.answer["status"] == "ok"
    assert support.server_lookups(run)[0]["family"] == V4
