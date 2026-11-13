import { lazy, Suspense, useMemo, useRef, useState } from "react";
import type { Availability, Fact, Hotel, TripPlan } from "../../../contracts/api";
import { copy } from "../i18n";
import { humanize, money, suitableRoom } from "../utils";
import { AvailabilityCalendar } from "./AvailabilityCalendar";
import { Icon } from "./Icon";
import { FactReferences, LoadingRows, Notice, Price, SectionHeading, type MoneyProps } from "./Shared";

const HotelMap = lazy(() => import("./HotelMap"));

interface HotelFilters {
  district: string; stars: number; minPrice: string; maxPrice: string; score: number;
  amenities: string[]; metro: number; family: boolean;
}
export const defaultHotelFilters: HotelFilters = {
  district: "", stars: 0, minPrice: "", maxPrice: "", score: 0, amenities: [], metro: 0, family: false,
};
export function filterHotels(hotels: Hotel[], filters: HotelFilters): Hotel[] {
  return hotels.filter(hotel =>
    (!filters.district || hotel.district === filters.district) &&
    hotel.stars >= filters.stars &&
    (!filters.minPrice || hotel.price_per_night_azn >= Number(filters.minPrice)) &&
    (!filters.maxPrice || hotel.price_per_night_azn <= Number(filters.maxPrice)) &&
    hotel.guest_score >= filters.score &&
    filters.amenities.every(amenity => hotel.amenities.includes(amenity)) &&
    (!filters.metro || (hotel.distance_to_metro_m !== null && hotel.distance_to_metro_m <= filters.metro)) &&
    (!filters.family || hotel.family_friendly),
  );
}

function HotelArt({ variant }: { variant: number }) {
  return <svg viewBox="0 0 180 180" className={`hotel-art hotel-art-${variant % 3}`} aria-hidden="true" focusable="false">
    <rect width="180" height="180" fill="var(--art-bg)" />
    <circle cx="145" cy="36" r="21" fill="var(--art-sun)" />
    <path d="M0 154h180v26H0z" fill="var(--art-ground)" />
    <path d={variant % 2 ? "M32 67h119v87H32zM25 66l67-25 67 25Z" : "M30 74h120v80H30zM24 74V61h18v13m13 0V61h18v13m13 0V61h18v13m13 0V61h18v13m9 0V61h18v13"}
      fill="var(--art-stone)" />
    <path d="M48 92h14v21H48zM82 92h14v21H82zM117 92h14v21h-14zM48 128h14v21H48zM117 128h14v21h-14zM81 155v-24a9 9 0 0 1 18 0v24"
      fill="var(--art-ink)" />
    <path d="M11 154v-38m149 39v-41" stroke="var(--art-ink)" strokeWidth="3" />
    <ellipse cx="11" cy="106" rx="13" ry="23" fill="var(--art-leaf)" />
    <ellipse cx="163" cy="99" rx="16" ry="29" fill="var(--art-leaf)" />
    <path d="M73 174h43" stroke="var(--art-stone)" strokeWidth="3" />
  </svg>;
}

function HotelDetail({ hotel, trip, busy, onSelect, onClose, currency, rates, facts, today }: MoneyProps & {
  hotel: Hotel; trip: TripPlan; busy: boolean; facts: Fact[]; today: string;
  onSelect: (hotelId: string, roomId: string) => Promise<boolean>; onClose: () => void;
}) {
  const guests = trip.search_params.adults + trip.search_params.children;
  const [room, setRoom] = useState(() => suitableRoom(hotel, guests));
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [chosen, setChosen] = useState(false);
  const selected = trip.selected_hotel_id === hotel.id;
  return <section className="hotel-detail" aria-labelledby="hotel-detail-title">
    <div className="detail-topline"><span className="fiction-label"><Icon name="info" />{copy.common.hotelDemo}</span>
      <button type="button" className="icon-button" onClick={onClose} aria-label={copy.common.close}><Icon name="close" /></button>
    </div>
    <header><p className="location-line"><Icon name="pin" />{hotel.district}</p>
      <h3 id="hotel-detail-title" tabIndex={-1}>{hotel.name}</h3><p>{hotel.description}</p>
    </header>
    <dl className="detail-facts">
      <div><dt>{copy.hotels.metroHeading}</dt><dd>{hotel.nearest_metro ?? copy.hotels.noMetro}
        {hotel.distance_to_metro_m !== null && <span> · {hotel.distance_to_metro_m} m</span>}</dd></div>
      <div><dt>{copy.hotels.airport}</dt><dd>{hotel.airport_stop}</dd></div>
      <div><dt>{copy.hotels.walk}</dt><dd>{hotel.walking_min_to_old_city !== null ? copy.common.minutes(hotel.walking_min_to_old_city) : copy.hotels.noWalk}</dd></div>
      <div><dt>{copy.hotels.coordinates}</dt><dd>{hotel.lat.toFixed(4)}, {hotel.lon.toFixed(4)}</dd></div>
    </dl>
    <h4>{copy.hotels.amenities}</h4><ul className="amenity-list">{hotel.amenities.map(amenity =>
      <li key={amenity}><Icon name="check" />{humanize(amenity)}</li>)}</ul>
    <h4>{copy.hotels.cancellation}</h4><p>{hotel.cancellation_policy}</p>
    <div className="field"><label htmlFor={`room-${hotel.id}`}>{copy.hotels.room}</label>
      <select id={`room-${hotel.id}`} value={room} disabled={busy} onChange={event => {
        setRoom(event.target.value); setAvailability(null); setChosen(false);
      }}>
        {!room && <option value="">{copy.hotels.noSuitableRoom}</option>}
        {hotel.room_types.map(type => <option key={type.id} value={type.id}>
          {type.name} · {copy.hotels.capacity(type.max_occupancy)}
        </option>)}
      </select><p className="field-help">{copy.hotels.upgradeNote}</p>
    </div>
    {room ? <AvailabilityCalendar hotelId={hotel.id} roomId={room} search={trip.search_params}
      currency={currency} rates={rates} onAvailability={setAvailability} /> : <Notice kind="warning">{copy.hotels.noSuitableRoom}</Notice>}
    <button className="button button-primary" type="button" disabled={busy || !room || !availability?.available || chosen}
      onClick={async () => { if (await onSelect(hotel.id, room)) setChosen(true); }}>
      <Icon name={chosen ? "check" : "bed"} />{busy ? copy.common.saving : chosen ? copy.hotels.selected : copy.hotels.select}
    </button>
    {selected && <p className="small-copy">{copy.hotels.selected}</p>}
    <details className="reference-details"><summary>{copy.common.sources}</summary>
      <FactReferences ids={hotel.grounding_refs} facts={facts} today={today} />
    </details>
  </section>;
}

export function Hotels({ trip, busy, onSelect, currency, rates, facts, today }: MoneyProps & {
  trip: TripPlan; busy: boolean; facts: Fact[]; today: string;
  onSelect: (hotelId: string, roomId: string) => Promise<boolean>;
}) {
  const [filters, setFilters] = useState<HotelFilters>(defaultHotelFilters);
  const [view, setView] = useState<"list" | "map">("list");
  const [detailId, setDetailId] = useState<string | null>(null);
  const detailContainer = useRef<HTMLDivElement>(null);
  const lastTrigger = useRef<HTMLElement | null>(null);
  const visible = useMemo(() => filterHotels(trip.hotels, filters), [trip.hotels, filters]);
  const districts = [...new Set(trip.hotels.map(hotel => hotel.district))];
  const amenities = [...new Set(trip.hotels.flatMap(hotel => hotel.amenities))];
  const detail = trip.hotels.find(hotel => hotel.id === detailId);
  const change = <K extends keyof HotelFilters>(key: K, value: HotelFilters[K]) => setFilters(current => ({ ...current, [key]: value }));
  function open(id: string) {
    if (document.activeElement instanceof HTMLElement) lastTrigger.current = document.activeElement;
    setDetailId(id);
    window.setTimeout(() => {
      detailContainer.current?.scrollIntoView({ block: "start", behavior: "instant" });
      detailContainer.current?.querySelector<HTMLElement>("h3")?.focus();
    }, 0);
  }

  return <div className="hotel-explorer">
    <SectionHeading title={copy.hotels.heading}>{copy.hotels.description}</SectionHeading>
    <Notice>{copy.common.hotelDemo}</Notice>
    <details className="filter-panel" open>
      <summary>{copy.hotels.filters}</summary>
      <div className="filter-grid">
        <div className="field"><label htmlFor="filter-district">{copy.hotels.district}</label>
          <select id="filter-district" value={filters.district} onChange={event => change("district", event.target.value)}>
            <option value="">{copy.common.all}</option>{districts.map(district => <option key={district}>{district}</option>)}
          </select></div>
        <div className="field"><label htmlFor="filter-stars">{copy.hotels.stars}</label>
          <select id="filter-stars" value={filters.stars} onChange={event => change("stars", Number(event.target.value))}>
            <option value="0">{copy.hotels.anyStars}</option>{[3, 4, 5].map(stars => <option key={stars} value={stars}>{copy.hotels.starLabel(stars)}</option>)}
          </select></div>
        <div className="field"><label htmlFor="filter-min-price">{copy.hotels.minPrice}</label>
          <input id="filter-min-price" type="number" min="0" value={filters.minPrice} onChange={event => change("minPrice", event.target.value)} /></div>
        <div className="field"><label htmlFor="filter-max-price">{copy.hotels.maxPrice}</label>
          <input id="filter-max-price" type="number" min="0" value={filters.maxPrice} onChange={event => change("maxPrice", event.target.value)} /></div>
        <div className="field"><label htmlFor="filter-score">{copy.hotels.score}</label>
          <select id="filter-score" value={filters.score} onChange={event => change("score", Number(event.target.value))}>
            <option value="0">{copy.hotels.anyScore}</option>{[7, 8, 9].map(score => <option key={score} value={score}>{score}+</option>)}
          </select></div>
        <div className="field"><label htmlFor="filter-metro">{copy.hotels.metro}</label>
          <select id="filter-metro" value={filters.metro} onChange={event => change("metro", Number(event.target.value))}>
            <option value="0">{copy.hotels.anyMetro}</option>{[300, 500, 1000, 2000].map(metres =>
              <option key={metres} value={metres}>{copy.hotels.metres(metres)}</option>)}
          </select></div>
      </div>
      <p className="small-copy">{copy.hotels.priceHelp}{filters.maxPrice && rates &&
        ` (${money(Number(filters.maxPrice), "GBP", rates)})`}</p>
      <fieldset className="amenity-filters"><legend>{copy.hotels.amenities}</legend>
        <div className="checkbox-group">{amenities.map(amenity => <label key={amenity}>
          <input type="checkbox" checked={filters.amenities.includes(amenity)}
            onChange={() => change("amenities", filters.amenities.includes(amenity) ? filters.amenities.filter(item => item !== amenity) : [...filters.amenities, amenity])} />
          {humanize(amenity)}
        </label>)}</div>
      </fieldset>
      <div className="filter-footer"><label className="checkbox-label"><input type="checkbox" checked={filters.family} onChange={event => change("family", event.target.checked)} />
        {copy.hotels.family}</label>
        <button type="button" className="text-button" onClick={() => setFilters(defaultHotelFilters)}>{copy.hotels.reset}</button>
      </div>
    </details>
    <div className="results-toolbar">
      <p role="status">{copy.hotels.results(visible.length)}</p>
      <div className="segmented-control" aria-label={copy.hotels.mapLabel}>
        <button type="button" aria-pressed={view === "list"} onClick={() => setView("list")}><Icon name="list" />{copy.hotels.list}</button>
        <button type="button" aria-pressed={view === "map"} onClick={() => setView("map")}><Icon name="map" />{copy.hotels.map}</button>
      </div>
    </div>
    <div ref={detailContainer} className="detail-anchor">
      {detail && <HotelDetail key={detail.id} hotel={detail} trip={trip} busy={busy} onSelect={onSelect}
        onClose={() => {
          setDetailId(null);
          window.setTimeout(() => lastTrigger.current?.focus(), 0);
        }} currency={currency} rates={rates} facts={facts} today={today} />}
    </div>
    {view === "map" && <Suspense fallback={<LoadingRows />}><HotelMap hotels={visible} onSelect={open} /></Suspense>}
    {!visible.length && <p className="empty-state">{copy.common.empty}</p>}
    <ol className="hotel-list">
      {visible.map((hotel, index) => <li key={hotel.id}>
        <article className={`hotel-row ${trip.selected_hotel_id === hotel.id ? "is-selected" : ""}`}>
          <div className="hotel-art-container"><HotelArt variant={index} />
            {view === "map" && <span className="map-list-number">{index + 1}</span>}</div>
          <div className="hotel-row-content">
            <div className="hotel-meta"><span className="location-line"><Icon name="pin" />{hotel.district}</span>
              <span aria-label={copy.hotels.starsLabel(hotel.stars)}><Icon name="star" />{hotel.stars}</span></div>
            <h3><button type="button" className="heading-button" onClick={() => open(hotel.id)}>{hotel.name}</button></h3>
            <p className="small-copy">{hotel.nearest_metro ?? copy.hotels.noMetro}
              {hotel.distance_to_metro_m !== null ? ` · ${hotel.distance_to_metro_m} m` : ""}</p>
            <div className="hotel-row-tags"><span className="guest-score" title={copy.hotels.scoreLabel}>{hotel.guest_score.toFixed(1)}<small>/ 10</small></span>
              <span className="small-copy">{copy.hotels.scoreLabel}</span>
              {trip.selected_hotel_id === hotel.id && <span className="selected-label"><Icon name="check" />{copy.hotels.selected}</span>}
            </div>
            <p className="fiction-label">{copy.common.hotelDemo}</p>
          </div>
          <div className="hotel-price">
            <strong><Price amount={hotel.price_per_night_azn} currency={currency} rates={rates} secondary /></strong>
            <span className="small-copy">{copy.common.perNight}</span>
            {hotel.rooms_required !== undefined && <span className="hotel-room-count">{copy.hotels.roomCount(hotel.rooms_required)}</span>}
            {hotel.available === false && <span className="stale-label">{copy.hotels.soldOut}</span>}
            {currency !== "GBP" && rates && <span className="small-copy">{money(hotel.price_per_night_azn, "GBP", rates)} / {copy.common.perNight}</span>}
            <span className="small-copy"><Price amount={hotel.price_total_azn} currency={currency} rates={rates} /> {copy.common.total.toLowerCase()}</span>
            <button type="button" className="button button-secondary" onClick={() => open(hotel.id)}>{copy.hotels.details}<Icon name="arrow" /></button>
          </div>
        </article>
      </li>)}
    </ol>
  </div>;
}
