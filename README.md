# entirius-py-google-calendar-sdk

A Python client for the Google Calendar API using a service account, part of
Entirius, the open-source modular ecommerce platform. It reads free-busy and creates events on behalf of a real user
through domain-wide delegation; it has no Django dependency and no booking logic.

[![PyPI](https://img.shields.io/pypi/v/entirius-py-google-calendar-sdk.svg)](https://pypi.org/project/entirius-py-google-calendar-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/entirius-py-google-calendar-sdk.svg)](https://pypi.org/project/entirius-py-google-calendar-sdk/)
[![License: MPL-2.0](https://img.shields.io/badge/license-MPL--2.0-blue.svg)](https://github.com/entirius/entirius-py-google-calendar-sdk/blob/develop/LICENSE)

## What it does

- Reads the busy periods of the impersonated user's primary calendar, merged with an optional shared calendar
  (`get_busy_periods()`).
- Checks one slot before booking (`is_slot_free()`).
- Creates an event with an attendee and an optional Google Meet link (`create_event()`).
- Wraps every Google API failure in `CalendarAPIError`; credential failures raise its subclass `CredentialsError`.
- Caches the API service per credentials file and impersonated user.

## Installation

```shell
uv add entirius-py-google-calendar-sdk
pip install entirius-py-google-calendar-sdk
```

The import name is `google_calendar_sdk`.

## Quick start

```python
from datetime import datetime, timezone

from google_calendar_sdk import GoogleCalendarClient

client = GoogleCalendarClient(credentials_path="/path/to/sa.json", impersonate_email="bookings@example.com")
start = datetime(2026, 4, 20, 14, 0, tzinfo=timezone.utc)
end = datetime(2026, 4, 20, 14, 30, tzinfo=timezone.utc)
if client.is_slot_free(start=start, end=end, timezone="Europe/Warsaw"):
    event = client.create_event(
        start=start, end=end, summary="Consultation", attendee_email="jan@example.com", timezone="Europe/Warsaw"
    )
    print(event.event_id, event.meet_link)
```

## Requirements

- Python 3.11 or newer.
- `google-api-python-client` and `google-auth` (installed as dependencies).
- A Google Cloud service account with domain-wide delegation and the Calendar scope.

## Documentation

- Service-account setup and free-busy semantics: https://github.com/entirius/entirius-py-google-calendar-sdk/blob/develop/docs/setup.md
- Public API: https://github.com/entirius/entirius-py-google-calendar-sdk/blob/develop/docs/api.md
- Design rules: https://github.com/entirius/entirius-py-google-calendar-sdk/blob/develop/docs/design.md
- Entirius documentation: https://docs.entirius.com/
- Releases: https://github.com/entirius/entirius-py-google-calendar-sdk/releases

## Part of Entirius

This SDK is the Google Calendar client of the Entirius backend service (Volkanos) and its modules.

- Backend service: https://github.com/entirius/entirius-service-volkanos
- Docker harness: https://github.com/entirius/entirius-zeno
- Consumer module: https://github.com/entirius/entirius-django-contact-forms

## Development

```shell
make install     # sync dependencies (uv)
make check       # lint + format check (ruff)
make test        # test suite (pytest); the Google API client is mocked, no network needed
```

Development and agent instructions: https://github.com/entirius/entirius-py-google-calendar-sdk/blob/develop/AGENTS.md

## License

Mozilla Public License 2.0 (MPL-2.0) — see https://github.com/entirius/entirius-py-google-calendar-sdk/blob/develop/LICENSE.
