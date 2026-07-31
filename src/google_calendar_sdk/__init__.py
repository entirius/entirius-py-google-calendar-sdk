"""Google Calendar API v3 wrapper for service-account flows."""

from google_calendar_sdk.client import GoogleCalendarClient
from google_calendar_sdk.exceptions import CalendarAPIError, CredentialsError
from google_calendar_sdk.types import BusyPeriod, EventResult

__all__ = ["GoogleCalendarClient", "CalendarAPIError", "CredentialsError", "BusyPeriod", "EventResult"]

__version__ = "1.0.1"
