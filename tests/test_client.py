# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from google_calendar_sdk import BusyPeriod, CalendarAPIError, CredentialsError, EventResult, GoogleCalendarClient
from google_calendar_sdk._service_cache import _clear_cache, get_service


@pytest.fixture(autouse=True)
def _reset_cache():
    _clear_cache()
    yield
    _clear_cache()


def _build_service(freebusy_response: dict | None = None, insert_response: dict | None = None) -> MagicMock:
    service = MagicMock()
    if freebusy_response is not None:
        service.freebusy.return_value.query.return_value.execute.return_value = freebusy_response
    if insert_response is not None:
        service.events.return_value.insert.return_value.execute.return_value = insert_response
    return service


def _make_client(service: MagicMock, *, calendar_id: str = "shared@group.calendar.google.com") -> GoogleCalendarClient:
    with patch("google_calendar_sdk.client.get_service", return_value=service):
        return GoogleCalendarClient(
            credentials_path="/fake/sa.json", impersonate_email="bookings@example.com", calendar_id=calendar_id
        )


# ---------------- get_busy_periods + is_slot_free ----------------


def test_get_busy_periods_returns_merged_busy_slots_from_all_calendars():
    service = _build_service(
        freebusy_response={
            "calendars": {
                "primary": {"busy": [{"start": "2026-04-20T10:00:00+00:00", "end": "2026-04-20T11:00:00+00:00"}]},
                "shared@group.calendar.google.com": {"busy": []},
            }
        }
    )
    client = _make_client(service)
    busy = client.get_busy_periods(datetime(2026, 4, 20, tzinfo=UTC), datetime(2026, 4, 21, tzinfo=UTC), timezone="UTC")
    assert busy == [BusyPeriod(datetime(2026, 4, 20, 10, 0, tzinfo=UTC), datetime(2026, 4, 20, 11, 0, tzinfo=UTC))]


def test_get_busy_periods_returns_empty_when_calendars_key_missing():
    service = _build_service(freebusy_response={})
    client = _make_client(service)
    assert (
        client.get_busy_periods(datetime(2026, 4, 20, tzinfo=UTC), datetime(2026, 4, 21, tzinfo=UTC), timezone="UTC")
        == []
    )


def test_is_slot_free_returns_true_when_no_overlapping_events():
    service = _build_service(freebusy_response={"calendars": {"primary": {"busy": []}}})
    client = _make_client(service)
    assert client.is_slot_free(
        datetime(2026, 4, 20, 9, 0, tzinfo=UTC), datetime(2026, 4, 20, 9, 30, tzinfo=UTC), timezone="UTC"
    )


def test_is_slot_free_returns_false_when_busy_period_present():
    service = _build_service(
        freebusy_response={
            "calendars": {
                "primary": {"busy": [{"start": "2026-04-20T09:00:00+00:00", "end": "2026-04-20T10:00:00+00:00"}]}
            }
        }
    )
    client = _make_client(service)
    assert not client.is_slot_free(
        datetime(2026, 4, 20, 9, 0, tzinfo=UTC), datetime(2026, 4, 20, 9, 30, tzinfo=UTC), timezone="UTC"
    )


def test_dedupe_skips_primary_calendar_id():
    service = _build_service(freebusy_response={"calendars": {"primary": {"busy": []}}})
    client = _make_client(service, calendar_id="primary")
    client.get_busy_periods(datetime(2026, 4, 20, tzinfo=UTC), datetime(2026, 4, 21, tzinfo=UTC), timezone="UTC")
    body = service.freebusy.return_value.query.call_args.kwargs["body"]
    assert body["items"] == [{"id": "primary"}]


# ---------------- create_event ----------------


def test_create_event_returns_event_id_and_meet_link():
    service = _build_service(insert_response={"id": "evt_123", "hangoutLink": "https://meet.google.com/abc-defg-hij"})
    client = _make_client(service)
    result = client.create_event(
        start=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
        end=datetime(2026, 4, 20, 9, 30, tzinfo=UTC),
        summary="Booking - Jan",
        attendee_email="jan@example.com",
        description="...",
        timezone="UTC",
    )
    assert result == EventResult(event_id="evt_123", meet_link="https://meet.google.com/abc-defg-hij")
    insert_kwargs = service.events.return_value.insert.call_args.kwargs
    assert insert_kwargs["calendarId"] == "primary"
    assert insert_kwargs["sendUpdates"] == "all"
    assert insert_kwargs["conferenceDataVersion"] == 1


def test_create_event_without_meet_link_returns_none_for_meet_link():
    service = _build_service(insert_response={"id": "evt_xyz", "hangoutLink": ""})
    client = _make_client(service)
    result = client.create_event(
        start=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
        end=datetime(2026, 4, 20, 9, 30, tzinfo=UTC),
        summary="Booking",
        attendee_email="jan@example.com",
        timezone="UTC",
        create_meet_link=False,
    )
    assert result.meet_link is None
    insert_kwargs = service.events.return_value.insert.call_args.kwargs
    assert insert_kwargs["conferenceDataVersion"] == 0
    assert "conferenceData" not in insert_kwargs["body"]


def test_create_event_strips_control_chars_from_summary_and_description():
    service = _build_service(insert_response={"id": "evt_x", "hangoutLink": ""})
    client = _make_client(service)
    client.create_event(
        start=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
        end=datetime(2026, 4, 20, 9, 30, tzinfo=UTC),
        summary="Subject\r\nInjected: phish",
        attendee_email="jan@example.com",
        description="Hello\x00world\nLine 2",
        timezone="UTC",
    )
    sent_body = service.events.return_value.insert.call_args.kwargs["body"]
    assert sent_body["summary"] == "SubjectInjected: phish"
    assert sent_body["description"] == "HelloworldLine 2"


def test_create_event_caps_summary_length():
    service = _build_service(insert_response={"id": "evt_x", "hangoutLink": ""})
    client = _make_client(service)
    client.create_event(
        start=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
        end=datetime(2026, 4, 20, 9, 30, tzinfo=UTC),
        summary="A" * 500,
        attendee_email="jan@example.com",
        timezone="UTC",
    )
    sent_body = service.events.return_value.insert.call_args.kwargs["body"]
    assert len(sent_body["summary"]) == 200


def test_create_event_rejects_malformed_attendee_email():
    service = _build_service(insert_response={"id": "evt_x", "hangoutLink": ""})
    client = _make_client(service)
    with pytest.raises(ValueError, match="attendee_email"):
        client.create_event(
            start=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
            end=datetime(2026, 4, 20, 9, 30, tzinfo=UTC),
            summary="x",
            attendee_email="not-an-email",
            timezone="UTC",
        )


# ---------------- HttpError wrapping ----------------


def test_freebusy_http_error_wraps_to_calendar_api_error_without_uri():
    service = MagicMock()
    resp = MagicMock(status=500)
    err = HttpError(resp=resp, content=b"boom")
    err.reason = "Internal Server Error"
    service.freebusy.return_value.query.return_value.execute.side_effect = err
    client = _make_client(service)
    with pytest.raises(CalendarAPIError) as excinfo:
        client.get_busy_periods(datetime(2026, 4, 20, tzinfo=UTC), datetime(2026, 4, 21, tzinfo=UTC), timezone="UTC")
    assert "freebusy.query" in str(excinfo.value)
    assert "500" in str(excinfo.value)
    assert "shared@group.calendar.google.com" not in str(excinfo.value)


def test_create_event_http_error_wraps_to_calendar_api_error():
    service = MagicMock()
    resp = MagicMock(status=403)
    err = HttpError(resp=resp, content=b"forbidden")
    err.reason = "Forbidden"
    service.events.return_value.insert.return_value.execute.side_effect = err
    client = _make_client(service)
    with pytest.raises(CalendarAPIError) as excinfo:
        client.create_event(
            start=datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
            end=datetime(2026, 4, 20, 9, 30, tzinfo=UTC),
            summary="Booking",
            attendee_email="jan@example.com",
            timezone="UTC",
        )
    assert "events.insert" in str(excinfo.value)
    assert "403" in str(excinfo.value)


# ---------------- Constructor validation ----------------


def test_init_rejects_empty_impersonate_email():
    with patch("google_calendar_sdk.client.get_service", return_value=MagicMock()):
        with pytest.raises(ValueError, match="impersonate_email"):
            GoogleCalendarClient(credentials_path="/fake/sa.json", impersonate_email="", calendar_id="primary")


def test_init_rejects_empty_calendar_id():
    with patch("google_calendar_sdk.client.get_service", return_value=MagicMock()):
        with pytest.raises(ValueError, match="calendar_id"):
            GoogleCalendarClient(credentials_path="/fake/sa.json", impersonate_email="x@y.com", calendar_id="")


def test_init_rejects_non_email_calendar_id():
    with patch("google_calendar_sdk.client.get_service", return_value=MagicMock()):
        with pytest.raises(ValueError, match="email-shaped"):
            GoogleCalendarClient(
                credentials_path="/fake/sa.json", impersonate_email="x@y.com", calendar_id="../etc/passwd"
            )


def test_init_accepts_primary_calendar_id():
    with patch("google_calendar_sdk.client.get_service", return_value=MagicMock()):
        GoogleCalendarClient(credentials_path="/fake/sa.json", impersonate_email="x@y.com", calendar_id="primary")


def test_init_accepts_email_calendar_id():
    with patch("google_calendar_sdk.client.get_service", return_value=MagicMock()):
        GoogleCalendarClient(
            credentials_path="/fake/sa.json",
            impersonate_email="x@y.com",
            calendar_id="shared@group.calendar.google.com",
        )


# ---------------- _service_cache.get_service ----------------


def test_get_service_raises_credentials_error_when_file_missing(tmp_path):
    missing = tmp_path / "no-such-file.json"
    with pytest.raises(CredentialsError) as excinfo:
        get_service(str(missing), "x@example.com")
    msg = str(excinfo.value)
    # The path itself MUST NOT leak in the public message — only error_id
    assert str(missing) not in msg
    assert "[" in msg and "]" in msg  # error_id bracketed


def test_get_service_raises_credentials_error_on_invalid_json(tmp_path):
    bad = tmp_path / "bad-creds.json"
    bad.write_text("not json")
    with pytest.raises(CredentialsError) as excinfo:
        get_service(str(bad), "x@example.com")
    assert "not json" not in str(excinfo.value)  # file content MUST NOT leak


def test_get_service_returns_cached_instance_on_second_call(tmp_path):
    creds_file = tmp_path / "sa.json"
    creds_file.write_text("{}")  # content irrelevant; we patch the loader
    sentinel = MagicMock(name="ServiceProxy")
    with (
        patch(
            "google_calendar_sdk._service_cache.service_account.Credentials.from_service_account_file",
            return_value=MagicMock(),
        ),
        patch("google_calendar_sdk._service_cache.build", return_value=sentinel),
    ):
        first = get_service(str(creds_file), "x@example.com")
        second = get_service(str(creds_file), "x@example.com")
    assert first is second is sentinel


def test_get_service_invalidates_cache_when_credentials_file_mtime_changes(tmp_path):
    creds_file = tmp_path / "sa.json"
    creds_file.write_text("v1")
    sentinel_a = MagicMock(name="ServiceA")
    sentinel_b = MagicMock(name="ServiceB")
    with (
        patch(
            "google_calendar_sdk._service_cache.service_account.Credentials.from_service_account_file",
            return_value=MagicMock(),
        ),
        patch("google_calendar_sdk._service_cache.build", side_effect=[sentinel_a, sentinel_b]),
    ):
        first = get_service(str(creds_file), "x@example.com")
        # Force mtime change
        import os

        new_mtime = creds_file.stat().st_mtime + 100
        os.utime(str(creds_file), (new_mtime, new_mtime))
        second = get_service(str(creds_file), "x@example.com")
    assert first is sentinel_a
    assert second is sentinel_b


def test_clear_cache_removes_all_entries(tmp_path):
    creds_file = tmp_path / "sa.json"
    creds_file.write_text("{}")
    sentinel_a = MagicMock(name="ServiceA")
    sentinel_b = MagicMock(name="ServiceB")
    with (
        patch(
            "google_calendar_sdk._service_cache.service_account.Credentials.from_service_account_file",
            return_value=MagicMock(),
        ),
        patch("google_calendar_sdk._service_cache.build", side_effect=[sentinel_a, sentinel_b]),
    ):
        first = get_service(str(creds_file), "x@example.com")
        _clear_cache()
        second = get_service(str(creds_file), "x@example.com")
    assert first is sentinel_a
    assert second is sentinel_b
