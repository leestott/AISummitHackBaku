import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import type { Booking, Currency, Fact, Meta, SearchParams, TripPlan } from "../../contracts/api";
import { api, errorMessage, isAborted } from "./api";
import { copy } from "./i18n";
import { activeHold, currencies, formatDate, suitableRoom } from "./utils";
import { useTrip } from "./useTrip";
import skyline from "./assets/baku-skyline.svg";
import { AboutData } from "./components/AboutData";
import { Activities } from "./components/Activities";
import { Assistant } from "./components/Assistant";
import { BookingFlow } from "./components/BookingFlow";
import { Flights } from "./components/Flights";
import { Hotels } from "./components/Hotels";
import { Icon, type IconName } from "./components/Icon";
import { SearchForm } from "./components/SearchForm";
import { ErrorNotice, FactReferences, Notice, Price } from "./components/Shared";
import { Checklist, Transport } from "./components/TravelGuidance";

type Page = "home" | "trip" | "data" | "booking";
type Tab = keyof typeof copy.trip.tabs;
const tabs: { id: Tab; icon: IconName }[] = [
  { id: "flights", icon: "plane" }, { id: "hotels", icon: "bed" }, { id: "activities", icon: "compass" },
  { id: "transport", icon: "bus" }, { id: "checklist", icon: "checklist" },
];

function TripSummary({ trip, currency, disabled, onBook }: { trip: TripPlan; currency: Currency; disabled: boolean; onBook: () => void }) {
  const hotel = trip.hotels.find(item => item.id === trip.selected_hotel_id);
  const flight = trip.flights.find(item => item.id === trip.selected_flight_id);
  return <aside className="trip-summary" aria-labelledby="summary-title">
    <h2 id="summary-title">{copy.trip.summary}</h2>
    <div className="summary-destination"><Icon name="compass" /><div><strong>{copy.trip.to}</strong><span>{copy.trip.from} {trip.search_params.origin}</span></div></div>
    <div className="summary-detail"><Icon name="calendar" /><span>{formatDate(trip.search_params.arrival, true)} – {formatDate(trip.search_params.departure, true)}
      <small>{copy.common.nights(trip.nights)}</small></span></div>
    <div className="summary-detail"><Icon name="people" /><span>{copy.common.guests(trip.search_params.adults + trip.search_params.children)}
      <small>{copy.search.budgets[trip.search_params.budget]} · {copy.search.paces[trip.search_params.pace]}</small></span></div>
    {hotel && <div className="summary-hotel"><span className="small-copy">{copy.trip.selectedHotel}</span><strong>{hotel.name}</strong>
      {hotel.rooms_required !== undefined && <span className="small-copy">{copy.hotels.roomCount(hotel.rooms_required)}</span>}
      <span className="fiction-label">{copy.common.hotelDemo}</span></div>}
    {flight && <p className="small-copy">{copy.trip.plannedFlight}: {flight.carrier}</p>}
    <dl className="summary-totals">
      <div><dt>{copy.trip.hotel}</dt><dd><Price amount={trip.totals.hotel_azn} currency={currency} rates={trip.exchange_rates} /></dd></div>
      <div><dt>{copy.trip.activities}</dt><dd><Price amount={trip.totals.activities_azn} currency={currency} rates={trip.exchange_rates} /></dd></div>
      <div><dt>{copy.trip.transport}</dt><dd><Price amount={trip.totals.transport_azn} currency={currency} rates={trip.exchange_rates} /></dd></div>
    </dl>
    <div className="summary-total" aria-live="polite" aria-atomic="true"><span>{copy.trip.total}</span>
      <strong><Price amount={trip.totals.total_azn} currency={currency} rates={trip.exchange_rates} secondary /></strong></div>
    <p className="small-copy">{copy.trip.excludes}</p><p className="small-copy">{copy.trip.roomNote}</p>
    <button type="button" className="button button-primary" disabled={disabled || !hotel} onClick={onBook}>{copy.trip.booking}<Icon name="arrow" /></button>
    <p className="small-copy summary-booking-note"><Icon name="shield" />{copy.trip.bookingHelp}</p>
  </aside>;
}

export function App() {
  const [page, setPage] = useState<Page>("home");
  const [tab, setTab] = useState<Tab>("hotels");
  const [currency, setCurrency] = useState<Currency>("AZN");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [factsError, setFactsError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [booking, setBooking] = useState<Booking | null>(null);
  const [roomChoice, setRoomChoice] = useState<{ hotelId: string; roomId: string } | null>(null);
  const main = useRef<HTMLElement>(null);
  const previousPage = useRef<Page>(page);
  const { trip, busy, error, status, search, update, editItinerary } = useTrip();
  const rates = trip?.exchange_rates ?? meta?.exchange_rates;
  const today = meta?.today ?? new Date().toISOString().slice(0, 10);
  const holding = activeHold(booking);
  const lockTrip = busy || holding;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setMetaError(null); setFactsError(null);
    const metadata = api.meta(controller.signal).then(result => {
      if (!controller.signal.aborted) setMeta(result);
    }).catch(cause => {
      if (!isAborted(cause) && !controller.signal.aborted) setMetaError(errorMessage(cause));
    });
    const grounding = api.facts(controller.signal).then(result => {
      if (!controller.signal.aborted) setFacts(result);
    }).catch(cause => {
      if (!isAborted(cause) && !controller.signal.aborted) setFactsError(errorMessage(cause));
    });
    void Promise.allSettled([metadata, grounding]).then(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reload]);

  useEffect(() => {
    if (previousPage.current === page) return;
    previousPage.current = page;
    main.current?.querySelector<HTMLElement>("h1")?.focus();
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [page]);

  async function performSearch(params: SearchParams) {
    if (holding) return false;
    const succeeded = await search(params);
    if (succeeded) {
      setRoomChoice(null); setBooking(null); setTab("hotels"); setPage("trip");
    }
    return succeeded;
  }
  async function selectHotel(hotelId: string, roomId: string) {
    if (lockTrip || !trip) return false;
    const saved = trip.selected_hotel_id === hotelId || await update({ hotel_id: hotelId });
    if (saved) setRoomChoice({ hotelId, roomId });
    return saved;
  }
  function openBasket() {
    if (!trip || busy) return;
    if (booking && !activeHold(booking) && booking.state !== "confirmed_simulated") setBooking(null);
    setPage("booking");
  }
  function selectTab(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let target: number | null = null;
    if (event.key === "ArrowRight") target = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft") target = (index + tabs.length - 1) % tabs.length;
    if (event.key === "Home") target = 0;
    if (event.key === "End") target = tabs.length - 1;
    if (target === null) return;
    event.preventDefault(); setTab(tabs[target].id);
    document.getElementById(`tab-${tabs[target].id}`)?.focus();
  }
  function guide() {
    if (page !== "home" && page !== "trip") setPage(trip ? "trip" : "home");
    window.setTimeout(() => {
      document.getElementById("local-guide")?.scrollIntoView({ block: "start", behavior: "instant" });
      document.getElementById("assistant-message")?.focus({ preventScroll: true });
    }, 0);
  }
  const month = Number(today.slice(5, 7));
  const seasonal = [12, 1, 2].includes(month) ? copy.hero.winter : month <= 5 ? copy.hero.spring : month <= 8 ? copy.hero.summer : copy.hero.autumn;
  const selectedHotel = trip?.hotels.find(hotel => hotel.id === trip.selected_hotel_id);
  const selectedRoom = trip && roomChoice?.hotelId === selectedHotel?.id ? roomChoice?.roomId ?? "" :
    suitableRoom(selectedHotel, trip ? trip.search_params.adults + trip.search_params.children : 0);

  return <>
    <a className="skip-link" href="#main-content">{copy.common.skip}</a>
    <div className="demo-ribbon"><Icon name="shield" /><strong>{copy.common.demo}</strong><span>{copy.common.demoDetail}</span></div>
    <header className="site-header page-width">
      <button className="brand-button" type="button" onClick={() => setPage("home")} aria-label={`${copy.common.brand} · ${copy.nav.explore}`}>
        <span className="brand-icon"><Icon name="compass" /></span><span><strong>{copy.common.brand}</strong><small>{copy.common.brandSubtitle}</small></span>
      </button>
      <nav aria-label={copy.common.brand}>
        <button type="button" className="nav-link" aria-current={page === "home" ? "page" : undefined} onClick={() => setPage("home")}>{copy.nav.explore}</button>
        {trip && <button type="button" className="nav-link" aria-current={page === "trip" ? "page" : undefined} onClick={() => setPage("trip")}>{copy.nav.trip}</button>}
        <button type="button" className="nav-link" aria-current={page === "data" ? "page" : undefined} onClick={() => setPage("data")}>{copy.nav.data}</button>
      </nav>
      <div className="header-controls">
        <span className="language-label" title={copy.common.languageNote} lang="en">{copy.common.english}</span>
        <label className="currency-control"><span className="sr-only">{copy.common.currency}</span>
          <select aria-label={copy.common.currency} value={rates ? currency : "AZN"} disabled={!rates}
            onChange={event => { const choice = currencies.find(value => value === event.target.value); if (choice) setCurrency(choice); }}>
            {currencies.map(value => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
      </div>
    </header>
    <div className="rate-strip page-width"><span>{rates ? copy.common.rate(formatDate(rates.as_of)) : copy.common.unavailableRate}</span>
      <button type="button" className="text-button" onClick={guide}><Icon name="chat" />{copy.nav.assistant}</button></div>
    <div className="live-status sr-only" role="status" aria-live="polite" aria-atomic="true">{busy ? copy.common.saving : status}</div>
    <main id="main-content" ref={main} className={page === "trip" ? "has-mobile-summary" : ""}>
      {(metaError || factsError) && <div className="service-alerts page-width">
        <ErrorNotice message={[
          metaError ? `${copy.common.metadataError} ${metaError}` : "",
          factsError ? `${copy.common.factsError} ${factsError}` : "",
        ].filter(Boolean).join("\n\n")} onRetry={() => setReload(value => value + 1)} />
      </div>}
      {page === "home" && <>
        <section className="hero page-width" aria-labelledby="hero-title">
          <div className="hero-copy"><span className="hero-location"><span />{copy.hero.location}</span>
            <h1 id="hero-title" tabIndex={-1}>{copy.hero.heading.split("\n").map(line => <span key={line}>{line}</span>)}</h1>
            <p>{copy.hero.description}</p>
            <a className="hero-link" href="#plan-a-trip">{copy.hero.searchTitle}<Icon name="arrow" /></a>
          </div>
          <figure className="hero-art"><img src={skyline} alt={copy.hero.skylineAlt} width="1100" height="730" fetchPriority="high" />
            <figcaption>{copy.hero.caption}</figcaption></figure>
        </section>
        <div className="page-width">
          {holding && <Notice><p>{copy.trip.holding}</p><button type="button" className="text-button" onClick={openBasket}>{copy.nav.resume}</button></Notice>}
          <SearchForm meta={meta} initial={trip?.search_params} busy={busy} error={error} locked={holding} onSearch={performSearch} />
          <section className="seasonal-section"><div className="seasonal-symbol"><Icon name="sun" /></div>
            <div><h2>{copy.hero.seasonalTitle}</h2><p>{seasonal}</p><small>{copy.hero.seasonalBaseline}</small></div>
            <div className="seasonal-route" aria-hidden="true"><svg viewBox="0 0 220 120" fill="none"><path d="M20 94c40-65 47 45 91-17s60-57 93-47" stroke="currentColor" strokeWidth="2" strokeDasharray="5 6" /><circle cx="20" cy="94" r="6" fill="currentColor" /><circle cx="204" cy="30" r="6" fill="currentColor" /></svg></div>
          </section>
          <section className="approach-section"><h2>{copy.hero.approachTitle}</h2><p>{copy.hero.approachBody}</p>
            <button type="button" className="text-button" onClick={() => setPage("data")}>{copy.nav.data}<Icon name="arrow" /></button></section>
          <Assistant meta={meta} tripId={trip?.id} facts={facts} today={today} />
        </div>
      </>}
      {page === "trip" && trip && <div className="page-width">
        <header className="trip-intro"><div><span className="small-copy">{copy.trip.planning}</span><h1 tabIndex={-1}>{copy.trip.heading}</h1><p>{copy.trip.subtitle}</p></div>
          <button type="button" className="button button-secondary" onClick={() => setPage("home")} disabled={busy}>{copy.nav.newTrip}<Icon name="arrow" /></button></header>
        <ErrorNotice message={error} />
        {holding && <Notice><p>{copy.trip.holding}</p><button type="button" className="text-button" onClick={openBasket}>{copy.nav.resume}</button></Notice>}
        {trip.notices.length > 0 && <details className="trip-notices"><summary><Icon name="info" />{copy.trip.notices}</summary>
          <ul>{trip.notices.map((notice, index) => <li key={index}>{notice}</li>)}</ul>
          <FactReferences ids={[...new Set(trip.checklist.flatMap(item => item.fact_refs))]} facts={facts} today={today} />
        </details>}
        <div className="trip-layout">
          <div className="trip-workspace">
            <div className="trip-tabs" role="tablist" aria-label={copy.trip.tabLabel}>
              {tabs.map((item, index) => <button key={item.id} id={`tab-${item.id}`} role="tab" type="button" aria-selected={tab === item.id}
                aria-controls={`panel-${item.id}`} tabIndex={tab === item.id ? 0 : -1} onClick={() => setTab(item.id)} onKeyDown={event => selectTab(event, index)}>
                <Icon name={item.icon} />{copy.trip.tabs[item.id]}</button>)}
            </div>
            <div className="trip-panel" id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} tabIndex={0}>
              {tab === "flights" && <Flights trip={trip} facts={facts} today={today} busy={lockTrip} onSelect={flightId => update({ flight_id: flightId })} currency={currency} rates={rates} />}
              {tab === "hotels" && <Hotels trip={trip} busy={lockTrip} onSelect={selectHotel} currency={currency} rates={rates} facts={facts} today={today} />}
              {tab === "activities" && <Activities trip={trip} busy={lockTrip} onEdit={editItinerary} onUpdate={update} currency={currency} rates={rates} facts={facts} today={today} />}
              {tab === "transport" && <Transport trip={trip} currency={currency} rates={rates} facts={facts} today={today} />}
              {tab === "checklist" && <Checklist trip={trip} facts={facts} today={today} />}
            </div>
          </div>
          <TripSummary trip={trip} currency={currency} disabled={busy} onBook={openBasket} />
        </div>
        <Assistant key={trip.id} meta={meta} tripId={trip.id} facts={facts} today={today} />
        <div className="mobile-summary"><div><span>{copy.trip.total}</span><strong><Price amount={trip.totals.total_azn} currency={currency} rates={rates} /></strong></div>
          <button type="button" className="button button-primary" disabled={busy || !selectedHotel} onClick={openBasket}>{copy.trip.booking}<Icon name="arrow" /></button></div>
      </div>}
      {page === "data" && <AboutData facts={facts} today={today} error={factsError} loading={loading} onRetry={() => setReload(value => value + 1)} />}
      {page === "booking" && trip && <BookingFlow key={trip.id} trip={trip} booking={booking} onBooking={setBooking} onClose={() => setPage("trip")}
        initialRoomId={selectedRoom} currency={currency} rates={rates} facts={facts} today={today} />}
    </main>
    <footer className={`site-footer page-width ${page === "trip" ? "footer-with-summary" : ""}`}>
      <div><span className="footer-brand"><Icon name="compass" />{copy.common.brand}</span><p>{copy.hero.footnote}</p></div>
      <div><button type="button" className="text-button" onClick={() => setPage("data")}>{copy.nav.data}</button><p>{copy.common.languageNote}</p></div>
    </footer>
  </>;
}
