# Zapier Platform App + Imperal Companion Connector — Preparation

**Owner:** Imperal Cloud / Vlad
**Prepared:** 2026-08-23
**Status:** implementation preparation approved by product decision

## 1. Passport

Zapier integration consists of two coordinated products:

1. **Imperal for Zapier** — a public Zapier Platform CLI integration, submitted to Zapier for Marketplace review. It makes Imperal events and approved Imperal operations available in users' Zaps.
2. **Zapier Companion Connector** — the Imperal-native connector. It provides secure two-way webhook bridging immediately and will add Powered by Zapier workflow management only after Zapier grants Partner API access.

The user selected the combined route: build both products now, submit the public integration for review, and unlock Partner API functionality only when Zapier has approved and provisioned the required client credentials.

## 2. Problem statement

When an operations team wants to connect Imperal workflows with its existing Zapier automations, it currently has to manually configure webhook URLs and loses a structured, reviewable integration surface. This causes duplicated setup work, weak observability, and no governed route to future Zap lifecycle management.

## 3. Audience, roles and access

- **Zap builder:** authorizes their Imperal account in Zapier and selects Imperal triggers/actions.
- **Imperal workspace owner:** configures the companion bridge, rotates inbound webhook secrets, and later connects Powered by Zapier.
- **Imperal platform operator:** owns the external API contract, Zapier developer account, review answers, demo account, and production credentials.

No Zapier connection label, error, event preview, log, UI title, or response may reveal an access token, webhook URL used as a credential, shared secret, or OAuth client secret.

## 4. User journeys and human decision points

1. A Zapier user connects an Imperal account via OAuth/API token, verified by a non-sensitive identity endpoint.
2. They select an Imperal event trigger. The integration subscribes a Zapier target URL through the Imperal event-subscription API and provides an identical polling sample fallback.
3. They use an Imperal action or search in a Zap. The adapter calls a documented Imperal API endpoint and returns a structured record, not a generic success message.
4. An Imperal user configures immediate outbound delivery to an existing Catch Hook and optionally receives inbound POSTs protected by a rotated shared secret.
5. After Zapier review grants Powered by Zapier access, a workspace owner connects it in the companion connector. Only then are list/create/enable/disable Zap controls exposed.

Human decision: publishing, OAuth client registration, Partner API credential entry, production endpoint configuration, destructive actions, and any monetary action remain explicit human-owned steps.

## 5. Value and success metrics

- All visible Zapier operations have a live test Zap and one successful run before review.
- Zapier validation has no blocking errors.
- Companion outbound/inbound bridge is usable independently of Partner API approval.
- No secret leaks in tests, source inspection, labels, diagnostics, or event history.
- Powered by Zapier features remain unavailable until their credential gate is satisfied.

## 6. Scope, non-scope and safety boundary

### In scope now

- TypeScript ESM Zapier Platform CLI project with typed auth, REST-hook trigger architecture, polling fallback, action/search scaffolding, validation/test scripts, static samples, and review package.
- Maximum public integration capability that can be implemented against an actual Imperal API contract: event trigger subscription, event search, and approved command dispatch.
- Existing companion's bidirectional Webhooks by Zapier bridge, secure secret rotation, event log, panels, PST, pricing, and Imperal validation.
- Partner API readiness artifacts and a feature gate for future Zap management.

### Deliberately not fabricated

The local platform repository contains no live public Imperal OAuth/API implementation or endpoint contract. The public Zapier app must not pretend such endpoints exist or send user credentials to a made-up URL. Its network adapter therefore requires explicit `IMPERAL_API_BASE_URL` and client credentials when the real public API is registered. Without those, source code and local contract tests can be validated, but a live Zapier account cannot be connected or submitted as proven functional.

### Out of scope until Zapier approval

- Reading, creating, editing, enabling, disabling, or running a user's Zaps through Powered by Zapier.
- Claiming Marketplace publication or Partner API access before Zapier confirms both.

## 7. Data, privacy and integration map

- Zapier stores only connection auth data required by its Platform connection model.
- The companion stores webhook URLs and shared secrets in `ctx.secrets`; its small inbound event ledger stores bounded payload previews.
- Zapier REST Hook subscription endpoints must receive only Zapier-provided target URLs and non-secret subscription references.
- Production API secrets are Zapier environment variables, never source files.

## 8. P0 definition and acceptance criteria

P0 is complete when the Zapier project passes local TypeScript build, unit tests and `zapier-platform validate`; every integration operation has static sample/data contract coverage; companion imports, tests and Imperal manifest validation pass; all tool prices use the approved scale; and external blockers are documented precisely.

## 9. Imperal panel UX map

The companion retains one `App settings` secondary button and center settings screen. Forms use labeled, full-width inputs with contextual placeholders. Setup instructions live in the center help overlay only; the sidebar never duplicates them.

## 10. Safety, approvals and audit trail

- Shared-secret comparison is constant-time.
- Secret rotation invalidates the old secret immediately.
- Payload previews are capped and rolling history bounded.
- No public integration delete action will be supplied; Zapier guidance favors non-destructive operations.
- Review and Partner API gates are recorded here and in `CONNECTOR_DISCOVERY.md`.

## 11. Discovery and validation plan

Official sources checked 2026-08-23: Zapier Platform CLI overview, TypeScript integration guide, triggers, actions, deduplication, integration checks, and Powered by Zapier documentation. Validate with `npm test`, `npm run build`, `zapier-platform validate`, companion PST/import tests, `imperal validate .`, security greps, pricing verification, then external live-test/review steps once credentials and endpoint contract exist.

## 12. Implementation plan and delivery statuses

| Item | Status |
|---|---|
| Companion webhook bridge | existing; re-audit/validate |
| Zapier Platform TypeScript project | in progress |
| Public Imperal API contract / OAuth registration | external platform dependency |
| Zapier local validation | pending |
| Companion validation and pricing check | pending |
| Zapier live Zaps / public review | blocked by real API/demo account and Zapier developer credentials |
| Powered by Zapier management | blocked by Zapier approval/client ID |

## 13. Decision log

- 2026-08-23: User selected both the public Zapier application and an Imperal companion connector, maximum real functionality, with submission when unblocked.
- 2026-08-23: No fake Imperal public API surface will be introduced merely to satisfy an external review checklist.

## 14. Live verification log

Pending real Imperal public API endpoints, Zapier developer account authentication, production connection, and Zapier review.
