# UI/UX audit

Evidence labels: **Static** = source inspection; **Functional** = executed test/device flow; **Visual** = inspected rendering. This audit is Static only unless stated otherwise.

| Actor | Static findings | Status | Evidence needed |
|---|---|---|---|
| Customer | Web/mobile login, account, address/location, market/store/catalogue, cart, checkout, orders/tracking/support exist | MVP_USABLE; NOT_VISUALLY_VERIFIED | Auth replacement, quote/COD/order flows, narrow web and Android visual QA |
| Merchant | Store/catalogue/inventory, orders, settlements, and legacy generic media page exist | MVP_USABLE; NEEDS_POLISH; NOT_VISUALLY_VERIFIED | Role/ownership and operational state QA; do not extend legacy media route |
| Delivery | Assignment, pickup/delivery transitions, location sharing, offline page, incidents/proof exist | MVP_USABLE; NOT_VISUALLY_VERIFIED | Permission, weak-connectivity, proof and Android field-device QA |
| Admin/support | Operations, support queue, recovery and delivery performance views exist | MVP_USABLE; NOT_VISUALLY_VERIFIED | Capability enforcement, destructive-action and desktop/narrow visual QA |

Reusable web components include buttons, fields, notices, empty/loading/retry views and price breakdowns. Static code also contains location/landmark cues, live-tracking error states, and some offline/retry behavior. Application of these patterns is not yet proven consistent.

Later visual QA must inspect desktop and narrow web, Flutter Android, iOS where possible, loading/empty/error/success/long text, permission failure, validation, and slow/offline recovery. Record screenshots and defects; do not call any surface polished before that evidence exists.

2026-10-04 bounded update: the web delivery handoff screen now has functional and inspected 320px/390px/1280px synthetic-fixture evidence in [16_DELIVERY_WEB_ACCEPTANCE.md](16_DELIVERY_WEB_ACCEPTANCE.md). This covers the picked-up COD rendering and functional loading/error/empty/retry behavior, not every delivery screen/state or Android/iOS acceptance. Other actors remain visually unverified.
