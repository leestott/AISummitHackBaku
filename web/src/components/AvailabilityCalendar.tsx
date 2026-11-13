import { useEffect, useState } from "react";
import type { Availability, SearchParams } from "../../../contracts/api";
import { api, errorMessage, isAborted } from "../api";
import { copy } from "../i18n";
import { formatDate } from "../utils";
import { ErrorNotice, LoadingRows, Notice, Price, type MoneyProps } from "./Shared";

export function AvailabilityCalendar({ hotelId, roomId, search, currency, rates, onAvailability }: MoneyProps & {
  hotelId: string;
  roomId: string;
  search: SearchParams;
  onAvailability?: (availability: Availability | null) => void;
}) {
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);
  const guests = search.adults + search.children;

  useEffect(() => {
    const controller = new AbortController();
    setAvailability(null);
    onAvailability?.(null);
    setError(null);
    if (!roomId) return () => controller.abort();
    setLoading(true);
    api.availability(hotelId, search.arrival, search.departure, guests, roomId, controller.signal)
      .then(result => {
        if (controller.signal.aborted) return;
        setAvailability(result);
        onAvailability?.(result);
      })
      .catch(cause => { if (!isAborted(cause) && !controller.signal.aborted) setError(errorMessage(cause)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [hotelId, roomId, search.arrival, search.departure, guests, revision, onAvailability]);

  return <section className="availability-calendar" aria-label={copy.hotels.availability}>
    <h4>{copy.hotels.availability}</h4>
    {loading && <LoadingRows label={copy.hotels.availabilityLoading} />}
    <ErrorNotice message={error} onRetry={() => setRevision(value => value + 1)} />
    {availability && <>
      {availability.rooms_required !== undefined && <p className="small-copy">
        <strong>{copy.hotels.roomCount(availability.rooms_required)}.</strong> {copy.hotels.aggregateRate}
      </p>}
      <Notice kind={availability.available ? "success" : "warning"}>
        {availability.available ? copy.hotels.available : copy.hotels.soldOut}
      </Notice>
      <div className="table-scroll" tabIndex={0} role="region" aria-label={copy.hotels.availability}>
        <table><thead><tr><th scope="col">{copy.hotels.date}</th><th scope="col">{copy.hotels.rate}</th>
          <th scope="col">{copy.hotels.remaining}</th><th scope="col">{copy.hotels.event}</th></tr></thead>
          <tbody>{availability.nights.map(night => <tr key={night.date}>
            <th scope="row">{formatDate(night.date, true)}</th>
            <td><Price amount={night.price_azn} currency={currency} rates={rates} />
              {night.unit_price_azn !== undefined && (availability.rooms_required ?? 1) > 1 &&
                <small className="night-unit-rate">{copy.hotels.unitRate}: <Price amount={night.unit_price_azn} currency={currency} rates={rates} /></small>}
            </td>
            <td>{night.available}</td><td>{night.event ?? "—"}</td>
          </tr>)}</tbody>
        </table>
      </div>
      <p className="inline-total"><span>{copy.hotels.totalRoom}</span>
        <strong><Price amount={availability.total_azn} currency={currency} rates={rates} secondary /></strong>
      </p>
    </>}
  </section>;
}
