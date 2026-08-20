"""Thin HTTP helper for the outgoing direction (Imperal -> Zapier).

Mirrors Make.com Connector's post_webhook: a Zapier "Catch Hook" trigger
URL is itself the credential (Zapier authenticates by knowing the URL,
not via a header), so this does a plain POST and reports delivery
success/failure back to the caller rather than raising -- a failed
delivery to the user's own downstream Zap is an expected, non-exceptional
outcome to report, not a connector bug.
"""
from __future__ import annotations


async def post_webhook(ctx, webhook_url: str, payload: dict) -> tuple[bool, int, str]:
    try:
        resp = await ctx.http.post(
            webhook_url, headers={"Content-Type": "application/json"}, json=payload,
        )
    except Exception as exc:  # network-level failure (DNS, timeout, refused)
        return False, 0, f"Could not reach the webhook URL: {exc}"

    status = getattr(resp, "status_code", 0)
    if 200 <= status < 300:
        return True, status, "Delivered."
    return False, status, f"Zapier responded with HTTP {status}."
