# google-calendar-sdk

Pure-Python wrapper around Google Calendar API v3 for service-account flows with domain-wide delegation. Used by Volkanos modules that book slots on behalf of a real user (consultations, demos, deliveries) — most prominently the booking widget in `django-contact-forms`.

This SDK does **one thing**: talk to Google Calendar. It has no Django, no Volkanos coupling, no business logic about who can book what. Callers decide when to query, what to write, and which exceptions to surface.

## Install

```bash
uv pip install entirius-py-google-calendar-sdk
```

Or as a dependency in `pyproject.toml`:

```toml
"entirius-py-google-calendar-sdk>=2.0.0"
```

## Use

```python
from datetime import datetime, timezone
from google_calendar_sdk import GoogleCalendarClient

client = GoogleCalendarClient(
    credentials_path="/app/credentials/sa.json",
    impersonate_email="bookings@yourdomain.com",
    calendar_id="primary",  # or a shared calendar ID
)

free = client.is_slot_free(
    start=datetime(2026, 4, 20, 14, 0, tzinfo=timezone.utc),
    end=datetime(2026, 4, 20, 14, 30, tzinfo=timezone.utc),
    timezone="Europe/Warsaw",
)

if free:
    event = client.create_event(
        start=datetime(2026, 4, 20, 14, 0, tzinfo=timezone.utc),
        end=datetime(2026, 4, 20, 14, 30, tzinfo=timezone.utc),
        summary="Consultation - Jan",
        attendee_email="jan@example.com",
        description="Booking via website widget",
        timezone="Europe/Warsaw",
        create_meet_link=True,
    )
    print(event.event_id, event.meet_link)
```

## Service-account setup

1. Create a Google Cloud project, enable the Calendar API.
2. Create a service account with **domain-wide delegation**.
3. In Google Workspace admin: grant the service account the scope `https://www.googleapis.com/auth/calendar`.
4. Download the JSON key. Mount it inside the container as a private file (e.g. `/app/credentials/sa.json`).
5. The `impersonate_email` argument is the real user the service account acts as — events are created on that user's `primary` calendar so they receive the invite and own the event.

## Free-busy semantics

`get_busy_periods` always queries the impersonated user's `primary` calendar. If `calendar_id` is set to anything other than `"primary"`, the shared calendar is queried as well — and busy periods from both are merged. This is the standard pattern for "the consultant has both a personal calendar AND a shared booking calendar; both must be free".

## Tests

```bash
pytest
```

Tests fully mock `googleapiclient.discovery.build` so no network access is required.
