"""Placeholder done-proof for ACD-300e-1 (user-approved 2026-10-24).

ACD-300e-1 is test_required: false. What it asks for (knowledge-query
declared under `skills:` on product-owner, business-analyst and it-po,
mirrored in the derived `skills_invoked`) is enforced by the build's
skill-reference check and registry_validator, not by a test. The done tools
still demand a covers-tagged test, so this placeholder exists only to let the
record close. It proves nothing and must be removed once the done-proof
remedy for test_required: false records lands.
"""


def test_acd_300e_1_placeholder_until_done_proof_remedy():
    # covers: ACD-300e-1
    # angle: placeholder
    """Placeholder: always passes; see the module docstring."""
    assert True
