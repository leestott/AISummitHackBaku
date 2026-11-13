import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Hotel } from "../../../contracts/api";
import { copy } from "../i18n";
import { Notice } from "./Shared";

export default function HotelMap({ hotels, onSelect }: { hotels: Hotel[]; onSelect: (hotelId: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const selection = useRef(onSelect);
  const [tileError, setTileError] = useState(false);
  useEffect(() => { selection.current = onSelect; }, [onSelect]);

  useEffect(() => {
    if (!container.current) return;
    setTileError(false);
    const map = L.map(container.current, {
      scrollWheelZoom: false,
      zoomAnimation: false,
      markerZoomAnimation: false,
      fadeAnimation: false,
    }).setView([40.3777, 49.892], 12);
    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    tiles.on("tileerror", () => setTileError(true));
    const points: L.LatLngTuple[] = [];
    hotels.forEach((hotel, index) => {
      if (!Number.isFinite(hotel.lat) || !Number.isFinite(hotel.lon)) return;
      const point: L.LatLngTuple = [hotel.lat, hotel.lon];
      points.push(point);
      const marker = L.marker(point, {
        title: copy.hotels.mapMarker(hotel.name),
        alt: copy.hotels.mapMarker(hotel.name),
        keyboard: true,
        icon: L.divIcon({
          className: "hotel-map-marker",
          html: `<span>${index + 1}</span>`,
          iconSize: [44, 44],
          iconAnchor: [22, 44],
        }),
      }).addTo(map);
      marker.on("click", () => selection.current(hotel.id));
    });
    if (points.length) map.fitBounds(L.latLngBounds(points), { padding: [42, 42], maxZoom: 14, animate: false });
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(container.current);
    return () => { observer.disconnect(); map.stop(); map.remove(); };
  }, [hotels]);

  return <div className="hotel-map">
    <p className="small-copy">{copy.hotels.mapNote}</p>
    {tileError && <Notice kind="warning">{copy.hotels.mapFailed}</Notice>}
    <div ref={container} className="map-canvas" role="region" aria-label={copy.hotels.mapLabel} />
  </div>;
}
