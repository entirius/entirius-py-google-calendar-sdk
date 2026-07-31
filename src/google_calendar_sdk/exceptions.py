# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.


class CalendarAPIError(Exception):
    """Base for all SDK errors. Wraps any failure from the Google Calendar API
    (HTTP, network, parsing). Catching this catches credential failures too —
    see ``CredentialsError``."""


class CredentialsError(CalendarAPIError):
    """Raised when service-account credentials cannot be loaded or refreshed.

    **Subclass of CalendarAPIError** — this relationship is part of the public
    API contract. Callers may write ``except CalendarAPIError`` once and catch
    both initialisation and runtime failures, or distinguish via ``except
    CredentialsError`` first when they need to.
    """
