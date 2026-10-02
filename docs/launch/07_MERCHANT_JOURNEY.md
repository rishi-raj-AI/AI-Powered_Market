# Merchant journey

`Sign in → verified merchant/store context → catalogue/inventory → incoming orders → allowed accept/reject/prepare/ready actions → settlement/status visibility`

Current static state: web and Flutter merchant paths exist for stores, inventory, orders and settlements. Verify all critical actions are server-side ownership/role guarded; hidden UI is never authorization.

Acceptance: merchant sees only owned stores/orders, receives clear operational state and recovery errors, cannot take invalid transitions, and has usable low-bandwidth/error states. Listing-owned media is deferred; the generic legacy media page is not the solution.

Availability invariant: `Store.is_active` is the merchant-owned store choice. `Merchant.status` is a separate platform eligibility gate; suspension and reapproval must not rewrite stored per-store availability.
