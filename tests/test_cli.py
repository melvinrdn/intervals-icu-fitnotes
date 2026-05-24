"""Tests for the CLI."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from intervals_icu_fitnotes.cli import _build_parser, _parse_since, main


class TestParseSince:
    def test_valid_date(self) -> None:
        assert _parse_since("2025-06-01") == date(2025, 6, 1)

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(argparse.ArgumentTypeError):
            _parse_since("01/06/2025")

    def test_garbage_raises(self) -> None:
        with pytest.raises(argparse.ArgumentTypeError):
            _parse_since("not-a-date")


class TestParser:
    def test_dry_run_minimal(self) -> None:
        args = _build_parser().parse_args(["dry-run"])
        assert args.command == "dry-run"
        assert args.csv is None
        assert args.since is None

    def test_sync_requires_explicit_apply(self) -> None:
        args = _build_parser().parse_args(["sync"])
        assert args.apply is False

        args = _build_parser().parse_args(["sync", "--apply"])
        assert args.apply is True

    def test_csv_path_argument(self) -> None:
        args = _build_parser().parse_args(["dry-run", "--csv", "/tmp/x.csv"])
        assert args.csv == Path("/tmp/x.csv")

    def test_since_parsed(self) -> None:
        args = _build_parser().parse_args(["dry-run", "--since", "2025-06-01"])
        assert args.since == date(2025, 6, 1)

    def test_no_command_fails(self) -> None:
        with pytest.raises(SystemExit):
            _build_parser().parse_args([])

    def test_unknown_command_fails(self) -> None:
        with pytest.raises(SystemExit):
            _build_parser().parse_args(["nope"])


class TestMainDispatch:
    def test_dispatches_to_handler(self) -> None:
        with patch("intervals_icu_fitnotes.cli.cmd_dry_run") as mock_handler:
            mock_handler.return_value = 0
            with patch("intervals_icu_fitnotes.cli.load_dotenv"):
                result = main(["dry-run"])
        assert result == 0
        mock_handler.assert_called_once()