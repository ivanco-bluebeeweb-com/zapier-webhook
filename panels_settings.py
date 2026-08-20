"""The single 'App settings' screen (center slot) -- everything
configurable for Zapier Webhook: outgoing webhook URL (Imperal -> Zap)
and inbound shared secret (Zap -> Imperal), plus the recent inbound
events log. Split out of panels.py per the same convention as Make.com
Connector's / n8n Connector's panels_settings.py.

Per ~/UI_INTERFACE_STANDARD.md: every ui.Form here is full_width so its
container stretches to the entire sidebar/dialog width, and its own
input children are also full_width. Every input carries a real label (a
ui.Text caption above it) in addition to a placeholder written for this
app's own domain -- never a bare placeholder standing in for a label,
never a generic example. "How to" instructions live only in the
center-overlay help dialog (zapier_connect_help), not duplicated here.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
import handlers as h


def _outgoing_section(configured: bool) -> ui.UINode:
    """Outgoing Zapier Catch Hook trigger URL -- other Imperal apps fire
    a Zap via send_webhook_event against this saved URL."""
    if configured:
        return ui.Stack(direction="v", gap=2, align="stretch", children=[
            ui.Text("Outgoing webhook (Imperal -> Zap)", variant="heading"),
            ui.Badge(label="Configured", color="green"),
            ui.Button(
                "Clear webhook", variant="secondary", size="sm", full_width=True,
                on_click=ui.Call("set_outgoing_webhook", webhook_url=""),
            ),
        ])
    return ui.Stack(direction="v", gap=2, align="stretch", children=[
        ui.Text("Outgoing webhook (Imperal -> Zap)", variant="heading"),
        ui.Text("Send events from Imperal into a Zap.", variant="caption"),
        ui.Form(
            children=[
                ui.Stack(direction="v", gap=1, align="stretch", children=[
                    ui.Text("Catch Hook URL", variant="caption"),
                    ui.Input(
                        placeholder="https://hooks.zapier.com/hooks/catch/...",
                        param_name="webhook_url",
                    ),
                ]),
            ],
            submit_label="Save webhook",
            action="set_outgoing_webhook",
        ),
    ])


def _inbound_section(configured: bool, webhook_url: str) -> ui.UINode:
    """Inbound direction -- a Zap's 'Webhooks by Zapier' POST action step
    hits this app's fixed URL with a shared secret in a custom header."""
    rows: list[ui.UINode] = [
        ui.Text("Incoming webhook (Zap -> Imperal)", variant="heading"),
        ui.Text("Webhook URL", variant="caption"),
        ui.Text(webhook_url, variant="body"),
        ui.Text("Header name to add in your Zap's POST step", variant="caption"),
        ui.Text("X-Zapier-Webhook-Secret", variant="body"),
    ]
    if configured:
        rows.append(ui.Badge(label="Ready to receive events", color="green"))
        rows.append(ui.Text(
            "Regenerating replaces the secret immediately -- update the "
            "header value in your Zap's action step right after.",
            variant="caption",
        ))
        rows.append(ui.Button(
            "Regenerate secret", variant="secondary", size="sm", full_width=True,
            icon="refresh-cw",
            on_click=ui.Call("regenerate_inbound_secret"),
        ))
    else:
        rows.append(ui.Text(
            "No shared secret yet -- generate one, then paste it as the "
            "header's value in your Zap's action step.",
            variant="caption",
        ))
        rows.append(ui.Button(
            "Generate shared secret", variant="primary", size="sm", full_width=True,
            icon="key", on_click=ui.Call("regenerate_inbound_secret"),
        ))
    return ui.Stack(direction="v", gap=2, align="stretch", children=rows)


def _recent_events_section(events: list) -> ui.UINode:
    if not events:
        return ui.Stack(direction="v", gap=2, children=[
            ui.Text("Recent inbound events", variant="heading"),
            ui.Text("No events received yet.", variant="caption"),
        ])
    items = [
        ui.ListItem(
            id=e.id,
            title=e.received_at,
            subtitle=e.payload_preview[:120],
        )
        for e in events
    ]
    return ui.Stack(direction="v", gap=2, children=[
        ui.Text("Recent inbound events", variant="heading"),
        ui.List(items=items),
    ])


@ext.panel("zapier_settings", slot="center", title="App settings", icon="⚙️",
           center_overlay=True)
async def zapier_settings_panel(ctx, **kwargs) -> object:
    out_status = await h._get_outgoing_status(ctx)
    in_status = await h._get_inbound_status(ctx)

    events = []
    try:
        page = await ctx.store.query(
            h._INBOUND_EVENTS_COLLECTION, order_by="-received_at", limit=10,
        )
        items = getattr(page, "items", None) or []
        for doc in items:
            data = doc.data if hasattr(doc, "data") else doc
            data = data or {}
            events.append(type("E", (), {
                "id": str(getattr(doc, "id", getattr(doc, "doc_id", ""))),
                "received_at": data.get("received_at", ""),
                "payload_preview": data.get("payload_preview", ""),
            })())
    except Exception:
        events = []

    content = ui.Stack(direction="v", gap=4, align="stretch", children=[
        _outgoing_section(out_status.configured),
        ui.Divider(),
        _inbound_section(in_status.configured, in_status.webhook_url),
        ui.Divider(),
        _recent_events_section(events),
    ])
    return ui.Dialog(
        title="App settings",
        content=content,
        confirm_label="",
        cancel_label="Close",
    )
