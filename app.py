"""Extension declaration, secrets, lifecycle hooks.

WHY THIS APP IS CALLED "Zapier Webhook", NOT "Zapier Connector".

Per CONNECTOR_DISCOVERY.md in this same folder: Zapier has no generally
available REST API for listing/creating/running a user's own Zaps. The
only surface that gives that (the Partner API / "Powered by Zapier")
requires US to first publish a public integration INSIDE Zapier's own
catalog and pass their review (~1 week, external, not under our control).
Vlad explicitly chose the fast, narrow path now (2026-08-20): a
Webhooks-by-Zapier-only connector -- no Zap listing, no Zap management,
just two-way webhook plumbing between Imperal and a Zap. This is
deliberately NOT the same shape as Make.com Connector / n8n Connector; it
cannot be, because the underlying API surface Zapier itself exposes here
is narrower. A future "Zapier Connector" (full Partner-API-based) may
follow once Vlad decides to go through Zapier's own app-review process --
that would be a DIFFERENT, later app, per the discovery doc's option 3.

WHY TWO INDEPENDENT WEBHOOK DIRECTIONS, EACH WITH ITS OWN SECRET/CONFIG.

- Outgoing (Imperal -> Zapier): the user adds a "Webhooks by Zapier"
  *trigger* step ("Catch Hook") to a Zap, copies the URL it gives them,
  and pastes it here. send_webhook_event then POSTs to that URL to kick
  off their Zap. Same shape as Make.com Connector's outgoing webhook --
  the URL itself is the credential, stored in ctx.secrets.
- Incoming (Zapier -> Imperal): the user adds a "Webhooks by Zapier"
  *action* step ("POST") to a Zap and points it at the URL this app
  displays (built from @ext.webhook's fixed path). We generate a random
  shared secret the user pastes into a custom header in that Zapier
  action step, and verify it on receipt -- this app has no OAuth/API-key
  relationship with Zapier at all, just a shared secret over HTTPS.

WHY BYOK-style secrets even though there's no "account" to connect.
There is no Zapier account-level auth in this narrow scope -- each
direction's secret is scoped to what it actually protects (an outgoing
target URL, and an inbound shared secret), not a single unified
"connection" like Make/n8n have.
"""

from imperal_sdk import Extension, ChatExtension

ext = Extension(
    "zapier-webhook",
    version="0.1.0",
    display_name="Zapier Webhook",
    description=(
        "Two-way webhook bridge between Imperal and Zapier, built on "
        "Webhooks by Zapier (no Zap listing or management -- Zapier's "
        "public API for that requires a separate, later app-review "
        "process; see this app's own description for why). Send events "
        "from Imperal to trigger a Zap, and receive events a Zap sends "
        "back into Imperal."
    ),
    icon="icon.svg",
    actions_explicit=True,
    capabilities=["zapier:read", "zapier:write"],
)

chat = ChatExtension(
    ext,
    tool_name="zapier-webhook",
    description="Send events to a Zap and receive events a Zap sends back, via Webhooks by Zapier",
)

ext.secret(
    name="zapier_outgoing_webhook_url",
    description=(
        "Outgoing Zapier 'Catch Hook' trigger URL -- add a 'Webhooks by "
        "Zapier' trigger step to a Zap, copy the URL it gives you, and "
        "paste it here. send_webhook_event POSTs to this URL."
    ),
    write_mode="both",
)
ext.secret(
    name="zapier_inbound_shared_secret",
    description=(
        "Shared secret this app generates for you -- paste it into a "
        "custom header (X-Zapier-Webhook-Secret) on a 'Webhooks by "
        "Zapier' POST action step, so this app can verify events really "
        "came from your Zap."
    ),
    write_mode="both",
)


@ext.health_check
async def health_check(ctx) -> bool:
    """Basic liveness check -- confirms the store surface is reachable."""
    await ctx.store.query("zapier_app_settings", limit=1)
    return True
