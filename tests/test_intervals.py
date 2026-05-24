"""Tests for the intervals.icu client."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from intervals_icu_fitnotes.intervals import (
    API_BASE,
    Activity,
    IntervalsClient,
    _parse_activity,
)


class TestParseActivity:
    def test_minimal_payload(self) -> None:
        a = _parse_activity(
            {
                "id": 12345,
                "type": "WeightTraining",
                "name": "Push",
                "start_date_local": "2025-02-23T10:13:53",
                "elapsed_time": 3600,
                "description": "set 1\nset 2",
            }
        )
        assert a == Activity(
            id="12345",
            type="WeightTraining",
            name="Push",
            start_date_local=datetime(2025, 2, 23, 10, 13, 53),
            elapsed_time_s=3600,
            description="set 1\nset 2",
        )

    def test_id_coerced_to_string(self) -> None:
        a = _parse_activity(
            {
                "id": 99,
                "type": "Run",
                "start_date_local": "2025-02-23T10:00:00",
                "elapsed_time": 1800,
            }
        )
        assert a.id == "99"
        assert isinstance(a.id, str)

    def test_missing_optional_fields(self) -> None:
        a = _parse_activity(
            {
                "id": 1,
                "type": "Ride",
                "start_date_local": "2025-02-23T10:00:00",
            }
        )
        assert a.name == ""
        assert a.description is None
        assert a.elapsed_time_s == 0


class TestFromEnv:
    def test_reads_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ICU_API_KEY", "secret123")
        monkeypatch.delenv("ICU_ATHLETE_ID", raising=False)
        with patch("intervals_icu_fitnotes.intervals.load_dotenv"):
            client = IntervalsClient.from_env()
        assert client._session.auth == ("API_KEY", "secret123")
        assert client._athlete_id == "0"  # default fallback

    def test_reads_athlete_id_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ICU_API_KEY", "secret123")
        monkeypatch.setenv("ICU_ATHLETE_ID", "i42")
        with patch("intervals_icu_fitnotes.intervals.load_dotenv"):
            client = IntervalsClient.from_env()
        assert client._athlete_id == "i42"

    def test_raises_if_key_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ICU_API_KEY", raising=False)
        with patch("intervals_icu_fitnotes.intervals.load_dotenv"):
            with pytest.raises(RuntimeError, match="ICU_API_KEY"):
                IntervalsClient.from_env()


class TestListActivities:
    def test_calls_correct_endpoint(self) -> None:
        client = IntervalsClient(api_key="key", athlete_id="i42")
        mock_response = MagicMock()
        mock_response.json.return_value = []

        with patch.object(
            client._session, "get", return_value=mock_response
        ) as mock_get:
            client.list_activities(oldest=date(2025, 2, 1))

        url = mock_get.call_args.args[0]
        params = mock_get.call_args.kwargs["params"]
        assert url == f"{API_BASE}/athlete/i42/activities"
        assert params == {"oldest": "2025-02-01"}

    def test_includes_newest_when_provided(self) -> None:
        client = IntervalsClient(api_key="key")
        mock_response = MagicMock()
        mock_response.json.return_value = []

        with patch.object(
            client._session, "get", return_value=mock_response
        ) as mock_get:
            client.list_activities(
                oldest=date(2025, 2, 1), newest=date(2025, 2, 28)
            )

        params = mock_get.call_args.kwargs["params"]
        assert params == {"oldest": "2025-02-01", "newest": "2025-02-28"}

    def test_parses_response(self) -> None:
        client = IntervalsClient(api_key="key")
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "type": "WeightTraining",
                "name": "Push",
                "start_date_local": "2025-02-23T10:00:00",
                "elapsed_time": 3600,
                "description": None,
            },
            {
                "id": 2,
                "type": "Run",
                "name": "Easy run",
                "start_date_local": "2025-02-24T07:00:00",
                "elapsed_time": 2400,
                "description": "felt good",
            },
        ]

        with patch.object(client._session, "get", return_value=mock_response):
            activities = client.list_activities(oldest=date(2025, 2, 1))

        assert len(activities) == 2
        assert activities[0].type == "WeightTraining"
        assert activities[1].description == "felt good"

    def test_raises_on_http_error(self) -> None:
        client = IntervalsClient(api_key="key")
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("401")

        with patch.object(client._session, "get", return_value=mock_response):
            with pytest.raises(requests.HTTPError):
                client.list_activities(oldest=date(2025, 2, 1))


class TestUpdateActivityDescription:
    def test_calls_correct_endpoint_with_payload(self) -> None:
        client = IntervalsClient(api_key="key", athlete_id="i42")
        mock_response = MagicMock()

        with patch.object(
            client._session, "put", return_value=mock_response
        ) as mock_put:
            client.update_activity_description("act-123", "new description")

        url = mock_put.call_args.args[0]
        payload = mock_put.call_args.kwargs["json"]
        assert url == f"{API_BASE}/activity/act-123"
        assert payload == {"description": "new description"}

    def test_raises_on_http_error(self) -> None:
        client = IntervalsClient(api_key="key")
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500")

        with patch.object(client._session, "put", return_value=mock_response):
            with pytest.raises(requests.HTTPError):
                client.update_activity_description("act-1", "x")


class TestContextManager:
    def test_closes_session_on_exit(self) -> None:
        client = IntervalsClient(api_key="key")
        with patch.object(client._session, "close") as mock_close:
            with client:
                pass
        mock_close.assert_called_once()