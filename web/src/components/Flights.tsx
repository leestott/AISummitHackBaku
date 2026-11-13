import type { Fact, TripPlan } from "../../../contracts/api";
import { copy } from "../i18n";
import { duration, formatDate, gbp, money } from "../utils";
import { Icon } from "./Icon";
import { ExternalLink, FactReferences, Notice, SectionHeading, type MoneyProps } from "./Shared";

export function Flights({ trip, facts, today, busy, onSelect, currency, rates }: MoneyProps & {
  trip: TripPlan; facts: Fact[]; today: string; busy: boolean; onSelect: (flightId: string) => Promise<boolean>;
}) {
  const flights = [...trip.flights].sort((a, b) => a.stops - b.stops || a.duration_min - b.duration_min);
  return <section>
    <SectionHeading title={copy.flights.heading}>{copy.flights.description}</SectionHeading>
    <Notice>{copy.flights.disclaimer}</Notice>
    {!flights.length && <p className="empty-state">{copy.flights.noFlights}</p>}
    <ul className="flight-list">{flights.map(flight => <li key={flight.id}>
      <article className={`flight-row ${trip.selected_flight_id === flight.id ? "is-selected" : ""}`}>
        <header className="flight-header"><div className="carrier-mark"><Icon name="plane" /></div>
          <div><h3>{flight.carrier}</h3><p className="small-copy">{flight.origin} → {flight.destination}</p></div>
          <span className="badge">{flight.stops ? copy.flights.stops(flight.stops) : copy.flights.nonstop}</span>
        </header>
        <div className="flight-route">
          <div><span className="small-copy">{copy.flights.departure}</span>
            {flight.departure_date && <time className="flight-date" dateTime={flight.departure_date}>{formatDate(flight.departure_date, true)}</time>}
            <strong>{flight.depart_local}</strong><span>{flight.origin}</span></div>
          <div className="flight-duration"><span>{duration(flight.duration_min)}</span><div className="route-line"><Icon name="plane" /></div>
            <span className="small-copy">{flight.via ? `${copy.flights.via} ${flight.via}` : copy.flights.nonstop}</span></div>
          <div><span className="small-copy">{copy.flights.arrival}</span>
            {flight.arrival_date && <time className="flight-date" dateTime={flight.arrival_date}>{formatDate(flight.arrival_date, true)}</time>}
            <strong>{flight.arrive_local}</strong>
            <span>{flight.destination}{flight.arrival_day_offset > 0 && <span className="next-day"> +{flight.arrival_day_offset}</span>}</span></div>
        </div>
        <p className="small-copy"><strong>{copy.flights.terminals}: </strong>{flight.terminals}</p>
        <p>{flight.schedule_note}</p>
        {(flight.arrival_day_offset > 0 || flight.early_checkin_note) && <Notice kind="warning">
          <strong>{copy.flights.nextDay}. </strong>{flight.early_checkin_note ?? copy.flights.overnight}
        </Notice>}
        <div className="flight-footer">
          <div><span className="fiction-label">{copy.common.indicative}</span>
            <strong className="fare-range">{gbp(flight.fare_min_gbp)}–{gbp(flight.fare_max_gbp)}</strong>
            {currency !== "GBP" && rates && rates.rates.GBP > 0 && <span className="small-copy">
              {money(flight.fare_min_gbp / rates.rates.GBP, currency, rates)}–{money(flight.fare_max_gbp / rates.rates.GBP, currency, rates)}
            </span>}
            <span className="small-copy">{copy.flights.fare} · GBP</span></div>
          <div className="flight-actions">
            <button type="button" className={trip.selected_flight_id === flight.id ? "button button-secondary" : "button button-primary"}
              disabled={busy || trip.selected_flight_id === flight.id} onClick={() => void onSelect(flight.id)}>
              {trip.selected_flight_id === flight.id && <Icon name="check" />}
              {trip.selected_flight_id === flight.id ? copy.flights.selected : copy.flights.select}
            </button>
            <ExternalLink href={flight.airline_url}>{copy.flights.official}</ExternalLink>
          </div>
        </div>
        <FactReferences ids={flight.grounding_refs} facts={facts} today={today} />
      </article>
    </li>)}</ul>
  </section>;
}
