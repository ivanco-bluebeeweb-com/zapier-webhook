"""Pydantic models for Zapier Webhook -- narrow two-direction webhook
bridge (see app.py for why this app is intentionally NOT a full
Make.com/n8n-style connector).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class NoParams(BaseModel):
    """Empty params for read-only calls that take no arguments."""
    pass


# ── Outgoing: Imperal -> Zapier (Catch Hook trigger) ───────────────────────

class SetOutgoingWebhookParams(BaseModel):
    webhook_url: str = Field(
        default="",
        description="Zapier 'Catch Hook' trigger URL to POST events to. Empty clears it.",
    )


class OutgoingWebhookStatus(BaseModel):
    configured: bool
    detail: str = ""


class SendWebhookEventParams(BaseModel):
    payload: dict = Field(
        default_factory=dict,
        description="Arbitrary JSON payload to POST to the configured Zapier Catch Hook URL.",
    )


class WebhookDeliveryResult(BaseModel):
    delivered: bool
    status_code: int = 0
    detail: str = ""


# ── Incoming: Zapier -> Imperal (POST action step) ─────────────────────────

class InboundWebhookConfig(BaseModel):
    configured: bool
    webhook_url: str = ""
    detail: str = ""


class RegenerateInboundSecretParams(BaseModel):
    pass


class InboundEventSummary(BaseModel):
    id: str
    received_at: str
    payload_preview: str = ""


class InboundEventList(BaseModel):
    events: list[InboundEventSummary] = Field(default_factory=list)
    total: int = 0
