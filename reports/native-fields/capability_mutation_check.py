"""Reproduce process-local Capability test mutation evidence from the repository root."""

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from knowledge.native_types import capability as module

spec = importlib.util.spec_from_file_location(
    "capability_tests", "tests/knowledge/test_native_capability.py"
)
tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tests)
original = module.extract
module._validator()
proofs = []


def invoke(name, values, mutation=None):
    with TemporaryDirectory(prefix="leafcutter-capability-proof-") as temp:
        with pytest.MonkeyPatch.context() as patch:
            if mutation is not None:
                mutation(patch)
            args = (
                []
                if name == "test_capability_real_registry_exact_fields_and_no_defaults"
                else [Path(temp)]
            )
            if name in {
                "test_capability_resolved_source_cannot_escape_snapshot",
                "test_capability_metadata_and_context_are_independent_copies",
            }:
                args.append(patch)
            getattr(tests, name)(*args, *values)


def prove(name, alteration, mutation, values=()):
    try:
        invoke(name, values, mutation)
    except (AssertionError, ValueError, pytest.fail.Exception) as error:
        invoke(name, values)
        proofs.append(
            {
                "test": name,
                "input": list(values),
                "alteration": alteration,
                "mutant": "caught",
                "failure_type": type(error).__name__,
                "restored": "green",
            }
        )
    else:
        raise AssertionError("Inert mutation: " + name + " " + alteration)


def wrap(transform):
    return lambda patch: patch.setattr(
        module, "extract", lambda root: transform(original(root))
    )


def silence(patch):
    def extract(root):
        try:
            return original(root)
        except ValueError:
            return []

    patch.setattr(module, "extract", extract)


prove(
    "test_capability_all_fields_and_nested_extensions_round_trip",
    "drop the future nested extension field",
    wrap(
        lambda records: [
            replace(r, metadata={k: v for k, v in r.metadata.items() if k != "future"})
            for r in records
        ]
    ),
)
prove(
    "test_capability_all_fields_and_nested_extensions_round_trip",
    "replace root registry context with entry metadata",
    wrap(
        lambda records: [
            replace(r, derived={"registry_context": r.metadata}) for r in records
        ]
    ),
)
prove(
    "test_capability_all_fields_and_nested_extensions_round_trip",
    "filter disabled authored capabilities as a runtime adapter might",
    wrap(lambda records: [r for r in records if r.metadata.get("enabled", True)]),
)
prove(
    "test_capability_real_registry_exact_fields_and_no_defaults",
    "insert runtime enabled=True into authored metadata",
    wrap(
        lambda records: [
            replace(r, metadata={**r.metadata, "enabled": True}) for r in records
        ]
    ),
)
prove(
    "test_capability_legacy_admission_does_not_read_references",
    "inject inferred components into legacy source",
    wrap(
        lambda records: [
            replace(r, metadata={**r.metadata, "components": ["inferred"]})
            for r in records
        ]
    ),
)
prove(
    "test_capability_source_order_and_changed_values_are_visible",
    "sort records by identity instead of preserving source order",
    wrap(lambda records: sorted(records, key=lambda r: r.native_id)),
)
prove(
    "test_capability_absent_and_empty_registry_do_not_invent_records",
    "manufacture a Capability record from a legacy agent",
    lambda patch: patch.setattr(module, "extract", lambda root: ["invented"]),
)
for contents in [
    "{",
    "[]",
    "{}",
    '{"registry_id":"x","registry_version":1,"capabilities":{}}',
]:
    prove(
        "test_capability_malformed_envelope_fails_explicitly",
        "silently discard malformed registry as empty",
        silence,
        (contents,),
    )
for field, value in [
    ("registry_id", ""),
    ("registry_version", 0),
    ("registry_version", True),
]:
    prove(
        "test_capability_invalid_registry_identity_fails",
        "silently discard invalid registry identity",
        silence,
        (field, value),
    )
for field, value in [
    ("id", "Bad Id"),
    ("id", None),
    ("name", ""),
    ("version", "1"),
    ("request_kinds", []),
    ("accepts_schemas", ["unknown"]),
    ("execution_mode", "unknown"),
    ("binding", ""),
    ("enabled", 1),
    ("process_maturity", True),
    ("process_maturity", 5),
    ("cost_hints", {"jev_calls": -1}),
    ("availability", {"status": "unknown"}),
    ("admission", {}),
    (
        "admission",
        {
            "kind": "legacy_admission",
            "decision_ref": "ADR-999",
            "admitted_by": "human",
            "admitted_on": "2026-10-02",
        },
    ),
]:
    prove(
        "test_capability_malformed_entry_fails_explicitly",
        "silently discard malformed present entry",
        silence,
        (field, value),
    )
prove(
    "test_capability_duplicate_ids_fail_without_source_changes",
    "silently discard conflicting identities",
    silence,
)
prove(
    "test_capability_resolved_source_cannot_escape_snapshot",
    "disable resolved source containment",
    lambda patch: patch.setattr(
        module, "relative", lambda root, path: "config/capability_registry.json"
    ),
)
prove(
    "test_capability_metadata_and_context_are_independent_copies",
    "retain mutable aliases to authored metadata and registry context",
    lambda patch: patch.setattr(module, "deepcopy", lambda value: value),
)
Path("reports/native-fields/capability-mutations.json").write_text(
    json.dumps(
        {
            "method": "Process-local mutations of the imported reader; each original test rerun green after restoration. No source files mutated.",
            "module": module.__file__,
            "proofs": proofs,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print(json.dumps({"proof_pairs": len(proofs), "all_caught": True, "all_restored_green": True}))
