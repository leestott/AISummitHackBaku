import { useRef, useState } from "react";
import type { Activity, Fact, ItineraryDay, TripPlan } from "../../../contracts/api";
import type { ItineraryPatch, TripPatch } from "../api";
import { copy } from "../i18n";
import { duration, formatDate, humanize, itineraryIds } from "../utils";
import { Icon } from "./Icon";
import { FactReferences, Notice, Price, SectionHeading, type MoneyProps } from "./Shared";

export function moveItem(days: ItineraryDay[], date: string, from: number, to: number): ItineraryPatch {
  return {
    days: days.map(day => {
      const ids = day.items.map(item => item.activity_id);
      if (day.date === date && from >= 0 && to >= 0 && from < ids.length && to < ids.length) {
        const [item] = ids.splice(from, 1);
        ids.splice(to, 0, item);
      }
      return { date: day.date, activity_ids: ids };
    }),
  };
}

function ActivityRow({ activity, trip, busy, onAdd, currency, rates, facts, today }: MoneyProps & {
  activity: Activity; trip: TripPlan; busy: boolean; facts: Fact[]; today: string;
  onAdd: (activityId: string, date: string) => Promise<boolean>;
}) {
  const [date, setDate] = useState(trip.itinerary_days[0]?.date ?? "");
  const included = itineraryIds(trip).includes(activity.id);
  return <article className="activity-row">
    <div className="activity-number"><Icon name={activity.indoor ? "bed" : "sun"} /></div>
    <div className="activity-main">
      <div className="activity-meta"><span>{humanize(activity.destination_id)}</span><span>{duration(activity.duration_min)}</span>
        <span>{activity.indoor ? copy.activities.indoor : copy.activities.outdoor}</span></div>
      <h4>{activity.name}</h4><p>{activity.description}</p>
      <p className="fiction-label">{copy.activities.fictional}</p>
      <div className="activity-getting-there"><Icon name="walk" /><div><strong>{copy.activities.how}</strong><p>{activity.how_to_get_there}</p></div></div>
      <p className="small-copy">{copy.activities.opening}: {activity.opening_hours.open}–{activity.opening_hours.close} · {copy.activities.capacity(activity.capacity_per_slot)}</p>
      <details className="score-details"><summary>{copy.activities.score}<span className="score-total">{activity.score.total.toFixed(2)}</span></summary>
        <p>{copy.activities.scoreDescription}</p>
        <dl className="score-breakdown">{Object.entries(copy.activities.scoreLabels).map(([key, label]) => {
          const scoreKey = key as keyof Activity["score"];
          return <div key={key}><dt>{label}</dt><dd>{activity.score[scoreKey].toFixed(2)}</dd></div>;
        })}</dl>
      </details>
      <FactReferences ids={activity.grounding_refs} facts={facts} today={today} />
    </div>
    <div className="activity-actions">
      <strong><Price amount={activity.price_azn} currency={currency} rates={rates} secondary /></strong>
      <span className="small-copy">{copy.common.perPerson}</span>
      {included ? <span className="selected-label"><Icon name="check" />{copy.activities.inPlan}</span> : <>
        <label htmlFor={`activity-day-${activity.id}`}>{copy.activities.addDay}</label>
        <select id={`activity-day-${activity.id}`} value={date} disabled={busy} onChange={event => setDate(event.target.value)}>
          {!date && <option value="">{copy.activities.dateSelect}</option>}
          {trip.itinerary_days.map(day => <option key={day.date} value={day.date}>{formatDate(day.date, true)}</option>)}
        </select>
        <button type="button" className="button button-secondary" disabled={busy || !date} onClick={() => void onAdd(activity.id, date)}>
          {copy.activities.add}<Icon name="arrow" />
        </button>
      </>}
    </div>
  </article>;
}

export function Activities({ trip, busy, onEdit, onUpdate, currency, rates, facts, today }: MoneyProps & {
  trip: TripPlan; busy: boolean; facts: Fact[]; today: string;
  onEdit: (patch: ItineraryPatch) => Promise<boolean>; onUpdate: (patch: TripPatch) => Promise<boolean>;
}) {
  const [category, setCategory] = useState("");
  const [destination, setDestination] = useState("");
  const [setting, setSetting] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const drag = useRef<{ date: string; index: number } | null>(null);
  const categories = [...new Set(trip.activities.flatMap(activity => activity.categories))];
  const destinations = [...new Set(trip.activities.map(activity => activity.destination_id))];
  const visible = trip.activities.filter(activity =>
    (!category || activity.categories.includes(category)) &&
    (!destination || activity.destination_id === destination) &&
    (!setting || (setting === "indoor" ? activity.indoor : !activity.indoor)) &&
    (!maxPrice || activity.price_azn <= Number(maxPrice)),
  );

  async function reorder(date: string, from: number, to: number) {
    if (busy) return;
    await onEdit(moveItem(trip.itinerary_days, date, from, to));
  }
  async function remove(date: string, index: number) {
    if (busy) return;
    const succeeded = await onEdit({
      days: trip.itinerary_days.map(day => ({
        date: day.date,
        activity_ids: day.items.filter((_, itemIndex) => day.date !== date || itemIndex !== index).map(item => item.activity_id),
      })),
    });
    if (succeeded) window.setTimeout(() => document.getElementById(`day-${date}`)?.focus(), 0);
  }
  async function add(id: string, date: string) {
    if (busy) return false;
    return onEdit({
      days: trip.itinerary_days.map(day => ({
        date: day.date,
        activity_ids: [...day.items.map(item => item.activity_id), ...(day.date === date ? [id] : [])],
      })),
    });
  }

  return <section>
    <SectionHeading title={copy.activities.heading}>{copy.activities.description}</SectionHeading>
    <Notice>{copy.common.activityDemo}</Notice>
    <div className="itinerary-heading"><h3>{copy.activities.itinerary}</h3>
      <div className="field"><label htmlFor="itinerary-pace">{copy.activities.pace}</label>
        <select id="itinerary-pace" value={trip.search_params.pace} disabled={busy} aria-describedby="pace-warning"
          onChange={event => {
            const pace = event.target.value;
            if (pace === "relaxed" || pace === "balanced" || pace === "packed") void onUpdate({ pace });
          }}>
          {Object.entries(copy.search.paces).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>
    </div>
    <p className="small-copy" id="pace-warning">{copy.activities.paceNote}</p>
    <p className="small-copy" id="drag-help">{copy.activities.dragHelp}</p>
    {busy && <p role="status" className="inline-pending">{copy.activities.saving}</p>}
    <div className="itinerary-days">
      {trip.itinerary_days.map((day, dayIndex) => <section className="itinerary-day" key={day.date} aria-labelledby={`day-${day.date}`}>
        <header className="day-header"><span className="day-index">{String(dayIndex + 1).padStart(2, "0")}</span>
          <div><h4 id={`day-${day.date}`} tabIndex={-1}>{formatDate(day.date)}</h4><p>{day.title}</p></div>
          <span className="day-total"><Price amount={day.total_azn} currency={currency} rates={rates} /></span>
        </header>
        {!day.items.length && <p className="empty-day">{copy.activities.emptyDay}</p>}
        <ol className="timeline" aria-describedby="drag-help">
          {day.items.map((item, index) => <li className="timeline-item" key={`${item.activity_id}-${index}`} draggable={!busy}
            onDragStart={event => {
              if (busy) { event.preventDefault(); return; }
              drag.current = { date: day.date, index };
              event.dataTransfer.effectAllowed = "move";
              event.dataTransfer.setData("text/plain", item.activity_id);
            }}
            onDragEnd={() => { drag.current = null; }}
            onDragOver={event => { if (!busy && drag.current?.date === day.date) { event.preventDefault(); event.dataTransfer.dropEffect = "move"; } }}
            onDrop={event => {
              event.preventDefault();
              const source = drag.current;
              drag.current = null;
              if (source?.date === day.date && source.index !== index && !busy) void reorder(day.date, source.index, index);
            }}>
            <div className="timeline-time"><Icon name="drag" /><time>{item.start_time}</time><span>{item.end_time}</span></div>
            <div className="timeline-main"><h5>{item.title}</h5>
              <p className="small-copy">{copy.activities.travel(item.travel_minutes)} · {item.transport_note}</p>
              <span className="fiction-label">{copy.activities.fictional}</span>
              <Price amount={item.price_azn} currency={currency} rates={rates} />
            </div>
            <div className="timeline-controls">
              <button type="button" className="icon-button" aria-label={copy.activities.moveUp(item.title)} disabled={busy || index === 0}
                onClick={() => void reorder(day.date, index, index - 1)}><Icon name="up" /></button>
              <button type="button" className="icon-button" aria-label={copy.activities.moveDown(item.title)} disabled={busy || index === day.items.length - 1}
                onClick={() => void reorder(day.date, index, index + 1)}><Icon name="down" /></button>
              <button type="button" className="icon-button" aria-label={copy.activities.remove(item.title)} disabled={busy}
                onClick={() => void remove(day.date, index)}><Icon name="trash" /></button>
            </div>
          </li>)}
        </ol>
      </section>)}
    </div>
    <h3 className="explorer-heading">{copy.activities.explorer}</h3>
    <div className="filter-grid activity-filters">
      <div className="field"><label htmlFor="activity-category">{copy.activities.category}</label>
        <select id="activity-category" value={category} onChange={event => setCategory(event.target.value)}>
          <option value="">{copy.common.all}</option>{categories.map(value => <option key={value} value={value}>{humanize(value)}</option>)}
        </select></div>
      <div className="field"><label htmlFor="activity-destination">{copy.activities.destination}</label>
        <select id="activity-destination" value={destination} onChange={event => setDestination(event.target.value)}>
          <option value="">{copy.common.all}</option>{destinations.map(value => <option key={value} value={value}>{humanize(value)}</option>)}
        </select></div>
      <div className="field"><label htmlFor="activity-setting">{copy.activities.setting}</label>
        <select id="activity-setting" value={setting} onChange={event => setSetting(event.target.value)}>
          <option value="">{copy.common.all}</option><option value="indoor">{copy.activities.indoor}</option><option value="outdoor">{copy.activities.outdoor}</option>
        </select></div>
      <div className="field"><label htmlFor="activity-price">{copy.activities.maxPrice}</label>
        <input id="activity-price" type="number" min="0" value={maxPrice} onChange={event => setMaxPrice(event.target.value)} /></div>
    </div>
    {!visible.length && <p className="empty-state">{copy.common.empty}</p>}
    <div className="activity-list">{visible.map(activity => <ActivityRow key={activity.id} activity={activity} trip={trip} busy={busy}
      onAdd={add} currency={currency} rates={rates} facts={facts} today={today} />)}</div>
  </section>;
}
