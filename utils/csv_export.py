"""CSV export utility for event participants."""
import csv
import io
from typing import BinaryIO

import database as db


async def export_participants_csv(event_id: int) -> BinaryIO:
    """Export participants of an event as CSV. Returns a BytesIO buffer."""
    participants = await db.get_event_participants_for_export(event_id)
    event = await db.get_event(event_id)
    event_title = event["title"] if event else "Unknown"

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "User ID", "Username", "Имя", "Тип билета",
        "Цена", "Статус", "Код чекина", "Дата регистрации",
    ])

    status_labels = {
        "registered": "Зарегистрирован",
        "attended": "Присутствовал",
        "waitlist": "Лист ожидания",
        "cancelled": "Отменён",
    }

    for p in participants:
        writer.writerow([
            p["user_id"],
            f"@{p['username']}" if p.get("username") else "",
            p.get("full_name") or "",
            p.get("ticket_name", "Без типа"),
            p.get("ticket_price", 0),
            status_labels.get(p["status"], p["status"]),
            p.get("checkin_code") or "",
            p.get("registered_at") or "",
        ])

    # Convert to bytes
    bytes_output = io.BytesIO()
    bytes_output.write(output.getvalue().encode("utf-8-sig"))  # BOM for Excel
    bytes_output.seek(0)
    return bytes_output
