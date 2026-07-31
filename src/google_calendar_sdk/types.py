# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BusyPeriod:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class EventResult:
    event_id: str
    meet_link: str | None  # None when the event has no Google Meet conference attached
