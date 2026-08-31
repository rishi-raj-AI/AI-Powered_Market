"""Shared test fixtures.

The suite runs against a real PostGIS database that persists between tests, so
anything a factory creates has to be removed again — otherwise a factory store
shows up in another test's public store listing and fails it.
"""

from __future__ import annotations

import pytest

from tests import factories


@pytest.fixture(autouse=True)
def _cleanup_factory_rows():
    """Remove every row the factories created during a test."""
    factories.reset_tracking()
    try:
        yield
    finally:
        factories.cleanup_tracked()
