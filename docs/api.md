# Public API

| Symbol | Type | Purpose |
|---|---|---|
| `GoogleCalendarClient(credentials_path, impersonate_email, calendar_id="primary")` | class | Main entry point |
| `.get_busy_periods(time_min, time_max, timezone) -> list[BusyPeriod]` | method | Free-busy across primary + optional shared calendar |
| `.is_slot_free(start, end, timezone) -> bool` | method | Race-condition guard before `create_event` |
| `.create_event(start, end, summary, attendee_email, description="", timezone="UTC", create_meet_link=True) -> EventResult` | method | Creates on primary, optional Meet link |
| `BusyPeriod(start, end)` | dataclass | Free-busy entry |
| `EventResult(event_id, meet_link)` | dataclass | `meet_link` is `str \| None` — `None` when no Meet conference attached |
| `CalendarAPIError` | exception | Base — wraps all Google API failures |
| `CredentialsError` | exception | **Subclass of `CalendarAPIError`** — credential load / refresh failures. Catching `CalendarAPIError` catches both. Part of the public API contract. |
