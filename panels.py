"""Panel UI -- Zapier Webhook (narrow two-direction bridge, see app.py).

SIDEBAR CONTENT -- NO CARDS ANYWHERE, per ~/UI_INTERFACE_STANDARD.md's
"left sidebar, no decorated cards" rule. Every section is a plain
ui.Stack, separated by ui.Divider().

Per ~/UI_INTERFACE_STANDARD.md (form-container rule, 2026-08-20): every
ui.Form here is full_width so its container is stretched to the entire
sidebar width, and its own children (inputs) are also full_width inside
it. Every input has a visible label (a ui.Text caption above it, never
just a placeholder standing in for one) and a placeholder that reflects
this app's own domain (Zapier URLs / header names), not a generic
example. The "how to" instructions live ONLY in the center-overlay help
dialog (make_connect_help-style) -- never duplicated inline in the
sidebar, per the same standard.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
import handlers as h


def _settings_button() -> ui.UINode:
    return ui.Button(
        "App settings", variant="secondary", size="sm", full_width=True,
        icon="settings", on_click=ui.Call("__panel__zapier_settings"),
    )


def _outgoing_section(configured: bool) -> ui.UINode:
    if configured:
        return ui.Stack(direction="v", gap=1, align="start", children=[
            ui.Text("Outgoing (Imperal -> Zap)", variant="body"),
            ui.Text("A Catch Hook URL is configured.", variant="caption"),
        ])
    return ui.Stack(direction="v", gap=1, align="start", children=[
        ui.Text("Outgoing (Imperal -> Zap)", variant="body"),
        ui.Text("Not configured -- add it in App settings.", variant="caption"),
    ])


def _inbound_section(configured: bool, inbound_url: str) -> ui.UINode:
    if not configured:
        return ui.Stack(direction="v", gap=1, align="start", children=[
            ui.Text("Incoming (Zap -> Imperal)", variant="body"),
            ui.Text("Not configured -- add it in App settings.", variant="caption"),
        ])
    return ui.Stack(direction="v", gap=1, align="start", children=[
        ui.Text("Incoming (Zap -> Imperal)", variant="body"),
        ui.Text(inbound_url, variant="caption", copyable=True),
    ])


@ext.panel("zapier_connect", slot="left", title="Zapier Webhook", icon="⚡",
           default_width=320, min_width=260, max_width=420)
async def zapier_connect_panel(ctx, **kwargs) -> object:
    out_status = await h._get_outgoing_status(ctx)
    in_status = await h._get_inbound_status(ctx)

    header = ui.Header(
        text="Zapier Webhook", level=2,
        subtitle="Two-way webhook bridge between Imperal and your Zaps",
    )

    children: list[ui.UINode] = [
        header,
        _outgoing_section(out_status.configured),
        ui.Divider(),
        _inbound_section(in_status.configured, in_status.webhook_url),
        ui.Divider(),
        ui.Button(
            "How this works", variant="ghost", size="sm", full_width=True,
            icon="help-circle", on_click=ui.Call("__panel__zapier_connect_help"),
        ),
        _settings_button(),
    ]
    return ui.Stack(direction="v", gap=4, align="stretch", children=children)


@ext.panel("zapier_connect_help", slot="center", title="How Zapier Webhook works",
           center_overlay=True)
async def zapier_connect_help(ctx, **kwargs) -> object:
    content = ui.Stack(direction="v", gap=3, children=[
        ui.Text("Why this app is narrower than Make.com/n8n:", variant="heading"),
        ui.Text(
            "Zapier has no public API to list or manage your existing Zaps "
            "without Imperal first publishing inside Zapier's own app "
            "catalog and passing their review. This app instead bridges two "
            "'Webhooks by Zapier' steps you add yourself inside a Zap.",
        ),
        ui.Divider(),
        ui.Text("Outgoing -- to trigger a Zap from Imperal:", variant="heading"),
        ui.Text("1. In Zapier, start a Zap and choose 'Webhooks by Zapier' -> 'Catch Hook' as the trigger."),
        ui.Text("2. Copy the URL Zapier gives you."),
        ui.Text("3. Paste it into 'Outgoing webhook URL' in App settings here."),
        ui.Divider(),
        ui.Text("Incoming -- to let a Zap notify Imperal:", variant="heading"),
        ui.Text("1. In a Zap, add 'Webhooks by Zapier' -> 'POST' as an action step."),
        ui.Text("2. Set its URL to the 'Incoming webhook URL' shown in App settings here."),
        ui.Text("3. Add a custom header with the name and value shown there, so Imperal can verify the request came from your Zap."),
        ui.Divider(),
        ui.Link(
            label="Open Zapier's Webhooks by Zapier documentation",
            href="https://help.zapier.com/hc/en-us/articles/44391646192397-Ways-to-make-API-requests-in-Zapier",
        ),
    ])
    return ui.Dialog(
        title="How Zapier Webhook works",
        content=content,
        confirm_label="",
        cancel_label="Close",
    )


@ext.panel("zapier_center", slot="center", title="Zapier Webhook", icon="⚡", center_overlay=True)
async def zapier_center_panel(ctx, **kwargs) -> object:
    """Base center panel -- per UI_INTERFACE_STANDARD.md (2026-08-20).
    This app has no list/detail content of its own to show in the center
    by default (everything lives in the sidebar). MUST carry
    center_overlay=True: per docs.imperal.io/en/concepts/panels, a plain
    slot="center" panel is registered but the Panel app never fetches it
    at session-init without that flag -- the center slot stays genuinely
    empty (not a caching issue) until center_overlay=True is set. Text is
    the shared canonical wording -- must stay identical across every app
    in this situation, not app-specific."""
    return ui.Empty(
        message="Nothing to show here -- this app is managed entirely from the sidebar.",
        icon="👈",
    )
