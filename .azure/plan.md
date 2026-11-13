# Caspian Compass deployment plan

Status: Demonstrated and verified for this proof of concept.

This public copy records the implementation approach, not reusable access to a
presenter's Azure environment. Deployment-specific values stay in ignored local
configuration.

## Approved scope

Build the supplied Caspian Compass specification as a demonstrator with a React
and TypeScript interface, a Python API, shared deterministic travel-planning
logic, and Microsoft Foundry hosted agents. All accommodation, activity slots,
prices, payments, and bookings are synthetic. No real booking or payment
provider is contacted.

The user approved Python in place of the suggested Node.js API and local SQLite
in place of managed PostgreSQL for this proof of concept. The application is
single-instance; production availability and multi-instance storage are outside
this proof of concept.

## Azure context

- Subscription and directory: explicitly selected by the operator; not published
- Foundry project and resource group: isolated per environment; names not published
- Region used for the demonstration: `northcentralus`
- Hosting: Microsoft Foundry hosted agents, not ordinary prompt agents
- Model and hosting consumption charges: acknowledged in plan approval

Use an isolated resource group for this project. Do not change or reuse unrelated
existing resources. Use explicit subscription and environment values rather than
changing global defaults.

## Implementation ownership

| Workstream | Files | Responsibility |
| --- | --- | --- |
| Travel domain | `server/caspian/catalog.py`, `server/caspian/planning.py`, domain tests | Grounded seed catalogue, reproducible availability, scoring, itinerary, transport, checklist |
| API and booking | `server/caspian/api.py`, `storage.py`, `booking.py`, API tests | Session isolation, SQLite persistence, test-card-only state machine, exports |
| Web interface | `web/` | Search, trip tabs, hotel detail/map, itinerary, booking, sources, grounded assistant |
| Foundry hosting | `azure.yaml`, `server/main.py`, `server/caspian/foundry.py`, agent requirements | Official hosted runtime, specialist agents, Azure provisioning and deployment |
| Integration | `contracts/`, root documentation and scripts | Contract consistency, run instructions, end-to-end verification |

## Data and safety

- Use the specification's twelve fictional hotels and fifteen real-landmark
  activities with synthetic prices and availability.
- Facts retain their source and specification baseline date. Do not describe the
  baseline as independently reverified. Flag facts older than ninety days.
- Deterministic code owns totals, ranking weights, dates, inventory, and booking
  transitions. Model output is never authority to create a reservation.
- Hosted agents handle natural-language interpretation and grounded travel
  assistance; the structured search path does not wait for a language model.
- Passport expiry is checked transiently, never stored or logged.
- Sessions and synthetic inventory expire daily; holds expire after fifteen
  minutes. No real card is accepted.
- Exclude unsafe regions and international land-border itineraries. Conditional
  train routes always include a road alternative and a verification notice.

## Provisioning and validation

Follow the Microsoft Foundry hosted-agent workflow and official sample manifest.
The selected quick-start workflow defers model capacity checks to provisioning;
if provisioning reports unavailable capacity, stop and resolve that specific
constraint without silently changing the user's region or subscription.

Before deployment, confirm the generated resource inventory, environment target,
entrypoint, model deployment, secret exclusions, and local hosted protocol.
Provision only the approved Foundry resources, model, and supporting monitoring
and identity resources. Do not provision unrelated database or web hosting
services without identifying their need.

## Delivery checklist

- [x] Read the full supplied specification.
- [x] Confirm subscription, directory, permissions, project name, and region.
- [x] Obtain implementation and hosted-agent deployment approval.
- [x] Implement the travel domain and deterministic acceptance cases.
- [x] Implement and connect the API, simulated booking, and web interface.
- [x] Provision and verify the new Foundry project.
- [x] Run the hosted agent locally and deploy it.
- [x] Verify a real remote hosted-agent invocation.
- [x] Verify the complete browser workflow and downloads.
- [x] Document commands, architecture, and proof-of-concept limitations.

## Foundry delivery

- The project reached provisioning state `Succeeded` in the operator-selected
  subscription and region. Actual identifiers and endpoints are environment-local.
- The demonstrated hosted agent contained a concierge, itinerary specialist,
  and travel-facts specialist inside one hosted runtime.
- One model deployment: `gpt-5.4-mini`, GlobalStandard, 50,000 TPM allocation.
  The initial 10,000 TPM allocation limited multi-agent calls; it was raised on
  the same model in the same approved region, without adding a model deployment.
- Real application-to-hosted-agent assistant and natural-language parsing calls
  completed with `source: foundry`; parsing preserved explicit dates and guests
  and required confirmation before search.
- Local preview was restarted with the final hosted-response decoding fix.
- The application uses an explicitly configured project endpoint; a saved editor
  selection is not a substitute for the operator's chosen deployment target.
- The frontend and Python API remain local. No separate Azure web host or
  managed PostgreSQL instance was created.

## Local integration evidence

- The combined API/domain suite passed in the isolated Python environment.
- Frontend tests and the production build passed.
- A real browser journey completed search, map/list switching, itinerary editing,
  mock checkout, non-test-card rejection, and PDF/ICS downloads.
- Desktop and mobile layouts were exercised at 1440, 390, and 320 pixels.
- One hundred simultaneous local structured searches returned valid plans with
  zero errors and measured p95 of 379.36 ms. This is a local measured burst,
  not a production availability or load guarantee.
- Browser traffic for that non-AI journey contacted only the local application
  and OpenStreetMap tiles, never a booking or payment provider.
- Integration fixes preserve removed activities when changing other trip fields,
  align required document fields with the API, and prevent a map animation from
  accessing its container after switching views.
