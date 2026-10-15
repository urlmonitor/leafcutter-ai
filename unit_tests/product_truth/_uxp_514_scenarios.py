"""
MODULE: _uxp_514_scenarios
GOAL: Named, memoised drift scenarios (one real CLI run each) shared by the
    umbrella UXP-514 tests and the UXP-514-1..6 child tests.
BUSINESS CONTEXT: A validator run over the bounded store costs seconds; the
    umbrella and its children prove the same behaviour from two directions, so
    each scenario runs once per process and both files assert on its result.
ARCHITECTURE: Builds on _uxp_514_harness (real store copy, real serializers,
    real CLI subprocess). Returns plain dicts: {"proc": CompletedProcess, ...facts
    about what was edited}. No assertions here.
"""
from __future__ import annotations

import copy

from unit_tests.product_truth import _uxp_514_harness as h
from unit_tests.product_truth._uxp_300_store import write_json

_FACTS: dict[str, dict] = {}


def _memo(key: str, build) -> dict:
    if key not in _FACTS:
        facts: dict = {}
        store = h.new_store()
        build(store, facts)
        facts["proc"] = h.run_validator(store)
        facts["store"] = store
        _FACTS[key] = facts
    return _FACTS[key]


# ------------------------------------------------------------------ D1
def d1_flipped_status() -> dict:
    def build(store, facts):
        path, flow, step = h.first_plain_step(store)
        facts.update(flow_id=flow["id"], node_id=step["id"], stored=step["impl_status"])
        step["impl_status"] = "done" if step["impl_status"] != "done" else "not_started"
        facts["new_value"] = step["impl_status"]
        write_json(path, flow)
    return _memo("d1_flip", build)


def d1_extra_step() -> dict:
    def build(store, facts):
        path, flow, step = h.first_plain_step(store)
        extra = copy.deepcopy(step)
        extra["id"] = step["id"] + "-uxp514-extra"
        extra["order"] = max(s.get("order", 0) for s in flow["steps"]) + 1
        flow["steps"].append(extra)
        write_json(path, flow)
    return _memo("d1_extra", build)


# ------------------------------------------------------------------ D2
def _pick_ac(store):
    return h.acs_with_product_truth(store)[0]


def d2_stale_back_reference() -> dict:
    def build(store, facts):
        path, record = _pick_ac(store)
        facts.update(ac_id=record["id"], inverted_node=record["product_truth"][0]["node"], held_node="stale-node-uxp514")
        h.edit_ac(path, lambda rec: rec["product_truth"][0].__setitem__("node", facts["held_node"]))
    return _memo("d2_stale", build)


def d2_missing_back_reference() -> dict:
    def build(store, facts):
        path, record = _pick_ac(store)
        facts.update(ac_id=record["id"])
        h.edit_ac(path, lambda rec: rec.pop("product_truth"))
    return _memo("d2_missing", build)


def d2_orphan_back_reference() -> dict:
    """A new AC (a real AC record re-serialised under a fresh id) carrying a block no journey step references."""
    def build(store, facts):
        path, record = h.acs_with_product_truth(store)[0]
        orphan = dict(record)
        orphan["id"] = "UXP-514-9"
        orphan["product_truth"] = [dict(entry) for entry in record["product_truth"]]
        facts["ac_id"] = orphan["id"]
        (path.parent / "UXP-514-9.yaml").write_text(
            h.yaml.safe_dump(orphan, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return _memo("d2_orphan", build)


# ------------------------------------------------------------------ D3
LOOKUPS = ("by_component", "by_entity", "by_flow", "by_ac")


def d3_edited_lookup(key: str) -> dict:
    def build(store, facts):
        def edit(index):
            entry = sorted(index[key])[0]
            facts.update(lookup=key, entry=entry)
            index[key][entry] = {"edited": "uxp514"} if isinstance(index[key][entry], dict) else []
        h.edit_index(store, edit)
    return _memo(f"d3_{key}", build)


def d3_regenerated_with_extra_flow() -> dict:
    """Real producer -> real consumer: add a journey, let the real generator index it, then validate."""
    def build(store, facts):
        src = h.flow_path(store, "fern-and-fig/track-an-order")
        flow = h.load_json(src)
        flow["id"] = "fern-and-fig/track-an-order-uxp514"
        flow["name"] = "track an order uxp514"
        write_json(src.with_name("track-an-order-uxp514.flow.json"), flow)
        gen = h.run_generator(store)
        facts["generator_returncode"] = gen.returncode
        facts["generator_output"] = h.output(gen)[-600:]
        facts["index"] = h.load_json(store / "index.json")
    return _memo("d3_extra_flow", build)


def d3_regenerated_baseline() -> dict:
    def build(store, facts):
        gen = h.run_generator(store)
        facts["generator_returncode"] = gen.returncode
        facts["index"] = h.load_json(store / "index.json")
    return _memo("d3_regen_baseline", build)


def lookup_entry_total(index: dict) -> int:
    return sum(len(index[key]) for key in LOOKUPS)


# ------------------------------------------------------------------ D4
BOGUS_SCREEN = "no-such-screen-uxp514"


def _flow_ids_by_readiness(store):
    draft, approved = [], []
    for path in h.flow_files(store):
        flow = h.load_json(path)
        if flow.get("steps"):
            (approved if flow.get("readiness") == "approved" else draft).append(flow["id"])
    return draft, approved


def _name_screen(store, flow_id, screen):
    path = h.flow_path(store, flow_id)
    flow = h.load_json(path)
    node = flow["steps"][0]
    node["screen"] = screen
    write_json(path, flow)
    return node["id"]


def _regen(store, facts):
    """Screens are part of the derived by_ac / product_truth data, so let the real generator re-derive it."""
    gen = h.run_generator(store)
    facts["generator_returncode"] = gen.returncode
    facts["generator_output"] = h.output(gen)[-500:]


def d4_unregistered_on_draft() -> dict:
    def build(store, facts):
        draft, _ = _flow_ids_by_readiness(store)
        h.set_readiness(store, draft[0], "draft")
        facts.update(flow_id=draft[0], node_id=_name_screen(store, draft[0], BOGUS_SCREEN), screen=BOGUS_SCREEN)
        _regen(store, facts)
    return _memo("d4_draft", build)


def d4_unregistered_on_approved() -> dict:
    def build(store, facts):
        draft, _ = _flow_ids_by_readiness(store)
        h.set_readiness(store, draft[0], "approved")
        facts.update(flow_id=draft[0], node_id=_name_screen(store, draft[0], BOGUS_SCREEN), screen=BOGUS_SCREEN)
        _regen(store, facts)
    return _memo("d4_approved", build)


def d4_registered_in_both_states_with_a_control() -> dict:
    """Registered screen on a draft AND an approved journey; a third, draft journey keeps the control unregistered."""
    def build(store, facts):
        draft, _ = _flow_ids_by_readiness(store)
        registered = h.registered_screens(store)[0]
        h.set_readiness(store, draft[0], "draft")
        h.set_readiness(store, draft[1], "approved")
        h.set_readiness(store, draft[2], "draft")
        facts.update(registered=registered, draft_flow=draft[0], approved_flow=draft[1], control_flow=draft[2])
        _name_screen(store, draft[0], registered)
        _name_screen(store, draft[1], registered)
        facts["control_node"] = _name_screen(store, draft[2], BOGUS_SCREEN)
        _regen(store, facts)
    return _memo("d4_registered", build)


# ------------------------------------------------------------------ D6
def d6_synced_store() -> dict:
    def build(store, facts):
        h.sync_copied_scalar_fields(store)
    return _memo("d6_synced", build)


def d6_summary_differs() -> dict:
    def build(store, facts):
        h.sync_copied_scalar_fields(store)

        def edit(index):
            art = next(a for a in index["artifacts"] if a["type"] == "flow")
            facts.update(artifact_id=art["id"], index_text="index copy EDITED uxp514",
                         source_text=h.load_json(store / art["path"])["summary"])
            art["summary"] = facts["index_text"]
        h.edit_index(store, edit)
    return _memo("d6_summary", build)


D6_FIELDS = ("summary", "kind", "source", "component")


def d6_every_field_edited() -> dict:
    """One distinct flow artifact per copied scalar field, each field altered in the index only."""
    def build(store, facts):
        h.sync_copied_scalar_fields(store)
        facts["edits"] = {}

        def edit(index):
            flows = [a for a in index["artifacts"] if a["type"] == "flow"]
            for art, field in zip(flows, D6_FIELDS):
                source_value = h.load_json(store / art["path"])[field]
                art[field] = f"{source_value}-EDITED-uxp514"
                facts["edits"][field] = (art["id"], art[field], source_value)
        h.edit_index(store, edit)
    return _memo("d6_fields", build)


def d6_extra_artifact() -> dict:
    def build(store, facts):
        src = h.flow_path(store, "fern-and-fig/track-an-order")
        flow = h.load_json(src)
        flow["id"] = "fern-and-fig/track-an-order-uxp514"
        flow["name"] = "track an order uxp514"
        write_json(src.with_name("track-an-order-uxp514.flow.json"), flow)
        facts["generator_returncode"] = h.run_generator(store).returncode
        h.sync_copied_scalar_fields(store)
    return _memo("d6_extra", build)
