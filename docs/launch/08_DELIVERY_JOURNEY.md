# Delivery journey

`Sign in → assigned work → pickup/store context → delivery landmark/directions → allowed transitions → tracking/proof → completion or incident`

Current static state: web and Flutter contain delivery-task and location-sharing surfaces. Merged PR #201 adds the existing server-authoritative customer-code proof and guarded completion workflow; it does not send a terminal status mutation or change delivery/payment state locally. The merged UPI fulfilment gate requires an online order to be paid before readiness or any physical fulfilment boundary, while COD remains exact-collection-gated. Rider release/failure controls and durable offline reconciliation remain separate follow-ups, not implied by a delivered-status control.

Acceptance: a partner sees only authorized tasks and minimum necessary customer data; GPS permissions and degraded connectivity are clear; an online order must be paid before it is ready, dispatched, picked up, or completed; the customer receives a handoff code, the server verifies it before completion, and COD collection uses the server-supplied exact total. Pickup/delivery/proof/incident transitions remain centrally enforced and auditable. Test Android field conditions before launch.

Privacy invariant: full household contact, address, directions, and exact delivery coordinates are rider-self-service data only. `/delivery/tasks/me` must return them only to the assigned delivery partner; admins use purpose-specific, PII-minimized operations endpoints.

Web handoff acceptance is now recorded in [16_DELIVERY_WEB_ACCEPTANCE.md](16_DELIVERY_WEB_ACCEPTANCE.md): 60 focused browser cases pass, including exact COD, paid UPI, code-service rejection, synchronous duplicate suppression, and authoritative recovery after lost completion/failed refresh. Its desktop/narrow screenshots use synthetic API fixtures; Android field/device acceptance and final PR CI remain separate gates.

Proof security acceptance (R-022, merged PR #203): enforce a 60-second resend cooldown, at most five issued codes and five incorrect guesses per delivery across resends/restarts/concurrent requests. The final issued code remains usable until expiry unless the guess limit is exhausted. After the limit, use the existing failure/support workflow; admins cannot bypass the proof lock. Verified evidence is immutable and an authorized retry returns it without a new code or evidence write.
