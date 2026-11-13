"""In-memory, explicitly simulated itinerary downloads."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
from io import BytesIO

from .booking import WATERMARK


def render_pdf(booking: dict, trip: dict, facts: list[dict]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    stream = BytesIO()
    styles = getSampleStyleSheet()
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 12
    styles["BodyText"].wordWrap = "LTR"
    document = SimpleDocTemplate(
        stream, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=55, bottomMargin=45,
        title=f"{booking['reference']} - {WATERMARK}",
        author="Caspian Compass demonstration", pageCompression=0,
    )

    def paragraph(value: object, style: str = "BodyText") -> Paragraph:
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), styles[style])

    def page_label(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#854000"))
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawCentredString(A4[0] / 2, A4[1] - 30, WATERMARK)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(36, 23, f"{booking['reference']} | No payment taken. No tickets issued.")
        canvas.drawRightString(A4[0] - 36, 23, str(doc.page))
        canvas.restoreState()

    story = [
        paragraph("Caspian Compass simulated itinerary", "Title"),
        paragraph(f"Reference: {booking['reference']}"),
        paragraph(f"Dates: {trip['search_params']['arrival']} to {trip['search_params']['departure']}"),
        paragraph(
            f"Travellers: {trip['search_params']['adults']} adults, "
            f"{trip['search_params']['children']} children"
        ),
        paragraph(
            "Fictional accommodation, synthetic prices and activity slots. "
            "This document is neither a voucher nor a reservation."
        ),
        Spacer(1, 12),
        paragraph("Simulated basket", "Heading2"),
    ]
    rows = [[paragraph(value) for value in ("Date", "Item", "Qty", "Unit AZN", "Total AZN")]]
    rows.extend([
        paragraph(item["date"]), paragraph(item["name"]), paragraph(item["quantity"]),
        paragraph(f"{item['unit_price_azn']:.2f}"), paragraph(f"{item['total_azn']:.2f}"),
    ] for item in booking["items"])
    table = Table(rows, colWidths=[65, 245, 30, 55, 55], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F2EF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#335F59")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([
        table, Spacer(1, 8),
        paragraph(f"Basket total: {booking['total_azn']:.2f} AZN / {booking['total_gbp']:.2f} GBP"),
        paragraph(
            f"Indicative currency conversion dated {trip['exchange_rates']['as_of']}. "
            "Flights and transport are not included in the simulated basket."
        ),
        paragraph("Day-by-day plan", "Heading2"),
    ])
    for day in trip["itinerary_days"]:
        story.append(paragraph(f"{day['date']} - {day['title']}", "Heading3"))
        for item in day["items"]:
            story.append(paragraph(
                f"{item['start_time']} - {item['end_time']}: {item['title']}. "
                f"{item['transport_note']}"
            ))
    flight = next(
        (item for item in trip["flights"] if item["id"] == trip["selected_flight_id"]), None
    )
    if flight:
        story.extend([
            paragraph("Flight: planned, not booked", "Heading2"),
            paragraph(
                f"{flight['carrier']}: {flight['origin']} to {flight['destination']}; "
                f"{flight['depart_local']} to {flight['arrive_local']}. {flight['schedule_note']}"
            ),
            paragraph(f"Verify schedules and fares directly: {flight['airline_url']}"),
        ])
    story.append(paragraph("Transport guidance (not reserved)", "Heading2"))
    for leg in trip["transport_legs"]:
        story.append(paragraph(
            f"{leg['from']} to {leg['to']}: {leg['mode']} ({leg['operator']}), "
            f"about {leg['duration_min']} minutes, estimated {leg['total_azn']:.2f} AZN. "
            f"{leg['schedule_note']}"
        ))
    story.append(paragraph("Important notices", "Heading2"))
    story.extend(paragraph(notice) for notice in booking["notices"])
    story.extend(
        paragraph(f"{item['title']}: {item['description']}") for item in trip["checklist"]
    )
    story.append(paragraph("Grounding sources", "Heading2"))
    story.append(paragraph(
        "Verification dates are the specification baseline, not a claim of independent re-verification. "
        "Confirm all entry rules, timetables and fares before travel."
    ))
    for fact in facts:
        story.append(paragraph(
            f"{fact['topic']}: {fact['statement']} "
            f"Baseline {fact['last_verified']}. Source: {fact['source_url']}"
        ))
    document.build(story, onFirstPage=page_label, onLaterPages=page_label)
    return stream.getvalue()


def ics_escape(value: object) -> str:
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(character for character in text if character >= " " or character in "\n\t")
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold_ics(line: str) -> str:
    parts = []
    current = ""
    size = 0
    for character in line:
        length = len(character.encode("utf-8"))
        if size + length > 75:
            parts.append(current)
            current, size = " ", 1
        current += character
        size += length
    parts.append(current)
    return "\r\n".join(parts)


def _baku_to_utc(day: str, local_time: str) -> str:
    value = datetime.fromisoformat(f"{day}T{local_time}")
    return value.replace(tzinfo=timezone(timedelta(hours=4))).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def render_ics(booking: dict, trip: dict, facts: list[dict]) -> bytes:
    reference = booking["reference"]
    created = datetime.fromisoformat(booking["created_at"].replace("Z", "+00:00"))
    stamp = created.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sources = "\n".join(
        f"{fact['topic']}: {fact['source_url']} (baseline {fact['last_verified']})" for fact in facts
    )
    description = (
        f"{WATERMARK}\nReference: {reference}\n"
        f"Synthetic basket: {booking['total_azn']:.2f} AZN / {booking['total_gbp']:.2f} GBP.\n"
        "No payment taken. Flights are planned, not booked. Confirm details before travel.\n"
        f"Sources:\n{sources}"
    )
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "PRODID:-//Caspian Compass//Simulated itinerary//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:{ics_escape(WATERMARK)}",
    ]
    hotel_items = [item for item in booking["items"] if item["kind"] == "hotel"]
    if hotel_items:
        hotel_prices = "\n".join(
            f"{item['date']}: {item['quantity']} room(s), {item['total_azn']:.2f} AZN"
            for item in hotel_items
        )
        lines.extend([
            "BEGIN:VEVENT", f"UID:{reference}-hotel@caspian-compass.invalid", f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{trip['search_params']['arrival'].replace('-', '')}",
            f"DTEND;VALUE=DATE:{trip['search_params']['departure'].replace('-', '')}",
            f"SUMMARY:{ics_escape(WATERMARK + ' - ' + hotel_items[0]['name'])}",
            f"DESCRIPTION:{ics_escape(description + chr(10) + hotel_prices)}",
            "STATUS:TENTATIVE", "TRANSP:TRANSPARENT", "END:VEVENT",
        ])
    selected_items = {
        item["id"]: item for item in booking["items"] if item["kind"] == "activity"
    }
    sequence = 0
    for day in trip["itinerary_days"]:
        for item in day["items"]:
            basket_id = f"{item['activity_id']}:{day['date']}:{item['start_time']}"
            if basket_id not in selected_items:
                continue
            sequence += 1
            selected = selected_items[basket_id]
            cost = f"Activity: {selected['quantity']} traveller(s), {selected['total_azn']:.2f} AZN."
            lines.extend([
                "BEGIN:VEVENT", f"UID:{reference}-activity-{sequence}@caspian-compass.invalid",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{_baku_to_utc(day['date'], item['start_time'])}",
                f"DTEND:{_baku_to_utc(day['date'], item['end_time'])}",
                f"SUMMARY:{ics_escape(WATERMARK + ' - ' + item['title'])}",
                f"DESCRIPTION:{ics_escape(description + chr(10) + cost)}",
                "STATUS:TENTATIVE", "TRANSP:TRANSPARENT", "END:VEVENT",
            ])
    lines.append("END:VCALENDAR")
    return ("\r\n".join(_fold_ics(line) for line in lines) + "\r\n").encode("utf-8")
