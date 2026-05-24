"""Minimal intervals.icu API client for activity sync."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Self

import requests
from dotenv import load_dotenv

API_BASE = "https://intervals.icu/api/v1"
DEFAULT_TIMEOUT = 30


@dataclass(frozen=True)
class Activity:
    """An activity as returned by intervals.icu."""

    id: str
    type: str
    name: str
    start_date_local: datetime  # naive: local time as stored by intervals
    elapsed_time_s: int  # total duration in seconds
    description: str | None


class IntervalsClient:
    """Thin client over the intervals.icu REST API.

    Authenticates via HTTP Basic with username 'API_KEY' and the personal API key
    as password. Use athlete_id '0' to auto-resolve from the key.
    """

    def __init__(self, api_key: str, athlete_id: str = "0") -> None:
        self._athlete_id = athlete_id
        self._session = requests.Session()
        self._session.auth = ("API_KEY", api_key)

    @classmethod
    def from_env(cls) -> Self:
        """Build a client from ICU_API_KEY and ICU_ATHLETE_ID (env or .env file)."""
        load_dotenv()
        key = os.environ.get("ICU_API_KEY")
        if not key:
            raise RuntimeError("ICU_API_KEY not set in environment or .env file")
        athlete_id = os.environ.get("ICU_ATHLETE_ID", "0")
        return cls(api_key=key, athlete_id=athlete_id)

    def list_activities(
        self,
        oldest: date,
        newest: date | None = None,
    ) -> list[Activity]:
        """List activities in a date range (inclusive)."""
        params = {"oldest": oldest.isoformat()}
        if newest is not None:
            params["newest"] = newest.isoformat()

        r = self._session.get(
            f"{API_BASE}/athlete/{self._athlete_id}/activities",
            params=params,
            timeout=DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
        return [_parse_activity(a) for a in r.json()]

    def update_activity_description(self, activity_id: str, description: str) -> None:
        """Overwrite the description of an existing activity."""
        r = self._session.put(
            f"{API_BASE}/athlete/{self._athlete_id}/activities/{activity_id}",
            json={"description": description},
            timeout=DEFAULT_TIMEOUT,
        )
        r.raise_for_status()

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _parse_activity(payload: dict) -> Activity:
    return Activity(
        id=str(payload["id"]),
        type=payload["type"],
        name=payload.get("name", ""),
        start_date_local=datetime.fromisoformat(payload["start_date_local"]),
        elapsed_time_s=int(payload.get("elapsed_time") or 0),
        description=payload.get("description"),
    )