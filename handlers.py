"""All chat functions and the inbound webhook receiver for Zapier Webhook.

Two independent slices, per app.py's reasoning:
  - Срез 1: outgoing webhook Imperal -> Zapier (mirrors Make.com Connector's
    set_outgoing_webhook / send_webhook_event exactly).
  - Срез 2: incoming webhook Zapier -> Imperal (@ext.webhook receiver +
    config/regenerate/list chat functions around it).
"""
from __future__ import annotations

import secrets as _secrets_mod
import time
import hmac

from app import ext, chat
import zapier_client as zc
from schemas import (
    NoParams,
    SetOutgoingWebhookParams,
    OutgoingWebhookStatus,
    SendWebhookEventParams,
    WebhookDeliveryResult,
    InboundWebhookConfig,
    RegenerateInboundSecretParams,
    InboundEventSummary,
    InboundEventList,
)

try:
    from imperal_sdk import ActionResult
except Exception:  # pragma: no cover
    ActionResult = None  # type: ignore

_OUTGOING_SECRET_NAME = "zapier_outgoing_webhook_url"
_INBOUND_SECRET_NAME = "zapier_inbound_shared_secret"
_INBOUND_HEADER_NAME = "X-Zapier-Webhook-Secret"

_INBOUND_EVENTS_COLLECTION = "zapier_inbound_events"
#: Keep the rolling log small -- this is a lightweight two-way bridge, not
#: an audit system. Oldest events are pruned past this cap.
_INBOUND_EVENTS_MAX = 50

_INBOUND_WEBHOOK_PATH = "/inbound"


def _build_inbound_url(ctx) -> str:
    """Public URL the user pastes into a Zapier 'Webhooks by Zapier' POST
    action step. Built the same way as the platform's own OAuth callback
    URLs (per decorators-reference.md): https://panel.imperal.io/v1/ext/
    <app_id>/webhook<path>.
    """
    app_id = getattr(ext, "app_id", None) or getattr(ext, "name", "zapier-webhook")
    return f"https://panel.imperal.io/v1/ext/{app_id}/webhook{_INBOUND_WEBHOOK_PATH}"


async def _get_outgoing_status(ctx) -> OutgoingWebhookStatus:
    """Plain-data helper for panels.py -- mirrors Make.com Connector's
    h._get_credentials pattern (no ActionResult wrapping; panels read
    state directly, chat functions wrap the same reads for the LLM)."""
    url = await ctx.secrets.get(_OUTGOING_SECRET_NAME)
    configured = bool(url)
    return OutgoingWebhookStatus(
        configured=configured,
        detail="Configured" if configured else "Not configured",
    )


async def _get_inbound_status(ctx) -> InboundWebhookConfig:
    secret = await ctx.secrets.get(_INBOUND_SECRET_NAME)
    return InboundWebhookConfig(
        configured=bool(secret),
        webhook_url=_build_inbound_url(ctx),
        detail=(
            "Ready to receive events" if secret
            else "Generate a shared secret first (regenerate_inbound_secret)"
        ),
    )


# ──────────────────────────────────────────────────────────────────────────
# Срез 1: outgoing webhook Imperal -> Zapier.
# ──────────────────────────────────────────────────────────────────────────

@chat.function(
    "set_outgoing_webhook",
    "Save (or clear, with an empty webhook_url) the Zapier 'Catch Hook' "
    "trigger URL that send_webhook_event will POST to. Get this URL by "
    "adding a 'Webhooks by Zapier' trigger step ('Catch Hook') as the "
    "first step of a Zap and copying its URL.",
    action_type="write",
    chain_callable=True,
    data_model=OutgoingWebhookStatus,
    event="zapier-webhook.set_outgoing_webhook",
    effects=["zapier.outgoing_webhook.configured"],
)
async def set_outgoing_webhook(ctx, params: SetOutgoingWebhookParams) -> "ActionResult":
    """The URL itself is the credential (Zapier authenticates by knowing
    it, not via a header), so it lives in ctx.secrets -- same tier as the
    inbound shared secret, not a non-sensitive store marker."""
    url = params.webhook_url.strip()
    if not url:
        await ctx.secrets.delete(_OUTGOING_SECRET_NAME)
        return ActionResult.success(
            OutgoingWebhookStatus(configured=False, detail="No webhook configured"),
            summary="Outgoing Zapier webhook cleared.",
            refresh_panels=["zapier_center", "zapier_settings"],
        )
    if not (url.startswith("https://") or url.startswith("http://")):
        return ActionResult.error(
            "That doesn't look like a URL. Paste the 'Catch Hook' trigger "
            "URL from Zapier (add a 'Webhooks by Zapier' trigger step to "
            "a Zap and copy its URL)."
        )
    await ctx.secrets.set(_OUTGOING_SECRET_NAME, url)
    return ActionResult.success(
        OutgoingWebhookStatus(configured=True, detail="Saved"),
        summary="Outgoing Zapier webhook saved.",
        refresh_panels=["zapier_center", "zapier_settings"],
    )


@chat.function(
    "get_outgoing_webhook_status",
    "Check whether an outgoing Zapier webhook URL is configured (does not reveal the URL).",
    action_type="read",
    chain_callable=True,
    data_model=OutgoingWebhookStatus,
)
async def get_outgoing_webhook_status(ctx, params: NoParams) -> "ActionResult":
    """Read-only check of whether the outgoing Zapier webhook is set."""
    url = await ctx.secrets.get(_OUTGOING_SECRET_NAME)
    configured = bool(url)
    return ActionResult.success(
        OutgoingWebhookStatus(
            configured=configured,
            detail="Configured" if configured else "Not configured",
        )
    )


@chat.function(
    "send_webhook_event",
    "Send an event payload to the configured Zapier Catch Hook webhook "
    "right now -- for other Imperal apps/automations to trigger a Zap. "
    "Run set_outgoing_webhook first if you haven't configured one yet.",
    action_type="write",
    chain_callable=True,
    data_model=WebhookDeliveryResult,
    event="zapier-webhook.send_webhook_event",
    effects=["zapier.webhook.sent"],
)
async def send_webhook_event(ctx, params: SendWebhookEventParams) -> "ActionResult":
    """POST params.payload to the saved Zapier Catch Hook URL right now."""
    url = await ctx.secrets.get(_OUTGOING_SECRET_NAME)
    if not url:
        return ActionResult.error(
            "No outgoing Zapier webhook configured yet. Run "
            "set_outgoing_webhook with your Zap's Catch Hook URL first."
        )
    delivered, status_code, detail = await zc.post_webhook(ctx, url, params.payload)
    result = WebhookDeliveryResult(delivered=delivered, status_code=status_code, detail=detail)
    if delivered:
        return ActionResult.success(result, summary=f"Event delivered (HTTP {status_code}).")
    return ActionResult.error(f"Delivery failed: {detail}")


# ──────────────────────────────────────────────────────────────────────────
# Срез 2: incoming webhook Zapier -> Imperal.
# ──────────────────────────────────────────────────────────────────────────

@chat.function(
    "get_inbound_webhook_config",
    "Read the inbound webhook URL and whether a shared secret is set up "
    "for receiving events FROM a Zap (via a 'Webhooks by Zapier' POST "
    "action step). Never reveals the secret itself.",
    action_type="read",
    chain_callable=True,
    data_model=InboundWebhookConfig,
)
async def get_inbound_webhook_config(ctx, params: NoParams) -> "ActionResult":
    """Read-only status of the inbound (Zap -> Imperal) webhook setup."""
    secret = await ctx.secrets.get(_INBOUND_SECRET_NAME)
    return ActionResult.success(
        InboundWebhookConfig(
            configured=bool(secret),
            webhook_url=_build_inbound_url(ctx),
            detail=(
                "Ready to receive events" if secret
                else "Generate a shared secret first (regenerate_inbound_secret)"
            ),
        )
    )


@chat.function(
    "regenerate_inbound_secret",
    "Generate a fresh shared secret for the inbound direction (Zapier -> "
    "Imperal), discarding any previous one. Paste the new value into a "
    "custom header named X-Zapier-Webhook-Secret on a 'Webhooks by "
    "Zapier' POST action step in your Zap.",
    action_type="write",
    chain_callable=True,
    data_model=InboundWebhookConfig,
    event="zapier-webhook.regenerate_inbound_secret",
    effects=["zapier.inbound_secret.rotated"],
)
async def regenerate_inbound_secret(ctx, params: RegenerateInboundSecretParams) -> "ActionResult":
    """Rotate the inbound shared secret; the old one stops being accepted immediately."""
    new_secret = _secrets_mod.token_urlsafe(32)
    await ctx.secrets.set(_INBOUND_SECRET_NAME, new_secret)
    return ActionResult.success(
        InboundWebhookConfig(
            configured=True,
            webhook_url=_build_inbound_url(ctx),
            detail=new_secret,  # surfaced once, in the write response, so the user can copy it
        ),
        summary="New inbound shared secret generated -- copy it now, it won't be shown again.",
        refresh_panels=["zapier_center", "zapier_settings"],
    )


@chat.function(
    "list_inbound_events",
    "List the most recent events a Zap has POSTed into this app via the "
    "inbound webhook, newest first.",
    action_type="read",
    chain_callable=True,
    data_model=InboundEventList,
)
async def list_inbound_events(ctx, params: NoParams) -> "ActionResult":
    """List the most recent events received via the inbound webhook, newest first."""
    page = await ctx.store.query(
        _INBOUND_EVENTS_COLLECTION, order_by="-received_at", limit=_INBOUND_EVENTS_MAX,
    )
    items = getattr(page, "items", None) or []
    events = [
        InboundEventSummary(
            id=str(getattr(doc, "id", getattr(doc, "doc_id", ""))),
            received_at=(doc.data or {}).get("received_at", "") if hasattr(doc, "data") else doc.get("received_at", ""),
            payload_preview=(doc.data or {}).get("payload_preview", "") if hasattr(doc, "data") else doc.get("payload_preview", ""),
        )
        for doc in items
    ]
    return ActionResult.success(InboundEventList(events=events, total=len(events)))


# ──────────────────────────────────────────────────────────────────────────
# Inbound webhook receiver -- runs with NO user in context
# (ctx.user.imperal_id == "__webhook__"), reachable by anyone who knows
# the URL. Verification is a plain shared-secret header comparison via
# hmac.compare_digest (constant-time, per Slack Connector's own inbound.py
# precedent) -- Zapier's "Webhooks by Zapier" action step has no HMAC
# signing of its own to verify against, unlike Slack's signed events, so
# a shared secret in a custom header is the correct minimum here.
# ──────────────────────────────────────────────────────────────────────────

@ext.webhook(_INBOUND_WEBHOOK_PATH, method="POST")
async def receive_zapier_webhook(ctx, headers: dict, body: str, query_params: dict):
    expected_secret = await ctx.secrets.get(_INBOUND_SECRET_NAME)
    if not expected_secret:
        return {"error": "Inbound webhook not configured yet"}

    # Header lookup is case-insensitive per HTTP semantics -- normalise
    # once rather than trust the exact casing Zapier happens to send.
    got_secret = ""
    lowered = {k.lower(): v for k, v in (headers or {}).items()}
    got_secret = lowered.get(_INBOUND_HEADER_NAME.lower(), "")

    if not hmac.compare_digest(got_secret, expected_secret):
        return {"error": "Invalid or missing shared secret"}

    preview = (body or "")[:500]
    await ctx.store.create(
        _INBOUND_EVENTS_COLLECTION,
        {
            "received_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "payload_preview": preview,
        },
    )

    # Prune past the cap so this collection cannot grow without bound --
    # same reasoning as Slack Connector's event ledger TTL, simplified to
    # a count-based cap since this app has no replay-window requirement.
    page = await ctx.store.query(
        _INBOUND_EVENTS_COLLECTION, order_by="-received_at", limit=1000,
    )
    items = getattr(page, "items", None) or []
    if len(items) > _INBOUND_EVENTS_MAX:
        for doc in items[_INBOUND_EVENTS_MAX:]:
            doc_id = getattr(doc, "id", None) or getattr(doc, "doc_id", None)
            if doc_id:
                await ctx.store.delete(_INBOUND_EVENTS_COLLECTION, doc_id)

    return {"ok": True}
