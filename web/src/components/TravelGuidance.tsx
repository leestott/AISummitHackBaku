import { useEffect, useRef, useState, type FormEvent } from "react";
import type { ChecklistItem, Fact, TripPlan } from "../../../contracts/api";
import { api, errorMessage } from "../api";
import { copy } from "../i18n";
import { duration, formatDate, humanize, safeUrl } from "../utils";
import { Icon } from "./Icon";
import { ErrorNotice, ExternalLink, FactReferences, Notice, Price, SectionHeading, type MoneyProps } from "./Shared";

export function Transport({ trip, currency, rates, facts, today }: MoneyProps & { trip: TripPlan; facts: Fact[]; today: string }) {
  return <section>
    <SectionHeading title={copy.transport.heading}>{copy.transport.description}</SectionHeading>
    <Notice>{copy.transport.baseline}</Notice>
    <p className="transport-total"><span>{copy.transport.total}</span><strong><Price amount={trip.totals.transport_azn} currency={currency} rates={rates} secondary /></strong></p>
    {!trip.transport_legs.length && <p className="empty-state">{copy.transport.noLegs}</p>}
    <ol className="transport-list">{trip.transport_legs.map(leg => <li key={leg.id} className="transport-leg">
      <div className="transport-symbol"><Icon name={leg.mode.toLowerCase().includes("walk") ? "walk" : "bus"} /></div>
      <div className="transport-body">
        <div className="transport-meta"><span>{humanize(leg.mode)} · {leg.operator}</span><span>{duration(leg.duration_min)}</span></div>
        <h3>{leg.from}<span className="route-arrow" aria-hidden="true"> → </span>{leg.to}</h3>
        <p>{leg.schedule_note}</p>
        <dl className="transport-prices">
          <div><dt>{copy.transport.fare}</dt><dd><Price amount={leg.fare_azn} currency={currency} rates={rates} secondary /></dd></div>
          <div><dt>{copy.transport.partyTotal}</dt><dd><Price amount={leg.total_azn} currency={currency} rates={rates} /></dd></div>
        </dl>
        <p className="approximate-note"><Icon name="info" />{copy.common.approximate}</p>
        <p><strong>{copy.transport.channel}: </strong>{safeUrl(leg.booking_channel) ?
          <ExternalLink href={leg.booking_channel}>{leg.booking_channel}</ExternalLink> : leg.booking_channel}</p>
        {leg.alternative && <Notice><strong>{copy.transport.alternative}: </strong>{leg.alternative}</Notice>}
        <p className="source-note">{copy.common.checked(formatDate(leg.last_verified))}</p>
        <FactReferences ids={leg.fact_refs} facts={facts} today={today} />
      </div>
    </li>)}</ol>
  </section>;
}

export function ChecklistEntries({ entries, facts, today, checkable = false }: {
  entries: ChecklistItem[]; facts: Fact[]; today: string; checkable?: boolean;
}) {
  const [checked, setChecked] = useState<string[]>([]);
  if (!entries.length) return <p className="empty-state">{copy.checklist.empty}</p>;
  return <ul className="checklist">{entries.map(item => <li key={item.id} className={`checklist-item severity-${item.severity}`}>
    <label className="checklist-symbol">
      {checkable ? <input type="checkbox" aria-label={`${copy.checklist.complete}: ${item.title}`} checked={checked.includes(item.id)}
        onChange={event => setChecked(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))} />
        : <Icon name={item.severity === "warning" ? "warning" : "checklist"} />}
    </label>
    <div><h3>{item.title}</h3><p>{item.description}</p>
      <FactReferences ids={item.fact_refs} facts={facts} today={today} fallback={{ source_url: item.source_url, last_verified: item.last_verified }} />
    </div>
  </li>)}</ul>;
}

export function Checklist({ trip, facts, today }: { trip: TripPlan; facts: Fact[]; today: string }) {
  const [nationality, setNationality] = useState("GB");
  const [entries, setEntries] = useState(trip.checklist);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  useEffect(() => { setEntries(trip.checklist); }, [trip.checklist]);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function refresh(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setPending(true); setError(null);
    try {
      const response = await api.checklist(trip.id, nationality.trim());
      if (mounted.current) setEntries(response);
    } catch (cause) {
      if (mounted.current) setError(errorMessage(cause));
    } finally {
      if (mounted.current) setPending(false);
    }
  }
  return <section>
    <SectionHeading title={copy.checklist.heading}>{copy.checklist.description}</SectionHeading>
    <Notice>{copy.checklist.baseline}</Notice>
    <form className="nationality-form" onSubmit={refresh}>
      <div className="field"><label htmlFor="checklist-nationality">{copy.checklist.nationality}</label>
        <input id="checklist-nationality" value={nationality} onChange={event => setNationality(event.target.value.toUpperCase())}
          autoComplete="off" required minLength={2} maxLength={2} pattern="[A-Z]{2}" disabled={pending} /></div>
      <button type="submit" className="button button-secondary" disabled={pending}>{pending ? copy.common.loading : copy.checklist.update}</button>
    </form>
    <ErrorNotice message={error} />
    <ChecklistEntries entries={entries} facts={facts} today={today} checkable />
  </section>;
}
