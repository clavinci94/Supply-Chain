"""Local smoke test — equivalent to `supplychainbench test-bundle .`.

Run from the bundle root:

    pytest tests/test_local.py -v

This loads the bundle through the validator and runs a 5-tick smoke
simulation on `intro_step_demand`. If this passes, your bundle is
structurally valid and will be accepted by the instructor's evaluator.
It does *not* tell you whether your policy is good — only whether it
is admissible.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from supplychainbench.sdk.validator import ValidationError, validate_bundle

BUNDLE_ROOT = Path(__file__).resolve().parent.parent


def test_bundle_validates() -> None:
    try:
        report = validate_bundle(BUNDLE_ROOT, smoke_ticks=5)
    except ValidationError as e:
        pytest.fail(f"bundle validation failed [{e.code}]: {e}")
    assert report.smoke_run_ok, f"smoke run did not complete: {report.smoke_error}"
