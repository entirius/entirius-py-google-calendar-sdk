# AGENTS.md

Pure-Python wrapper around Google Calendar API v3 for service-account + domain-wide-delegation flows —
distribution `entirius-py-google-calendar-sdk`, import `google_calendar_sdk`.
No Django, no Volkanos coupling. One job: talk to Calendar.

## Commands

| Command | Meaning |
|---|---|
| `make install` | sync dependencies (uv, incl. extras) |
| `make check` | lint + format-check (ruff) |
| `make fix` | auto-fix lint + format |
| `make test` | test suite (pytest) |

## Conventions

- English only: code, docs, commits, branches, PRs.
- MPL-2.0: every non-trivial source file carries the license header (pre-commit inserts it).
- Toolchain: uv + ruff + hatchling + pytest; all config in `pyproject.toml`; `uv.lock` committed.
- Git flow: `master` (production) + `develop` (integration); changes land via PR; semver tag on `master`.
- Never rename the import package `google_calendar_sdk` — it is a public API contract.
- Default: do not commit — git is the user's call.

## Commit Message Format

**NEVER add `Co-Authored-By: Claude ...` (or any other Claude/Anthropic attribution) to commit messages.**

This overrides the default Claude Code behavior of appending a `Co-Authored-By` trailer. Commit messages MUST contain only the user's authored content — no robot footer, no "Generated with Claude Code" line, no co-author trailer.

Same rule applies to PR descriptions: no `Generated with [Claude Code]` footer.

## Architecture

```
src/google_calendar_sdk/
├── __init__.py          # Re-exports the public API
├── client.py            # GoogleCalendarClient — get_busy_periods, is_slot_free, create_event
├── types.py             # BusyPeriod, EventResult dataclasses (frozen)
├── exceptions.py        # CalendarAPIError, CredentialsError
└── _service_cache.py    # Module-level service cache keyed by (credentials_path, impersonate_email)

tests/
└── test_client.py       # Mocks googleapiclient.discovery.build — no live calls
```

## Public API

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

## Design rules

- **No business logic.** SDK doesn't decide what's a valid slot or who's allowed to book. Callers gate on their own rules and call SDK only when ready.
- **Cache is keyed by `(credentials_path, impersonate_email, mtime(credentials_path))`.** Bounded LRU (max 32 entries), thread-safe (double-checked lock). A credential rotation invalidates the cache entry automatically because the mtime changes. Tests reset state via `_service_cache._clear_cache()`.
- **Events are always created on `primary`** of the impersonated user. The `calendar_id` argument is for free-busy queries only (the "shared" calendar pattern).
- **All Google API failures wrap to `CalendarAPIError`.** Callers never see `googleapiclient.errors.HttpError` directly. `HttpError.uri` (which contains the caller-controlled `calendar_id`) is stripped from wrapped messages — only HTTP status + reason are surfaced. Full error details land in the SDK logger with a unique `error_id`.
- **Input validation at the boundary.** `__init__` rejects empty `impersonate_email`, empty/non-email `calendar_id` (other than `"primary"`). `create_event` rejects malformed `attendee_email`, strips control chars from `summary` / `description`, caps lengths.

## Testing

```bash
uv run pytest
```

`googleapiclient.discovery.build` is fully mocked. Cache is reset by `autouse` fixture so tests stay isolated.

## Anti-patterns

DO NOT:
- Import `django.*` or any Volkanos package — this SDK must stay framework-agnostic
- Add config-loading logic (env vars, settings.py reads) — caller passes plain values
- Catch and silently swallow `HttpError` — wrap and raise so callers can decide
- Add a "high-level booking helper" — that belongs in the consumer (e.g. `django-contact-forms.services.booking_service`)
