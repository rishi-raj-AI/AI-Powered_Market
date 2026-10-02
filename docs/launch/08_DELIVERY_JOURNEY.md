# Delivery journey

`Sign in → assigned work → pickup/store context → delivery landmark/directions → allowed transitions → tracking/proof → completion or incident`

Current static state: web and Flutter contain delivery task, location-sharing, offline, incident and proof surfaces. The backend’s delivery vocabulary and auditable transitions remain authoritative.

Acceptance: a partner sees only authorized tasks and minimum necessary customer data; GPS permissions and degraded connectivity are clear; pickup/delivery/proof/incident transitions are centrally enforced and auditable; COD instructions are clear. Test Android field conditions before launch.

Privacy invariant: full household contact, address, directions, and exact delivery coordinates are rider-self-service data only. `/delivery/tasks/me` must return them only to the assigned delivery partner; admins use purpose-specific, PII-minimized operations endpoints.
