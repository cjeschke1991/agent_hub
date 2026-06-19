"""Google Calendar integration for urgency context."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from agent_hub.agents.gmail_assistant.prefs import extract_sender_email


@dataclass
class CalendarEvent:
    summary: str
    start: str
    attendees: list[str]


def fetch_upcoming_events(service: Any, hours: int = 48) -> list[CalendarEvent]:
    now = datetime.now(timezone.utc)
    time_max = now + timedelta(hours=hours)
    payload = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=20,
        )
        .execute()
    )
    events: list[CalendarEvent] = []
    for item in payload.get("items", []):
        start = item.get("start", {})
        start_time = start.get("dateTime") or start.get("date") or ""
        attendees = [
            extract_sender_email(a.get("email", ""))
            for a in item.get("attendees", [])
            if a.get("email")
        ]
        events.append(
            CalendarEvent(
                summary=item.get("summary", "(no title)"),
                start=start_time,
                attendees=attendees,
            )
        )
    return events


def calendar_emails_from_events(events: list[CalendarEvent]) -> set[str]:
    emails: set[str] = set()
    for event in events:
        emails.update(event.attendees)
    return emails


def format_calendar_context(events: list[CalendarEvent]) -> str:
    if not events:
        return ""
    lines = ["Upcoming calendar (next 48 hours):"]
    for event in events[:10]:
        attendee_text = ", ".join(event.attendees[:5]) if event.attendees else "no attendees listed"
        lines.append(f"- {event.summary} at {event.start} (attendees: {attendee_text})")
    return "\n".join(lines)
