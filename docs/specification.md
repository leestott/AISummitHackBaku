# Caspian Compass: Baku and Azerbaijan Travel Agent

> **Original brief, not current travel advice.** This is the supplied version 1.0 specification dated 13 November 2026. Its requirements and historical claims are preserved; only Markdown layout replaces Word formatting and its generated table of contents. The source's suggested architecture and delivery roadmap are not claims about the completed proof of concept. See [how the application was developed](development.md#what-the-proof-of-concept-changed) for implementation choices and limitations, including the exclusion of international land-border routes.

> [Download the public Word copy](specification.docx). Document properties and unused authoring XML have been removed from that copy; the visible requirements text is unchanged.

Application specification, version 1.0, 13 November 2026. Prepared for Lee Stott, Developer Relations.

## 1. Purpose and summary

Caspian Compass is a web-based travel agent for visitors to Baku and the wider Republic of Azerbaijan. A traveller enters their dates, origin city, budget and interests, and the application returns a trip plan: recommended flights, a shortlist of hotels, activities suited to the season of travel, and the public transport they will need from landing to departure.

The application is a demonstrator. Hotels, room availability, prices and the booking process are synthetic, and no real booking, payment or reservation is ever made. The synthetic data is grounded in verified facts about Azerbaijan (real neighbourhoods, real attractions, real flight routes, real transport fares and real entry rules) so the experience feels authentic and the recommendations are genuinely useful for planning.

The core outcomes are search and discovery of hotels and activities, a realistic end-to-end mock booking flow ending in a clearly labelled "simulated" confirmation, seasonally aware activity recommendations for the chosen travel period, indicative flight options from the traveller's origin, and a transport plan covering the airport transfer, city transit and intercity travel.

## 2. Scope

### 2.1 In scope

- Responsive web UI (desktop, tablet, mobile) for search, browse, compare and mock booking.

- Synthetic hotel inventory for Baku and five regional destinations: Sheki, Gabala, Guba, Shahdag and Ganja.

- Activity catalogue built on real attractions with synthetic time slots, prices and capacity.

- Recommendation engine that ranks activities by travel dates, season, interests, budget and pace.

- Flight recommendation module using real route facts with synthetic fares.

- Public transport planner using published fares and timetables, with a "last verified" date on every fact.

- Pre-travel checklist (e-visa, passport validity, registration rules, currency).

- Simulated booking flow with basket, traveller details, mock payment and simulated confirmation.

### 2.2 Out of scope

- Any live booking, payment processing, or calls to real hotel, airline or rail booking systems.

- Storing real card numbers. The payment step accepts only published test card numbers.

- Issuing tickets, vouchers or e-visas. The application links to official sources instead.

- Travel to regions where the UK FCDO advises against travel; these are excluded from recommendations.

## 3. Users and personas

| Persona | Profile | Primary need |
| --- | --- | --- |
| City-break traveller | Couple from London, 4 nights, mid-range budget | Fast plan for Baku Old City, food and architecture |
| Explorer | Solo traveller, 10 to 14 days, flexible budget | Multi-region route combining Baku, Sheki, Gabala and the mountains |
| Business-plus-leisure | Conference attendee adding 2 days | Hotels near the centre, short evening activities, airport timing |
| Family | Two adults, two children, school holidays | Family-friendly activities, larger rooms, simple transport |
| Demo presenter | Developer advocate showing the app | Reliable, repeatable synthetic data and a seeded "demo mode" |

## 4. Grounding facts (verified November 2026)

The synthetic data must be consistent with the facts below. Each fact is stored in a facts table with a source URL and a last-verified date, and the UI shows "Information checked on [date]. Confirm before travel." beside it.

### 4.1 Entry and documents

| Topic | Fact used by the application | Source |
| --- | --- | --- |
| Visa route | UK and many other nationals apply online for an ASAN e-visa before travel | evisa.gov.az |
| Processing | Standard e-visa issued within 3 working days; urgent within 3 hours | evisa.gov.az/en/information |
| Fee | 20 USD state fee plus 9 USD service fee, paid by Visa, Mastercard, UnionPay or JCB | evisa.gov.az/en/information |
| Stay | Single entry, valid for a 30-day stay | evisa.gov.az/en/information |
| Passport | Must expire at least 3 months after the e-visa expiry date | evisa.gov.az/en/information |
| Registration | Visitors staying more than 15 days must register with the State Migration Service | entryrules.com (citing official source) |
| Land borders | As of early November 2026, entry by land and by ferry is closed to foreign tourists; plan to arrive by air | 4ttransfer.com (citing ADY) |

### 4.2 Flights (London example)

| Route | Operator | Pattern | Times and duration |
| --- | --- | --- | --- |
| London Heathrow T4 to Baku GYD T1 | Azerbaijan Airlines (AZAL) | 3 non-stop flights per week | Departs 22:05, arrives about 07:35 next day; about 5h 30m |
| London Gatwick North to Baku GYD T1 | Azerbaijan Airlines (AZAL) | 4 non-stop flights per week | Departs between 10:25 and 11:25; about 5h 30m |
| London to Baku via Istanbul | Turkish Airlines | Daily one-stop options | About 8h 50m to 9h 15m total |
| London to Baku via Warsaw, Frankfurt, Vienna and others | LOT, Lufthansa, BA codeshares | One-stop options | About 8h to 11h total |

Heydar Aliyev International Airport (GYD) is the only airport in Baku. Fares in the application are synthetic and must be labelled "indicative".

### 4.3 Public transport

| Mode | Fact used by the application |
| --- | --- |
| H1 Airport Express bus | Runs 24/7 between the airport, Koroglu interchange and 28 May metro; every 15 minutes; about 30 minutes; fare 1.30 AZN; pay by bank card, Apple Pay, Google Pay, BakiKart, m10 or Birbank |
| BakiKart | Rechargeable transit card; card costs 2 AZN; sold at airport and metro stations |
| Baku Metro | Single ride about 0.60 AZN on BakiKart (sources differ; show as approximate) |
| Rail: Baku to Ganja | Daily trains, about 4 hours, from about 12.80 AZN |
| Rail: Baku to Gabala | Weekends and holidays only, 07:30 to 11:06, from 12 AZN |
| Rail: Baku to Sheki and Balakan | Night train resuming from 20 November 2026; Sheki from about 14.80 AZN; timetable being confirmed |
| Rail: Baku to Tbilisi | Daily, including Stadler sleeper 23:10 to 08:41 next day |
| No rail service | Guba, Shahdag, Shamakhi and Gobustan are reached by road (car, transfer or tour) |
| Tickets | ADY sells on ticket.ady.az, the ADY Mobile app and station offices; original passport needed |

### 4.4 Destination facts

Icherisheher (the walled Old City) was inscribed by UNESCO in 2000 and contains the Maiden Tower and the Palace of the Shirvanshahs. Baku sits about 28 m below sea level and is known as the City of Winds. Summers are hot and winters mild; spring (March to May) and autumn (September to November) are generally the most comfortable seasons. The currency is the Azerbaijani manat (AZN); cards are widely accepted in Baku, while cash matters more in the regions.

## 5. Functional requirements

### 5.1 Trip search (home page)

| ID | Requirement |
| --- | --- |
| FR-01 | Search form captures origin city or airport, arrival and departure dates, number of adults and children, budget band (economy, mid-range, premium) and interests (history, architecture, food, nature, adventure, wine, family, nightlife). |
| FR-02 | Destination defaults to Baku, with optional add-on regions (Sheki, Gabala, Guba, Shahdag, Ganja). |
| FR-03 | Validation: departure after arrival; total stay of 30 days or fewer triggers the e-visa notice; over 15 days triggers the registration notice. |
| FR-04 | Search returns a single "Trip plan" page with tabs for Flights, Hotels, Activities, Transport and Checklist. |
| FR-05 | Free-text search box ("3 days in Baku with kids in April") parsed into the structured fields above, with the parsed values shown for confirmation. |

### 5.2 Hotel search and detail

| ID | Requirement |
| --- | --- |
| FR-10 | List view with filters for district, star rating, price per night (AZN and GBP), guest score, amenities, distance to nearest metro, and family suitability. |
| FR-11 | Map view placing hotels at their synthetic coordinates within the real district boundary. |
| FR-12 | Detail page shows description, room types, amenities, cancellation policy, nearest metro station, H1 stop, and walking time to Icherisheher. |
| FR-13 | Availability calendar driven by a deterministic synthetic generator (same seed returns the same result), with higher prices and lower availability during peak events. |
| FR-14 | Every hotel page carries a persistent banner: "Demonstration hotel. Fictional property and prices." |

### 5.3 Activity recommendations

| ID | Requirement |
| --- | --- |
| FR-20 | Catalogue of real attractions and experiences with synthetic slot times, prices and capacity. |
| FR-21 | Recommendation score per activity: season fit (35%), interest match (30%), budget fit (15%), travel-time feasibility from the chosen hotel (10%) and diversity bonus (10%). |
| FR-22 | Seasonal rules: outdoor and mountain activities are down-ranked in heavy weather months; Shahdag ski activities appear only December to March; indoor museums are boosted on high-wind or rainy days. |
| FR-23 | Event overlay: when dates overlap a known event (for example Novruz in late March), relevant activities are boosted and hotel prices raised. Event dates are stored with a "confirm dates" flag. |
| FR-24 | Auto-generated day-by-day itinerary with a pace setting (relaxed, balanced, packed), respecting opening hours and travel time between stops. |
| FR-25 | Each activity shows "How to get there" using the transport module. |

### 5.4 Flight recommendations

| ID | Requirement |
| --- | --- |
| FR-30 | For the origin and dates, list non-stop options first, then one-stop options, using the real route patterns in section 4.2. |
| FR-31 | Each option shows carrier, departure and arrival times, duration, stops, terminals and a synthetic indicative fare range. |
| FR-32 | Arrival-time intelligence: an overnight arrival (for example 07:35 from Heathrow) flags early check-in and suggests a light first-day plan. |
| FR-33 | "Check on airline site" link replaces any purchase button. No flight booking is simulated beyond adding to the trip plan. |

### 5.5 Transport planner

| ID | Requirement |
| --- | --- |
| FR-40 | Airport-to-hotel plan: H1 bus to 28 May or Koroglu, then metro or a short taxi, with fare and time estimates; taxi and ride-hailing shown as alternatives. |
| FR-41 | City transit guidance: BakiKart purchase, top-up, metro lines and stations nearest each hotel and activity. |
| FR-42 | Intercity legs: rail where available (Ganja, Gabala at weekends, Sheki from 20 November 2026), road transfer otherwise (Guba, Shahdag, Shamakhi, Gobustan). |
| FR-43 | Each leg shows mode, duration, indicative cost in AZN and GBP, booking channel and a last-verified date. |
| FR-44 | Total transport budget for the trip, summed by code, not by hand. |

### 5.6 Simulated booking flow

The booking flow mirrors a real online travel agent so it can be demonstrated end to end, but every step is clearly synthetic.

| Step | Screen | Behaviour |
| --- | --- | --- |
| 1 | Basket | Hotel room(s) and activities with dates, guests and line prices; flights shown as "planned, not booked" |
| 2 | Traveller details | Name, email, nationality, passport expiry (used only to run the 3-month validity check, then discarded) |
| 3 | Review | Price breakdown, cancellation terms, and checklist warnings (e-visa, registration) |
| 4 | Mock payment | Accepts test card numbers only; any other number is rejected with "Real cards are not accepted in this demo" |
| 5 | Simulated confirmation | Reference in the form SIM-BAK-XXXXXX, a watermark reading "SIMULATED – NOT A RESERVATION", and downloadable itinerary (PDF and .ics) |

Booking state machine: draft → held (15-minute synthetic hold) → details_captured → payment_simulated → confirmed_simulated, with expired and cancelled_simulated as terminal states. Synthetic inventory is decremented within the demo session only and reset nightly.

### 5.7 Pre-travel checklist

A generated checklist covering the e-visa (fee, processing time, official portal link), passport validity, registration for stays over 15 days, travel insurance, currency and card use, BakiKart, modest dress at mosques, and the current FCDO advice link.

## 6. Synthetic data specification

### 6.1 Principles

- Fictional names for every hotel and tour operator, so no real business is misrepresented. Real names are used only for public landmarks, transport operators, airports and airlines.

- Real geography: coordinates fall inside the real district; nearest metro station and distances are computed from real station locations.

- Plausible pricing: price bands are calibrated to the district and star rating, then varied by season and day of week with a seeded random generator.

- Every synthetic record carries is_synthetic: true and a grounding_refs list naming the facts it relies on.

- Reproducible: a single seed value regenerates the whole dataset for demos and tests.

### 6.2 Synthetic hotel catalogue (sample)

| ID | Name (fictional) | Location (real district) | Stars | Nearest transport | Base rate AZN / night |
| --- | --- | --- | --- | --- | --- |
| HTL-BAK-001 | Qala Courtyard House | Icherisheher (Old City) | 4 | Icheri Sheher metro | 210 |
| HTL-BAK-002 | Caspian Promenade Hotel | Baku Boulevard / Sahil | 5 | Sahil metro | 390 |
| HTL-BAK-003 | Nizami Street Suites | Fountains Square / Nizami Street | 4 | Sahil or 28 May metro | 180 |
| HTL-BAK-004 | Flame Hill Residence | Upland Park area near Flame Towers | 5 | Funicular / taxi | 420 |
| HTL-BAK-005 | Station Square Inn | Near 28 May station (H1 stop, rail station) | 3 | 28 May metro | 95 |
| HTL-BAK-006 | White City Lofts | White City / Port Baku | 4 | Ganjlik or Koroglu metro | 160 |
| HTL-BAK-007 | Absheron Shore Resort | Absheron coast, Mardakan | 5 | Taxi / transfer | 350 |
| HTL-SHK-001 | Silk Caravan Guesthouse | Sheki old town, near Khan's Palace | 3 | Sheki station (from 20 Nov 2026) | 85 |
| HTL-GAB-001 | Tufandag Valley Lodge | Gabala, near Tufandag cable car | 4 | Gabala station (weekend train) | 170 |
| HTL-GUB-001 | Qudyalchay River Rooms | Guba town | 3 | Road transfer only | 75 |
| HTL-SHD-001 | Shahdag Snowline Chalet | Shahdag Mountain Resort | 4 | Road transfer only | 240 |
| HTL-GNJ-001 | Javad Khan Street Hotel | Ganja centre | 3 | Ganja station | 80 |

Rates shown are synthetic base rates for a standard double room. The generator applies multipliers: weekend 1.10, peak event 1.35 to 1.60, low season 0.80, family room 1.40, suite 2.20.

### 6.3 Activity catalogue (sample)

| ID | Activity (real place) | Area | Duration | Best season | Synthetic price AZN |
| --- | --- | --- | --- | --- | --- |
| ACT-001 | Guided walk of Icherisheher (UNESCO Old City) | Baku | 3h | All year | 35 |
| ACT-002 | Maiden Tower and roof deck | Baku | 1.5h | All year | 15 |
| ACT-003 | Palace of the Shirvanshahs | Baku | 2h | All year | 15 |
| ACT-004 | Heydar Aliyev Center (Zaha Hadid) | Baku | 2h | All year, rainy days | 20 |
| ACT-005 | Azerbaijan Carpet Museum | Baku | 1.5h | All year, rainy days | 12 |
| ACT-006 | Funicular and Martyrs' Lane viewpoint at sunset, Flame Towers light show | Baku | 2h | All year, evenings | 10 |
| ACT-007 | Baku Boulevard and Caspian boat trip | Baku | 2.5h | April to October | 25 |
| ACT-008 | Gobustan rock carvings and mud volcanoes | About 70 km south-west | 5h | Spring and autumn; avoid after heavy rain | 70 |
| ACT-009 | Ateshgah Fire Temple and Yanar Dag | Absheron Peninsula | 4h | All year, best at dusk | 55 |
| ACT-010 | Food tour: plov, qutab, dolma and tea | Baku | 3h | All year | 90 |
| ACT-011 | Sheki Khan's Palace and caravanserai day | Sheki | Full day or overnight | Spring to autumn | 120 |
| ACT-012 | Gabala cable car and Nohur Lake | Gabala | Full day | May to October | 110 |
| ACT-013 | Guba, Candy Cane Mountains and Khinalig village | Guba region | Full day | May to October | 130 |
| ACT-014 | Shahdag ski day | Shahdag | Full day | December to March | 150 |
| ACT-015 | Shamakhi wine tasting | Shamakhi | Half day | All year | 85 |

### 6.4 Seasonal calendar used by the recommender

| Period | Conditions | Recommender behaviour |
| --- | --- | --- |
| December to February | Mild in Baku, cold and snowy in the mountains, windy | Boost museums, food, hammams; enable Shahdag skiing; down-rank boat trips |
| March to May | Comfortable, spring bloom; Novruz holiday in late March | Boost Old City, Gobustan, regional trips; Novruz events and price uplift |
| June to August | Hot, often above 30 °C | Boost early-morning and evening slots, Caspian beaches, mountain escapes to Gabala and Guba |
| September to November | Comfortable, harvest season | Boost wine tasting, hiking, regional day trips; check for major events (for example the Baku Formula 1 race, dates to be confirmed) |

## 7. Data model

| Entity | Key fields |
| --- | --- |
| Fact | id, topic, statement, value, unit, source_url, last_verified, confidence |
| Destination | id, name, region, lat, lon, transport_modes, notes |
| Hotel | id, name, destination_id, district, lat, lon, stars, amenities[], base_rate_azn, nearest_metro, family_friendly, is_synthetic, grounding_refs[] |
| RoomType | id, hotel_id, name, max_occupancy, rate_multiplier, inventory |
| Activity | id, name, destination_id, category[], duration_min, season_months[], indoor, price_azn, opening_hours, capacity_per_slot, grounding_refs[] |
| Event | id, name, start_date, end_date, dates_confirmed, price_multiplier, boosted_categories[] |
| FlightOption | id, origin, destination, carrier, days_of_week[], depart_local, arrive_local, duration_min, stops, via, terminals, fare_band_gbp, is_indicative |
| TransportLeg | id, from, to, mode, operator, duration_min, fare_azn, schedule_note, booking_channel, fact_refs[] |
| TripPlan | id, session_id, search_params, flights[], hotel_selection, activities[], itinerary_days[], transport_legs[], checklist[] |
| SimBooking | reference, trip_plan_id, state, items[], total_azn, total_gbp, created_at, expires_at, watermark |

## 8. API design

| Method and path | Purpose |
| --- | --- |
| POST /api/search | Parse structured or free-text search; return a TripPlan id |
| GET /api/trip/{id} | Full trip plan |
| GET /api/hotels?destination=&district=&stars=&price_min=&price_max=&checkin=&checkout= | Hotel search |
| GET /api/hotels/{id}/availability?checkin=&checkout=&guests= | Synthetic availability and rates |
| GET /api/activities/recommendations?trip_id= | Ranked activities with score breakdown |
| GET /api/flights?origin=&depart=&return= | Indicative flight options |
| GET /api/transport/plan?trip_id= | Airport, city and intercity legs with costs |
| GET /api/checklist?trip_id=&nationality= | Pre-travel checklist |
| POST /api/sim-bookings | Create a simulated booking (draft and hold) |
| POST /api/sim-bookings/{ref}/pay | Mock payment with test cards only |
| GET /api/sim-bookings/{ref} | Simulated confirmation and itinerary downloads |
| GET /api/facts | All grounding facts with sources and verification dates |

## 9. User interface

### 9.1 Pages

- Home: hero image of the Baku skyline, search form, seasonal "Why visit now" panel driven by the current month.

- Trip plan: tabbed view (Flights, Hotels, Activities, Transport, Checklist) with a persistent trip summary and running total.

- Hotel results and hotel detail, with list and map toggle.

- Activity explorer with filters and a drag-and-drop itinerary builder.

- Basket, traveller details, review, mock payment and simulated confirmation.

- About the data: explains the synthetic approach and lists every grounding fact with its source.

### 9.2 Design and accessibility

- Visual language inspired by the Caspian: deep teal accent, sandstone neutrals, generous whitespace.

- WCAG 2.2 AA: keyboard navigation, visible focus, contrast checked, alt text for all imagery, ARIA live regions for search results.

- Currency toggle (AZN, GBP, USD, EUR) with a dated exchange rate; language-ready for English, Azerbaijani and Russian.

- Synthetic labelling is always visible: banner on hotel pages, watermark on confirmations, "indicative" on fares.

## 10. Non-functional requirements

| Area | Requirement |
| --- | --- |
| Performance | Search results in under 1.5 seconds at the 95th percentile with 100 concurrent users |
| Availability | 99.5% for the demo environment |
| Security | No real payment data; test card allow-list; OWASP Top 10 controls; rate limiting on search |
| Privacy | Passport expiry used transiently for the validity check and never stored; demo sessions purged nightly |
| Data freshness | Facts older than 90 days are flagged in the admin view for re-verification |
| Observability | Structured logs, request tracing, dashboard for searches, simulated bookings and recommendation clicks |
| Determinism | Fixed seed for demo mode so presentations are repeatable |

## 11. Suggested technical architecture

- Front end: React with TypeScript and Vite, a component library such as Fluent UI, and a map component using OpenStreetMap tiles.

- Back end: Node.js (or ASP.NET Core) REST API; recommendation and itinerary logic as a separate service.

- Data: PostgreSQL with PostGIS for geography; JSON seed files for synthetic hotels, activities and facts.

- Synthetic data generator: Python script using a fixed seed, reading the facts table and writing seed files, with validation tests that every record references at least one fact.

- Optional AI assistant: a chat panel that answers questions using only the facts table and the trip plan, and refuses to claim that anything is booked.

- Hosting: Azure Static Web Apps for the front end, Azure Container Apps for the API, Azure Database for PostgreSQL.

## 12. Acceptance criteria

- A search for London to Baku, 4 nights in April, mid-range, history and food returns non-stop AZAL options from Heathrow and Gatwick, at least five hotels, a four-day itinerary and an airport plan using the H1 bus.

- A December search that includes Shahdag shows ski activities; a July search for the same destination does not.

- A stay longer than 15 days shows the registration notice; a stay longer than 30 days shows the e-visa limit warning.

- The booking flow completes with a test card and produces a SIM-BAK- reference and watermark; a non-test card number is rejected.

- Every hotel, fare and booking screen displays its synthetic or indicative label.

- Every transport fare and entry rule shown in the UI links to a fact with a source and a last-verified date.

- No outbound call is made to any real booking or payment system (verified by network tests).

## 13. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Users mistake the demo for a real booking site | Persistent labels, watermark, test-card-only payment, no real supplier names |
| Facts go out of date (fares, timetables, visa fees, border rules) | Last-verified dates, 90-day re-verification flag, "confirm before travel" text |
| Sources disagree (for example metro fare 0.40 vs 0.60 AZN) | Store the range, show as approximate, link to the operator |
| Rail services change at short notice (Sheki line resuming 20 November 2026) | Schedule flag on rail legs and road alternative always shown |
| Safety-sensitive regions recommended | Exclusion list aligned with current FCDO advice |

## 14. Delivery plan

| Phase | Weeks | Output |
| --- | --- | --- |
| 1. Foundations | 1 to 2 | Facts table, data model, synthetic data generator, seed data |
| 2. Search and hotels | 3 to 4 | Search, hotel list, map and detail pages |
| 3. Activities and itinerary | 5 to 6 | Recommender, seasonal rules, itinerary builder |
| 4. Flights and transport | 7 | Flight options, transport planner, checklist |
| 5. Simulated booking | 8 | Basket to confirmation flow, PDF and calendar export |
| 6. Hardening and demo | 9 to 10 | Accessibility audit, performance tests, demo mode and presenter script |

## 15. Sources

- Republic of Azerbaijan official e-visa portal: https://evisa.gov.az/en/information

- EntryRules, UK citizens travelling to Azerbaijan: https://entryrules.com/countries/azerbaijan/gb

- BakuBus, H1 Airport Express: https://www.bakubus.az/quality

- Directflights.com, London Heathrow to Baku: https://www.directflights.com/LHR-GYD

- Directflights.com, London Gatwick to Baku: https://www.directflights.com/LGW-GYD

- FlightConnections, LHR to GYD: https://www.flightconnections.com/flights-from-lhr-to-gyd

- Flight Routes, LHR to GYD one-stop options: https://www.flightroutes.com/LHR-GYD

- 4T Transfer, trains in Azerbaijan 2026 (citing ADY): https://4ttransfer.com/trains-azerbaijan/

- Operativ Məlumat Mərkəzi, ADY timetable: https://operativmm.az/en/qatar-cedveli

- Lonely Planet, best things to do in Baku: https://www.lonelyplanet.com/articles/best-things-to-do-in-baku-azerbaijan

- App Savvy Traveller, things to do in Baku: https://appsavvytraveller.com/things-to-do-in-baku/

- Azerbaijan Railways ticketing: https://ticket.ady.az
