import { useEffect, useRef, useState, type FormEvent } from "react";
import type { Availability, Booking, Fact, TripPlan } from "../../../contracts/api";
import { api, errorMessage } from "../api";
import { copy } from "../i18n";
import { activeHold, formatDate, humanize, itineraryIds, remainingHold, suitableRoom } from "../utils";
import { AvailabilityCalendar } from "./AvailabilityCalendar";
import { Icon } from "./Icon";
import { ErrorNotice, Notice, Price, type MoneyProps } from "./Shared";
import { ChecklistEntries } from "./TravelGuidance";

type Step = 0 | 1 | 2 | 3 | 4;
function stepFor(booking: Booking | null): Step {
  if (!booking) return 0;
  if (booking.state === "confirmed_simulated") return 4;
  if (booking.state === "details_captured") return 2;
  if (booking.state === "payment_simulated") return 3;
  return 1;
}

export function BookingLines({ booking, currency, rates }: MoneyProps & { booking: Booking }) {
  return <section className="booking-lines" aria-label={copy.booking.serverPrice}>
    <h3>{copy.booking.serverPrice}</h3>
    <div className="table-scroll" tabIndex={0} role="region" aria-label={copy.booking.serverPrice}>
      <table><thead><tr><th scope="col">{copy.booking.item}</th><th scope="col">{copy.booking.quantity}</th>
        <th scope="col">{copy.booking.price}</th></tr></thead>
        <tbody>{booking.items.map(item => <tr key={item.id}>
          <th scope="row">{item.name}<small>{formatDate(item.date)}</small></th><td>{item.quantity}</td>
          <td><Price amount={item.total_azn} currency={currency} rates={rates} /></td>
        </tr>)}</tbody>
        <tfoot><tr><th scope="row" colSpan={2}>{copy.common.total}</th>
          <td><Price amount={booking.total_azn} currency={currency} rates={rates} secondary /></td></tr></tfoot>
      </table>
    </div>
  </section>;
}

export function BookingFlow({ trip, booking, onBooking, onClose, initialRoomId, currency, rates, facts, today }: MoneyProps & {
  trip: TripPlan; booking: Booking | null; onBooking: (booking: Booking | null) => void; onClose: () => void;
  initialRoomId: string; facts: Fact[]; today: string;
}) {
  const hotel = trip.hotels.find(item => item.id === trip.selected_hotel_id);
  const guests = trip.search_params.adults + trip.search_params.children;
  const [step, setStep] = useState<Step>(() => stepFor(booking));
  const [roomId, setRoomId] = useState(() =>
    hotel?.room_types.some(room => room.id === initialRoomId)
      ? initialRoomId : suitableRoom(hotel, guests));
  const [selectedActivities, setSelectedActivities] = useState(() => itineraryIds(trip));
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [nationality, setNationality] = useState("GB");
  const [passportExpiry, setPassportExpiry] = useState("");
  const [visaExpiry, setVisaExpiry] = useState("");
  const [card, setCard] = useState("4242424242424242");
  const [agreed, setAgreed] = useState(false);
  const [now, setNow] = useState(Date.now);
  const lock = useRef(false);
  const expiryChecked = useRef<string | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const remaining = booking ? remainingHold(booking, now) : 0;
  const elapsed = activeHold(booking) && (!Number.isFinite(remaining) || remaining <= 0);
  const terminal = booking?.state === "expired" || booking?.state === "cancelled_simulated";
  const mismatch = booking !== null && booking.trip_plan_id !== trip.id;
  const itineraryActivities = trip.activities.filter(activity => itineraryIds(trip).includes(activity.id));
  const disabled = pending || elapsed || terminal || mismatch;

  useEffect(() => {
    if (!activeHold(booking)) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [booking]);

  useEffect(() => {
    if (!booking || !elapsed || pending || lock.current || expiryChecked.current === booking.reference) return;
    expiryChecked.current = booking.reference;
    let disposed = false;
    api.booking(booking.reference).then(result => {
      if (!disposed) onBooking(result);
    }).catch(cause => { if (!disposed) setError(errorMessage(cause)); });
    return () => { disposed = true; };
  }, [booking, elapsed, pending, onBooking]);

  useEffect(() => { heading.current?.focus(); }, [step]);

  async function run(action: () => Promise<Booking>, next?: Step) {
    if (lock.current) return;
    lock.current = true; setPending(true); setError(null);
    try {
      const result = await action();
      onBooking(result);
      setStep(result.state === "confirmed_simulated" ? 4 : next !== undefined && next < 4 ? next : stepFor(result));
      setConfirmCancel(false);
      setNow(Date.now());
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      lock.current = false; setPending(false);
    }
  }

  async function create() {
    if (!hotel || !roomId || !availability?.available || pending) return;
    await run(() => api.createBooking({
      trip_plan_id: trip.id,
      hotel_id: hotel.id,
      room_type_id: roomId,
      activity_ids: selectedActivities,
      ...(trip.selected_flight_id ? { flight_id: trip.selected_flight_id } : {}),
    }), 1);
  }
  async function submitDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!booking || disabled) return;
    await run(() => api.details(booking.reference, {
      name: name.trim(), email: email.trim(), nationality: nationality.trim(),
      passport_expiry: passportExpiry,
      ...(visaExpiry ? { evisa_expiry: visaExpiry } : {}),
    }), 2);
    // Expiry values never survive a completed request, including a rejected validation.
    setPassportExpiry(""); setVisaExpiry("");
  }
  async function pay(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!booking || !agreed || disabled) return;
    await run(() => api.pay(booking.reference, card), 4);
    setCard("4242424242424242"); setAgreed(false);
  }
  const flight = trip.flights.find(item => item.id === trip.selected_flight_id);

  return <div className="booking-page page-width">
    <button type="button" className="text-button back-link" onClick={onClose} disabled={pending}><Icon name="back" />{copy.nav.backTrip}</button>
    <header className="page-intro"><h1>{copy.booking.title}</h1></header>
    <Notice kind="warning"><strong>{copy.booking.safety}</strong></Notice>
    <ol className="booking-steps" aria-label={copy.booking.title}>
      {copy.booking.steps.map((label, index) => <li key={label} className={index === step ? "current" : index < step ? "complete" : ""}
        aria-current={index === step ? "step" : undefined}>
        <span className="step-index">{index < step ? <Icon name="check" /> : index + 1}</span><span>{label}</span>
      </li>)}
    </ol>
    {booking && <div className="hold-bar">
      <div><span className="small-copy">{copy.booking.reference}</span><strong>{booking.reference}</strong></div>
      {activeHold(booking) && !elapsed && <div className="hold-countdown">
        <span>{copy.booking.hold}</span><span role="timer" aria-live="off">
          {Math.floor(remaining / 60).toString().padStart(2, "0")}:{(remaining % 60).toString().padStart(2, "0")}
        </span><small>{copy.booking.holdHelp}</small>
      </div>}
      <span className="small-copy">{copy.booking.state}: {humanize(booking.state)}</span>
    </div>}
    <ErrorNotice message={error} />
    {mismatch && <Notice kind="warning">{copy.booking.mismatch}</Notice>}
    {(elapsed || booking?.state === "expired") && <div role="alert"><Notice kind="warning">{copy.booking.expired}</Notice></div>}
    {booking?.state === "cancelled_simulated" && <Notice kind="success">{copy.booking.cancelled}</Notice>}
    {booking?.notices.map((notice, index) => <Notice key={`${notice}-${index}`} kind="warning">{notice}</Notice>)}
    {(!terminal && !elapsed && !mismatch) && <div className="booking-content">
      {step === 0 && <section>
        <h2 ref={heading} tabIndex={-1}>{copy.booking.basket}</h2><p>{copy.booking.basketDescription}</p>
        <Notice>{copy.common.hotelDemo}</Notice>
        {hotel ? <>
          <div className="basket-hotel"><Icon name="bed" /><div><h3>{hotel.name}</h3><p>{hotel.district}</p>
            <p className="small-copy">{formatDate(trip.search_params.arrival)} – {formatDate(trip.search_params.departure)}
              {" · "}{copy.common.nights(trip.nights)} · {copy.common.guests(guests)}</p></div></div>
          <div className="field"><label htmlFor="booking-room">{copy.booking.room}</label>
            <select id="booking-room" value={roomId} disabled={pending} onChange={event => {
              setRoomId(event.target.value); setAvailability(null);
            }}>
              {!roomId && <option value="">{copy.booking.noRoom}</option>}
              {hotel.room_types.map(room => <option key={room.id} value={room.id}>
                {room.name} · {copy.hotels.capacity(room.max_occupancy)}
              </option>)}
            </select>
            <p className="field-help">{copy.hotels.upgradeNote}</p>
          </div>
          {roomId && <AvailabilityCalendar hotelId={hotel.id} roomId={roomId} search={trip.search_params}
            currency={currency} rates={rates} onAvailability={setAvailability} />}
          <h3>{copy.booking.activities}</h3><p className="fiction-label">{copy.common.activityDemo}</p>
          <div className="basket-activities">{itineraryActivities.map(activity => <label key={activity.id}>
            <input type="checkbox" disabled={pending} checked={selectedActivities.includes(activity.id)}
              onChange={event => setSelectedActivities(current => event.target.checked ? [...current, activity.id] : current.filter(id => id !== activity.id))} />
            <span><strong>{activity.name}</strong><small>{trip.itinerary_days.filter(day => day.items.some(item => item.activity_id === activity.id))
              .map(day => formatDate(day.date, true)).join(", ")}</small></span>
            <span><Price amount={activity.price_azn} currency={currency} rates={rates} /><small>{copy.common.perPerson}</small></span>
          </label>)}</div>
          {!selectedActivities.length && <p>{copy.booking.noActivities}</p>}
          <p className="small-copy">{copy.booking.estimate}</p>
          <p className="planned-flight"><Icon name="plane" /><span>{flight && <strong>{flight.carrier} · {flight.origin} → {flight.destination}. </strong>}{copy.booking.flight}</span></p>
          <h3>{copy.booking.terms}</h3><p>{hotel.cancellation_policy}</p>
          <button type="button" className="button button-primary button-large" disabled={pending || !roomId || !availability?.available} onClick={() => void create()}>
            {pending ? copy.booking.holding : copy.booking.continue}<Icon name="arrow" />
          </button>
        </> : <Notice kind="warning">{copy.booking.noRoom}</Notice>}
      </section>}
      {step === 1 && booking && <section>
        <h2 ref={heading} tabIndex={-1}>{copy.booking.traveller}</h2><p>{copy.booking.privacy}</p>
        <form onSubmit={submitDetails} autoComplete="off" className="traveller-form">
          <fieldset disabled={disabled}><legend className="sr-only">{copy.booking.traveller}</legend>
            <div className="form-grid">
              <div className="field"><label htmlFor="traveller-name">{copy.booking.name}</label>
                <input id="traveller-name" value={name} onChange={event => setName(event.target.value)} minLength={2} maxLength={100} required autoComplete="off" /></div>
              <div className="field"><label htmlFor="traveller-email">{copy.booking.email}</label>
                <input id="traveller-email" type="email" value={email} onChange={event => setEmail(event.target.value)} maxLength={254} required autoComplete="off" /></div>
              <div className="field"><label htmlFor="traveller-nationality">{copy.booking.nationality}</label>
                <input id="traveller-nationality" value={nationality} onChange={event => setNationality(event.target.value.toUpperCase())} minLength={2} maxLength={2} pattern="[A-Z]{2}" required autoComplete="off" /></div>
              <div className="field"><label htmlFor="passport-expiry">{copy.booking.passportExpiry}</label>
                <input id="passport-expiry" type="date" value={passportExpiry} onChange={event => setPassportExpiry(event.target.value)} min={today} required autoComplete="off" /></div>
              <div className="field"><label htmlFor="visa-expiry">{copy.booking.visaExpiry}</label>
                <input id="visa-expiry" type="date" value={visaExpiry} onChange={event => setVisaExpiry(event.target.value)} autoComplete="off" aria-describedby="visa-expiry-help" /></div>
            </div>
            <p className="field-help" id="visa-expiry-help">{copy.booking.visaHelp}</p>
            <button type="submit" className="button button-primary" disabled={disabled}>{pending ? copy.common.saving : copy.booking.detailsContinue}<Icon name="arrow" /></button>
          </fieldset>
        </form>
        <BookingLines booking={booking} currency={currency} rates={rates} />
      </section>}
      {step === 2 && booking && <section>
        <h2 ref={heading} tabIndex={-1}>{copy.booking.review}</h2>
        <BookingLines booking={booking} currency={currency} rates={rates} />
        <p className="planned-flight"><Icon name="plane" />{copy.booking.flight}</p>
        <h3>{copy.booking.terms}</h3><p>{hotel?.cancellation_policy}</p>
        <h3>{copy.booking.warnings}</h3><ChecklistEntries entries={trip.checklist} facts={facts} today={today} />
        <Notice kind="warning">{copy.booking.safety}</Notice>
        <button type="button" className="button button-primary" disabled={disabled} onClick={() => { setStep(3); setError(null); }}>
          {copy.booking.paymentContinue}<Icon name="arrow" />
        </button>
      </section>}
      {step === 3 && booking && <section>
        <h2 ref={heading} tabIndex={-1}>{copy.booking.paymentTitle}</h2>
        <Notice kind="warning"><strong>{copy.booking.paymentNote}</strong></Notice>
        <BookingLines booking={booking} currency={currency} rates={rates} />
        <form onSubmit={pay} autoComplete="off" className="payment-form">
          <fieldset disabled={disabled}><legend className="sr-only">{copy.booking.paymentTitle}</legend>
            <div className="field"><label htmlFor="test-card-number">{copy.booking.card}</label>
              <input id="test-card-number" type="text" inputMode="numeric" autoComplete="off" spellCheck={false}
                value={card} onChange={event => setCard(event.target.value)} maxLength={24} required aria-describedby="test-card-help" />
              <p id="test-card-help" className="field-help">{copy.booking.cardHelp}</p>
            </div>
            <label className="checkbox-label payment-agreement"><input type="checkbox" checked={agreed}
              onChange={event => setAgreed(event.target.checked)} required />{copy.booking.agreement}</label>
            <div className="button-row">
              <button type="button" className="button button-secondary" disabled={disabled} onClick={() => setStep(2)}><Icon name="back" />{copy.booking.continueReview}</button>
              <button type="submit" className="button button-primary" disabled={disabled || !agreed}>
                <Icon name="shield" />{pending ? copy.booking.paying : copy.booking.pay}
              </button>
            </div>
          </fieldset>
        </form>
      </section>}
      {step === 4 && booking?.state === "confirmed_simulated" && <section className="confirmation" aria-label={copy.booking.watermark}>
        <div className="confirmation-icon"><Icon name="check" /></div>
        <h2 ref={heading} tabIndex={-1}>{copy.booking.confirmation}</h2>
        <p className="confirmation-watermark">{copy.booking.watermark}</p>
        <p className="reference-label">{copy.booking.reference}</p><strong className="confirmation-reference">{booking.reference}</strong>
        <p>{copy.booking.confirmationBody}</p>
        <p className="small-copy">{copy.booking.safety}</p>
        <BookingLines booking={booking} currency={currency} rates={rates} />
        <div className="button-row">
          <a className="button button-primary" href={api.download(booking.reference, "pdf")} download><Icon name="download" />{copy.booking.pdf}</a>
          <a className="button button-secondary" href={api.download(booking.reference, "ics")} download><Icon name="calendar" />{copy.booking.calendar}</a>
        </div>
        <p className="small-copy">{copy.booking.downloadNote}</p>
      </section>}
    </div>}
    {booking && <div className="booking-management">
      <button type="button" className="text-button" disabled={pending} onClick={() => void run(() => api.booking(booking.reference))}>{copy.booking.refresh}</button>
      <p className="small-copy">{copy.booking.refreshHelp}</p>
      {!terminal && <>
        {!confirmCancel ? <button type="button" className="text-button destructive-text" disabled={pending} onClick={() => setConfirmCancel(true)}>{copy.booking.cancel}</button> :
          <div className="cancel-confirmation"><p>{copy.booking.cancelQuestion}</p><div className="button-row">
            <button type="button" className="button button-danger" disabled={pending} onClick={() => void run(() => api.cancel(booking.reference))}>
              {pending ? copy.common.saving : copy.booking.cancelConfirm}</button>
            <button type="button" className="button button-secondary" disabled={pending} onClick={() => setConfirmCancel(false)}>{copy.booking.keep}</button>
          </div></div>}
      </>}
    </div>}
  </div>;
}
