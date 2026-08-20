"""Shared fixtures for Zapier Webhook PST (Plausible Scenario Testing).

Mirrors Make.com Connector's tests/conftest.py: imperal_sdk.testing.MockContext
+ MockSecretStore give us the REAL handlers.py code path (real HTTP call
construction, real secret storage, real header-comparison logic) against a
controlled fake HTTP backend -- not a re-implementation of the logic under a
different name.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def ctx():
    from imperal_sdk.testing import MockContext, MockSecretStore

    mock = MockContext()
    mock.secrets = MockSecretStore({})
    return mock


@pytest.fixture
def ctx_outgoing_configured(ctx):
    """Same as `ctx` but with an outgoing Catch Hook URL already saved."""
    from imperal_sdk.testing import MockSecretStore
    ctx.secrets = MockSecretStore({
        "zapier_outgoing_webhook_url": "https://hooks.zapier.com/hooks/catch/12345/abcde/",
    })
    return ctx


@pytest.fixture
def ctx_inbound_configured(ctx):
    """Same as `ctx` but with an inbound shared secret already generated."""
    from imperal_sdk.testing import MockSecretStore
    ctx.secrets = MockSecretStore({
        "zapier_inbound_shared_secret": "test-shared-secret-9f21ab",
    })
    return ctx


@pytest.fixture
def ctx_both_configured(ctx):
    """Both directions configured at once -- the account owner's steady state."""
    from imperal_sdk.testing import MockSecretStore
    ctx.secrets = MockSecretStore({
        "zapier_outgoing_webhook_url": "https://hooks.zapier.com/hooks/catch/12345/abcde/",
        "zapier_inbound_shared_secret": "test-shared-secret-9f21ab",
    })
    return ctx
