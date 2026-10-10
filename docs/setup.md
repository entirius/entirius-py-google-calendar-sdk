# Setup

## Service-account setup

1. Create a Google Cloud project, enable the Calendar API.
2. Create a service account with **domain-wide delegation**.
3. In Google Workspace admin: grant the service account the scope `https://www.googleapis.com/auth/calendar`.
4. Download the JSON key. Mount it inside the container as a private file (e.g. `/app/credentials/sa.json`).
5. The `impersonate_email` argument is the real user the service account acts as — events are created on that user's `primary` calendar so they receive the invite and own the event.

## Free-busy semantics

`get_busy_periods` always queries the impersonated user's `primary` calendar. If `calendar_id` is set to anything other than `"primary"`, the shared calendar is queried as well — and busy periods from both are merged. This is the standard pattern for "the consultant has both a personal calendar AND a shared booking calendar; both must be free".
