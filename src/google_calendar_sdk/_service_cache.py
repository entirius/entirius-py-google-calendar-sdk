# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Bounded, thread-safe cache so discovery doc + signed JWT stay warm across calls.

The cache key is `(credentials_path, impersonate_email, mtime)` — re-stating the file
modification time means a credential rotation invalidates the entry automatically on
the next call.
"""

import logging
import os
import threading
import uuid
from collections import OrderedDict
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

from google_calendar_sdk.exceptions import CalendarAPIError, CredentialsError

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
_MAX_ENTRIES = 32

logger = logging.getLogger(__name__)

_cache: OrderedDict[tuple[str, str, float], Any] = OrderedDict()
_lock = threading.Lock()


def get_service(credentials_path: str, impersonate_email: str) -> Any:
    """Return cached Google Calendar service, building it on first miss for this credential triple."""
    mtime = _stat_mtime(credentials_path)
    key = (credentials_path, impersonate_email, mtime)

    if (service := _cache.get(key)) is not None:
        _cache.move_to_end(key)
        return service

    with _lock:
        if (service := _cache.get(key)) is not None:  # double-checked
            _cache.move_to_end(key)
            return service

        credentials = _load_credentials(credentials_path, impersonate_email)
        service = _build_service(credentials)

        _cache[key] = service
        _cache.move_to_end(key)
        if len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)
        return service


def _stat_mtime(credentials_path: str) -> float:
    try:
        return os.path.getmtime(credentials_path)
    except OSError as exc:
        error_id = uuid.uuid4().hex[:12]
        logger.error("Cannot stat credentials path %s [error_id=%s]: %s", credentials_path, error_id, exc)
        raise CredentialsError(f"Cannot load service-account credentials [{error_id}]") from exc


def _load_credentials(credentials_path: str, impersonate_email: str) -> service_account.Credentials:
    try:
        return service_account.Credentials.from_service_account_file(
            credentials_path, scopes=CALENDAR_SCOPES, subject=impersonate_email
        )
    except Exception as exc:
        error_id = uuid.uuid4().hex[:12]
        logger.error("Cannot load credentials from %s [error_id=%s]: %s", credentials_path, error_id, exc)
        raise CredentialsError(f"Cannot load service-account credentials [{error_id}]") from exc


def _build_service(credentials: service_account.Credentials) -> Any:
    try:
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)
    except Exception as exc:
        error_id = uuid.uuid4().hex[:12]
        logger.error("Calendar discovery build failed [error_id=%s]: %s", error_id, exc)
        raise CalendarAPIError(f"Calendar discovery build failed [{error_id}]") from exc


def _clear_cache() -> None:
    """Test-only helper. Underscore to discourage production callers."""
    with _lock:
        _cache.clear()
