# Contributor guidance

This project was built with the microsoft-foundry skill. Before working on or
answering questions about Foundry agents, read the microsoft-foundry skill first.

- The API and hosted agents share deterministic travel logic in `server/caspian`.
  Do not replace price arithmetic, inventory, eligibility, or booking transitions
  with model-generated decisions.
- `contracts/api.ts` defines the JSON interface consumed by the web application.
  Keep backend responses and frontend types consistent.
- This is a simulation. Never integrate a real booking or payment provider, accept
  real card data, persist passport expiry, or describe a mock booking as a real
  reservation.
- Retain source URLs, baseline dates, and uncertainty on travel facts. Do not
  present an old specification baseline as newly verified information.
