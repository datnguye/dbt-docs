"""Shared fixtures for the health rule-engine tests.

The rule registry (``DIMENSION_RULES``) is module-global and mutated by
``register_rule`` / the plugin loaders, so reset it to the built-in baseline
around every test to keep them independent.
"""

import pytest

from dbdocs.extract.health import rules as health_rules


@pytest.fixture(autouse=True)
def _reset_health_rules():
    health_rules.reset_rules()
    yield
    health_rules.reset_rules()
