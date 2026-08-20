"""Plausible Scenario Testing (PST) for Zapier Webhook.

Method: Docs/session-notes/SCENARIO_TESTING_STANDARD.md. Persona used
throughout: the Zapier account owner (PREPARATION.md-equivalent role in
app.py) -- the one person who configures both directions of this bridge:
pastes a Catch Hook URL to send events OUT to a Zap, and generates a
shared secret so a Zap's own "Webhooks by Zapier" POST step can send
events IN. Single functional role; scenario variety comes from DATA
classes (empty/typical/boundary/invalid/exotic states -- never
configured, configured then cleared, wrong secret, missing header,
oversized payload) and the 5 required branches.

Every test calls the REAL handlers.py chat functions (and the REAL
@ext.webhook receiver) with REAL params models, through
imperal_sdk.testing.MockContext -- not a re-implementation of the logic
under a different name.
"""
from __future__ import annotations

import pytest

import handlers as h
from schemas import (
    NoParams,
    SetOutgoingWebhookParams,
    SendWebhookEventParams,
    RegenerateInboundSecretParams,
)


# ──────────────────────────────────────────────────────────────────────────
# Branch 1 -- Empty state (nothing configured yet)
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_outgoing_status_empty_reports_not_configured(ctx):
    result = await h.get_outgoing_webhook_status(ctx, NoParams())
    assert result.status == "success"
    assert result.data.configured is False


@pytest.mark.asyncio
async def test_inbound_config_empty_reports_not_configured(ctx):
    result = await h.get_inbound_webhook_config(ctx, NoParams())
    assert result.status == "success"
    assert result.data.configured is False
    assert result.data.webhook_url  # URL is always derivable, even unconfigured


@pytest.mark.asyncio
async def test_send_webhook_event_with_no_url_configured_errors_cleanly(ctx):
    result = await h.send_webhook_event(ctx, SendWebhookEventParams(payload={"a": 1}))
    assert result.status == "error"
    assert "set_outgoing_webhook" in result.error


@pytest.mark.asyncio
async def test_list_inbound_events_empty_returns_empty_list(ctx):
    result = await h.list_inbound_events(ctx, NoParams())
    assert result.status == "success"
    assert result.data.events == []
    assert result.data.total == 0


# ──────────────────────────────────────────────────────────────────────────
# Branch 2 -- Typical state (the everyday, happy path)
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_outgoing_webhook_then_status_reports_configured(ctx):
    result = await h.set_outgoing_webhook(
        ctx, SetOutgoingWebhookParams(webhook_url="https://hooks.zapier.com/hooks/catch/1/a/")
    )
    assert result.status == "success"
    assert result.data.configured is True

    status = await h.get_outgoing_webhook_status(ctx, NoParams())
    assert status.data.configured is True


@pytest.mark.asyncio
async def test_send_webhook_event_delivers_through_real_http_call(ctx_outgoing_configured):
    ctx_outgoing_configured.http.mock_post(
        "hooks.zapier.com", response={}, status=200,
    )
    result = await h.send_webhook_event(
        ctx_outgoing_configured, SendWebhookEventParams(payload={"order_id": 42})
    )
    assert result.status == "success"
    assert result.data.delivered is True
    assert result.data.status_code == 200


@pytest.mark.asyncio
async def test_regenerate_inbound_secret_then_config_reports_configured(ctx):
    result = await h.regenerate_inbound_secret(ctx, RegenerateInboundSecretParams())
    assert result.status == "success"
    assert result.data.configured is True
    first_secret = result.data.detail
    assert first_secret  # surfaced once in the write response

    config = await h.get_inbound_webhook_config(ctx, NoParams())
    assert config.data.configured is True


@pytest.mark.asyncio
async def test_receive_zapier_webhook_with_correct_secret_is_accepted(ctx_inbound_configured):
    result = await h.receive_zapier_webhook(
        ctx_inbound_configured,
        headers={"X-Zapier-Webhook-Secret": "test-shared-secret-9f21ab"},
        body='{"event": "new_lead", "name": "Jane"}',
        query_params={},
    )
    assert result.get("ok") is True

    events = await h.list_inbound_events(ctx_inbound_configured, NoParams())
    assert events.data.total == 1
    assert "new_lead" in events.data.events[0].payload_preview


# ──────────────────────────────────────────────────────────────────────────
# Branch 3 -- Boundary state (limits: header casing, event cap, empty body)
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_receive_zapier_webhook_header_lookup_is_case_insensitive(ctx_inbound_configured):
    """Zapier's own 'Webhooks by Zapier' step lets the user type the header
    name in any case -- HTTP header names are case-insensitive by spec, so
    the receiver must normalise before comparing."""
    result = await h.receive_zapier_webhook(
        ctx_inbound_configured,
        headers={"x-zapier-webhook-secret": "test-shared-secret-9f21ab"},
        body="{}",
        query_params={},
    )
    assert result.get("ok") is True


@pytest.mark.asyncio
async def test_receive_zapier_webhook_empty_body_is_still_accepted(ctx_inbound_configured):
    """An empty POST body is a plausible real event (some Zap steps send no
    body at all) -- it must not crash the receiver, just record an empty
    preview."""
    result = await h.receive_zapier_webhook(
        ctx_inbound_configured,
        headers={"X-Zapier-Webhook-Secret": "test-shared-secret-9f21ab"},
        body="",
        query_params={},
    )
    assert result.get("ok") is True


@pytest.mark.asyncio
async def test_receive_zapier_webhook_oversized_body_is_truncated_to_preview(ctx_inbound_configured):
    huge_body = "x" * 5000
    result = await h.receive_zapier_webhook(
        ctx_inbound_configured,
        headers={"X-Zapier-Webhook-Secret": "test-shared-secret-9f21ab"},
        body=huge_body,
        query_params={},
    )
    assert result.get("ok") is True
    events = await h.list_inbound_events(ctx_inbound_configured, NoParams())
    assert len(events.data.events[0].payload_preview) <= 500


@pytest.mark.asyncio
async def test_list_inbound_events_caps_at_max_and_prunes_oldest(ctx_inbound_configured):
    """Send 55 events (cap is 50) -- list_inbound_events must never return
    more than the cap, and the receiver's own pruning must not raise."""
    for i in range(55):
        result = await h.receive_zapier_webhook(
            ctx_inbound_configured,
            headers={"X-Zapier-Webhook-Secret": "test-shared-secret-9f21ab"},
            body=f'{{"seq": {i}}}',
            query_params={},
        )
        assert result.get("ok") is True

    events = await h.list_inbound_events(ctx_inbound_configured, NoParams())
    assert events.data.total <= 50


# ──────────────────────────────────────────────────────────────────────────
# Branch 4 -- Invalid state (wrong secret, missing header, not configured)
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_receive_zapier_webhook_wrong_secret_is_rejected(ctx_inbound_configured):
    result = await h.receive_zapier_webhook(
        ctx_inbound_configured,
        headers={"X-Zapier-Webhook-Secret": "totally-wrong-guess"},
        body="{}",
        query_params={},
    )
    assert "error" in result
    events = await h.list_inbound_events(ctx_inbound_configured, NoParams())
    assert events.data.total == 0  # rejected delivery is never stored


@pytest.mark.asyncio
async def test_receive_zapier_webhook_missing_header_is_rejected(ctx_inbound_configured):
    result = await h.receive_zapier_webhook(
        ctx_inbound_configured, headers={}, body="{}", query_params={},
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_receive_zapier_webhook_not_configured_at_all_is_rejected(ctx):
    """Before regenerate_inbound_secret has ever been called, ANY delivery
    must be rejected -- there is no secret to compare against, and this
    must not be mistaken for 'accept everything'."""
    result = await h.receive_zapier_webhook(
        ctx, headers={"X-Zapier-Webhook-Secret": "anything"}, body="{}", query_params={},
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_send_webhook_event_network_failure_not_raised_as_exception(ctx_outgoing_configured):
    """A DNS/timeout/connection-refused failure against the user's own Zap
    is an expected, reportable outcome -- not an unhandled exception that
    would surface as a raw 500 to the chat."""
    class _BoomHTTP:
        async def post(self, *a, **kw):
            raise ConnectionError("Could not resolve host")

    ctx_outgoing_configured.http = _BoomHTTP()
    result = await h.send_webhook_event(
        ctx_outgoing_configured, SendWebhookEventParams(payload={"x": 1})
    )
    assert result.status == "error"
    assert "Delivery failed" in result.error


@pytest.mark.asyncio
async def test_send_webhook_event_non_2xx_status_is_reported_as_failure(ctx_outgoing_configured):
    ctx_outgoing_configured.http.mock_post("hooks.zapier.com", response={}, status=410)
    result = await h.send_webhook_event(
        ctx_outgoing_configured, SendWebhookEventParams(payload={"x": 1})
    )
    assert result.status == "error"
    assert "410" in result.error


# ──────────────────────────────────────────────────────────────────────────
# Branch 5 -- Exotic / adversarial (soap-opera sequences, clearing, replay)
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_clear_outgoing_webhook_with_empty_url(ctx_outgoing_configured):
    """set_outgoing_webhook with an empty URL clears it -- documented
    behaviour in the function's own docstring, must actually work."""
    result = await h.set_outgoing_webhook(ctx_outgoing_configured, SetOutgoingWebhookParams(webhook_url=""))
    assert result.status == "success"
    assert result.data.configured is False

    status = await h.get_outgoing_webhook_status(ctx_outgoing_configured, NoParams())
    assert status.data.configured is False


@pytest.mark.asyncio
async def test_regenerate_inbound_secret_twice_old_secret_stops_working(ctx_inbound_configured):
    """D2 Idempotency / soap-opera: regenerate the secret while an old one
    is already saved -- the OLD secret must stop being accepted immediately
    after rotation (the whole point of 'regenerate')."""
    old_secret = "test-shared-secret-9f21ab"

    # Old secret still works before rotation.
    pre = await h.receive_zapier_webhook(
        ctx_inbound_configured,
        headers={"X-Zapier-Webhook-Secret": old_secret}, body="{}", query_params={},
    )
    assert pre.get("ok") is True

    await h.regenerate_inbound_secret(ctx_inbound_configured, RegenerateInboundSecretParams())

    # Old secret must now be rejected.
    post = await h.receive_zapier_webhook(
        ctx_inbound_configured,
        headers={"X-Zapier-Webhook-Secret": old_secret}, body="{}", query_params={},
    )
    assert "error" in post


@pytest.mark.asyncio
async def test_set_outgoing_webhook_called_twice_second_call_overwrites_cleanly(ctx):
    """D2 Idempotency: saving a new URL over an existing one must fully
    replace it, not append/merge -- a double-click or a corrected paste
    must leave exactly one URL in effect."""
    await h.set_outgoing_webhook(ctx, SetOutgoingWebhookParams(webhook_url="https://hooks.zapier.com/hooks/catch/1/a/"))
    result = await h.set_outgoing_webhook(ctx, SetOutgoingWebhookParams(webhook_url="https://hooks.zapier.com/hooks/catch/2/b/"))
    assert result.status == "success"
    assert result.data.configured is True

    saved = await ctx.secrets.get("zapier_outgoing_webhook_url")
    assert saved == "https://hooks.zapier.com/hooks/catch/2/b/"


@pytest.mark.asyncio
async def test_replay_of_same_delivery_is_recorded_twice_not_deduped(ctx_inbound_configured):
    """This app does not attempt delivery-id deduplication (unlike Slack's
    inbound.py) -- a Zap retry after a timeout is expected to create a
    second event, not silently vanish. Documenting the actual behaviour so
    a future change here is a deliberate decision, not an accidental one."""
    body = '{"event": "same_event_replayed"}'
    headers = {"X-Zapier-Webhook-Secret": "test-shared-secret-9f21ab"}
    await h.receive_zapier_webhook(ctx_inbound_configured, headers=headers, body=body, query_params={})
    await h.receive_zapier_webhook(ctx_inbound_configured, headers=headers, body=body, query_params={})

    events = await h.list_inbound_events(ctx_inbound_configured, NoParams())
    assert events.data.total == 2


@pytest.mark.asyncio
async def test_full_lifecycle_configure_use_rotate_clear(ctx):
    """Soap-opera sequence covering the whole owner journey in one run:
    configure both directions, use them, rotate the inbound secret, then
    clear the outgoing URL -- exactly the order a real setup session goes
    in, per app.py's own settings-screen layout."""
    # 1. Configure outgoing.
    await h.set_outgoing_webhook(ctx, SetOutgoingWebhookParams(webhook_url="https://hooks.zapier.com/hooks/catch/9/z/"))
    # 2. Generate inbound secret.
    gen = await h.regenerate_inbound_secret(ctx, RegenerateInboundSecretParams())
    secret = gen.data.detail
    # 3. Receive a real event.
    recv = await h.receive_zapier_webhook(
        ctx, headers={"X-Zapier-Webhook-Secret": secret}, body='{"k": "v"}', query_params={},
    )
    assert recv.get("ok") is True
    # 4. Rotate the secret.
    await h.regenerate_inbound_secret(ctx, RegenerateInboundSecretParams())
    # 5. Old secret now rejected.
    stale = await h.receive_zapier_webhook(
        ctx, headers={"X-Zapier-Webhook-Secret": secret}, body="{}", query_params={},
    )
    assert "error" in stale
    # 6. Clear outgoing.
    cleared = await h.set_outgoing_webhook(ctx, SetOutgoingWebhookParams(webhook_url=""))
    assert cleared.data.configured is False
