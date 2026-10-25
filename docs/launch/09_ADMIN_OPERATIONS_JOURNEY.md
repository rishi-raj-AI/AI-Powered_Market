# Admin and support journey

`Sign in → operations overview → merchant/order/delivery/support visibility → authorized intervention → audit trail`

Current static state: admin operations, delivery recovery/performance, support queue and capability-aware support surfaces exist. Their visual quality and complete end-to-end authorization remain unverified.

2026-10-25 bounded acceptance result: the existing backend capability boundary was sound, but the web admin surface advertised role changes to normal admins that the server denies, and advertised a one-click post-pickup return to admins without the required financial authority. The isolated remediation reads the existing server capability response before exposing those controls; discovery failures fail closed. Normal administrators retain pre-pickup reassign with `rider.operations`; post-pickup return additionally requires `refund.write` and `settlement.write`, presents an explicit consequence review, and reports only the server's resulting refund/settlement outcome. Server capability checks, locks, transitions, audit, and financial rules remain the authority.

Acceptance: only appropriate capabilities expose and permit interventions; user, merchant, delivery and support actions are auditable; public replies and internal notes remain separated; failure/recovery operations show clear consequences and confirmation where destructive.

Availability invariant: operational active-store counts include only active stores whose merchant is approved; a suspended merchant's preserved store flag must not make it operationally active.
