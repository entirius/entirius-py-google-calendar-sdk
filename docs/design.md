# Design

## Design rules

- **No business logic.** SDK doesn't decide what's a valid slot or who's allowed to book. Callers gate on their own rules and call SDK only when ready.
- **Cache is keyed by `(credentials_path, impersonate_email, mtime(credentials_path))`.** Bounded LRU (max 32 entries), thread-safe (double-checked lock). A credential rotation invalidates the cache entry automatically because the mtime changes. Tests reset state via `_service_cache._clear_cache()`.
- **Events are always created on `primary`** of the impersonated user. The `calendar_id` argument is for free-busy queries only (the "shared" calendar pattern).
- **All Google API failures wrap to `CalendarAPIError`.** Callers never see `googleapiclient.errors.HttpError` directly. `HttpError.uri` (which contains the caller-controlled `calendar_id`) is stripped from wrapped messages — only HTTP status + reason are surfaced. Full error details land in the SDK logger with a unique `error_id`.
- **Input validation at the boundary.** `__init__` rejects empty `impersonate_email`, empty/non-email `calendar_id` (other than `"primary"`). `create_event` rejects malformed `attendee_email`, strips control chars from `summary` / `description`, caps lengths.

## Anti-patterns

DO NOT:
- Import `django.*` or any Volkanos package — this SDK must stay framework-agnostic
- Add config-loading logic (env vars, settings.py reads) — caller passes plain values
- Catch and silently swallow `HttpError` — wrap and raise so callers can decide
- Add a "high-level booking helper" — that belongs in the consumer (e.g. `django-contact-forms.services.booking_service`)
