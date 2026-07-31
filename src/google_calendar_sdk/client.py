# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import re
from datetime import datetime
from uuid import uuid4

from googleapiclient.errors import HttpError

from google_calendar_sdk._service_cache import get_service
from google_calendar_sdk.exceptions import CalendarAPIError
from google_calendar_sdk.types import BusyPeriod, EventResult

# Google Ads / Calendar enum constants used in proto bodies. Kept module-level so
# a rename in one upstream version is fixed in one place.
CONFERENCE_SOLUTION_HANGOUTS_MEET = "hangoutsMeet"
SEND_UPDATES_ALL = "all"
PRIMARY_CALENDAR_ID = "primary"

# Hard caps on user-controlled fields that flow into Google Calendar event bodies.
# Calendar accepts much larger but those values then ride into email notifications;
# defending against CRLF / control-char injection here removes a phishing primitive.
_MAX_SUMMARY_LEN = 200
_MAX_DESCRIPTION_LEN = 2000
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class GoogleCalendarClient:
    """Wraps Google Calendar API v3 using a service account with domain-wide delegation.

    Queries free-busy across both the configured ``calendar_id`` (a shared booking
    calendar) and the impersonated user's ``primary`` calendar. New events are always
    created on ``primary`` so the impersonated user owns them and gets the invite.

    Raises ``CredentialsError`` (subclass of ``CalendarAPIError``) at construction
    time if the service-account JSON cannot be loaded or the impersonation grant
    is rejected.
    """

    def __init__(self, credentials_path: str, impersonate_email: str, calendar_id: str = PRIMARY_CALENDAR_ID) -> None:
        if not impersonate_email:
            raise ValueError("impersonate_email is required (cannot be empty)")
        if not calendar_id:
            raise ValueError("calendar_id is required; pass 'primary' explicitly to opt out")
        if calendar_id != PRIMARY_CALENDAR_ID and not _EMAIL_RE.match(calendar_id):
            raise ValueError(f"calendar_id must be 'primary' or an email-shaped string, got: {calendar_id!r}")
        self.calendar_id = calendar_id
        self.impersonate_email = impersonate_email
        self._service = get_service(credentials_path, impersonate_email)

    def get_busy_periods(self, time_min: datetime, time_max: datetime, timezone: str) -> list[BusyPeriod]:
        body = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "timeZone": timezone,
            "items": _dedupe_calendars(self.calendar_id),
        }
        try:
            result = self._service.freebusy().query(body=body).execute()
        except HttpError as exc:
            raise CalendarAPIError(_safe_http_error_text("freebusy.query", exc)) from exc

        busy: list[BusyPeriod] = []
        for cal_data in result.get("calendars", {}).values():
            for period in cal_data.get("busy", []):
                busy.append(BusyPeriod(_parse(period["start"]), _parse(period["end"])))
        return busy

    def is_slot_free(self, start: datetime, end: datetime, timezone: str) -> bool:
        """Calls freebusy once for a single window. Per-slot use in a loop is wasteful —
        callers iterating over a day should call ``get_busy_periods`` once and check
        overlaps locally."""
        return not self.get_busy_periods(start, end, timezone)

    def create_event(
        self,
        start: datetime,
        end: datetime,
        summary: str,
        attendee_email: str,
        description: str = "",
        timezone: str = "UTC",
        create_meet_link: bool = True,
    ) -> EventResult:
        if not _EMAIL_RE.match(attendee_email or ""):
            raise ValueError(f"attendee_email is not a valid email address: {attendee_email!r}")
        body = _build_event_body(
            start=start,
            end=end,
            summary=_sanitize(summary, _MAX_SUMMARY_LEN),
            attendee_email=attendee_email,
            description=_sanitize(description, _MAX_DESCRIPTION_LEN),
            timezone=timezone,
            create_meet_link=create_meet_link,
        )
        try:
            event = (
                self._service.events()
                .insert(
                    calendarId=PRIMARY_CALENDAR_ID,
                    body=body,
                    conferenceDataVersion=1 if create_meet_link else 0,
                    sendUpdates=SEND_UPDATES_ALL,
                )
                .execute()
            )
        except HttpError as exc:
            raise CalendarAPIError(_safe_http_error_text("events.insert", exc)) from exc
        return EventResult(event_id=event["id"], meet_link=event.get("hangoutLink") or None)


def _build_event_body(
    *,
    start: datetime,
    end: datetime,
    summary: str,
    attendee_email: str,
    description: str,
    timezone: str,
    create_meet_link: bool,
) -> dict:
    body: dict = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone},
        "attendees": [{"email": attendee_email}],
        "reminders": {"useDefault": True},
    }
    if create_meet_link:
        body["conferenceData"] = {
            "createRequest": {
                "requestId": str(uuid4()),
                "conferenceSolutionKey": {"type": CONFERENCE_SOLUTION_HANGOUTS_MEET},
            }
        }
    return body


def _dedupe_calendars(calendar_id: str) -> list[dict]:
    # Google freebusy returns duplicate busy intervals if the same calendar ID
    # appears twice in items. Always send primary once; add the shared calendar
    # only when it's a distinct ID.
    items = [{"id": PRIMARY_CALENDAR_ID}]
    if calendar_id and calendar_id != PRIMARY_CALENDAR_ID:
        items.append({"id": calendar_id})
    return items


def _sanitize(value: str, max_len: int) -> str:
    return _CONTROL_CHARS.sub("", value or "")[:max_len]


def _safe_http_error_text(operation: str, exc: HttpError) -> str:
    # HttpError.uri contains the calendar_id (caller-controlled) and any query
    # params — both can leak via logs. Surface only status + reason.
    status = getattr(getattr(exc, "resp", None), "status", "?")
    reason = getattr(exc, "reason", "") or ""
    return f"{operation} failed: HTTP {status} {reason}".strip()


def _parse(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise CalendarAPIError(f"unexpected timestamp from Calendar API: {value!r}") from exc
