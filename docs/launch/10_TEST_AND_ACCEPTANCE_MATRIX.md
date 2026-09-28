# Test and acceptance matrix

| Surface | Required evidence | State |
|---|---|---|
| Backend auth | Unit/integration tests for token verification, mapping, sessions, disabled SMS, production fail-closed config | NOT_STARTED |
| Authorization | Customer/merchant/delivery/admin negative and ownership tests | PARTIAL — existing coverage; revalidate after auth |
| Web | Build, Playwright critical paths, accessibility and responsive visual QA | PARTIAL — baseline CI passed; Firebase and visual work pending |
| Flutter | Analyze, unit/widget tests, debug Android build and Android visual QA | PARTIAL — baseline CI passed; Firebase and visual work pending |
| Customer/operations | End-to-end actor journeys, state transitions, quote/payment boundaries | PARTIAL — existing tests; launch rerun pending |
| Release | Compose/images, production config audit, owner config checklist, explicit release approval | BLOCKED |

Repository commands: `make test-backend`, `make test-web`, `make test-e2e`, and `make mobile-check`; CI also runs Android analysis/tests/build and production compose/image validation. Do not use arbitrary sleeps to stabilize async tests.
