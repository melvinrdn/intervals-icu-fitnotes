"""Command-line interface for syncing Fit Notes to intervals.icu."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from .fitnotes import group_into_sessions, parse_csv
from .intervals import IntervalsClient
from .sync import Match, format_description, match_sessions

DEFAULT_TZ = "Europe/Stockholm"


def _parse_since(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"invalid date '{value}': use YYYY-MM-DD"
        ) from e


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="icu-sync",
        description="Sync Fit Notes strength sessions to intervals.icu activity descriptions.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--csv",
            type=Path,
            help="Path to Fit Notes CSV (overrides FITNOTES_CSV env var)",
        )
        p.add_argument(
            "--since",
            type=_parse_since,
            help="Process activities since this date (YYYY-MM-DD)",
        )
        p.add_argument(
            "--tz",
            default=DEFAULT_TZ,
            help=f"Timezone for matching (default: {DEFAULT_TZ})",
        )

    dry = subparsers.add_parser(
        "dry-run", help="Show what would be synced without writing"
    )
    add_common(dry)

    sync = subparsers.add_parser(
        "sync", help="Write descriptions to intervals.icu (requires --apply)"
    )
    add_common(sync)
    sync.add_argument(
        "--apply",
        action="store_true",
        help="Actually write to intervals.icu (default is dry-run)",
    )

    listcmd = subparsers.add_parser(
        "list-activities",
        help="List strength activities from intervals.icu (no Fit Notes needed)",
    )
    listcmd.add_argument(
        "--since",
        type=_parse_since,
        help="List activities since this date (YYYY-MM-DD)",
    )

    return parser


def _resolve_csv(args: argparse.Namespace) -> Path:
    if args.csv:
        return args.csv
    env_path = os.environ.get("FITNOTES_CSV")
    if not env_path:
        print(
            "error: no CSV path. Set FITNOTES_CSV in .env or use --csv",
            file=sys.stderr,
        )
        sys.exit(2)
    return Path(env_path)


def _resolve_since(args: argparse.Namespace) -> date:
    if args.since:
        return args.since
    env_since = os.environ.get("ICU_SINCE")
    if env_since:
        return _parse_since(env_since)
    print(
        "error: no --since date provided. Use --since YYYY-MM-DD or set ICU_SINCE in .env",
        file=sys.stderr,
    )
    sys.exit(2)


def _load_matches(args: argparse.Namespace, client: IntervalsClient) -> list[Match]:
    csv_path = _resolve_csv(args)
    if not csv_path.exists():
        print(f"error: CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    since = _resolve_since(args)
    tz = ZoneInfo(args.tz)

    print(f"Loading Fit Notes from {csv_path}...")
    sets = parse_csv(csv_path)
    sessions = group_into_sessions(sets)
    print(f"  {len(sets)} sets, {len(sessions)} sessions\n")

    print(f"Fetching activities from intervals.icu since {since}...")
    activities = client.list_activities(oldest=since)
    print(f"  {len(activities)} activities total\n")

    matches = match_sessions(activities, sessions, tz=tz)
    print(f"Matching... {len(matches)} matches found\n")
    return matches


def _print_match(m: Match, new_desc: str, label: str) -> None:
    n_sets = sum(len(s.sets) for s in m.sessions)
    names = " + ".join(dict.fromkeys(s.name for s in m.sessions))
    print(f"[{label}] activity {m.activity.id} ({m.activity.type})")
    print(f"  intervals.icu: {m.activity.start_date_local}")
    print(f"  fit notes:     {names} ({n_sets} sets)")
    print()
    print(new_desc)
    print("---")


def cmd_dry_run(args: argparse.Namespace) -> int:
    with IntervalsClient.from_env() as client:
        matches = _load_matches(args, client)

    if not matches:
        print("No matches. Check timezone, --since, and activity types.")
        return 0

    print("=" * 70)
    for m in matches:
        new_desc = format_description(m.sessions)
        label = "UNCHANGED" if m.activity.description == new_desc else "WOULD UPDATE"
        _print_match(m, new_desc, label)

    print("Dry run complete. No changes sent.")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    if not args.apply:
        print("--apply not set, running as dry-run.\n")

    with IntervalsClient.from_env() as client:
        matches = _load_matches(args, client)

        if not matches:
            print("No matches.")
            return 0

        updated = 0
        skipped = 0
        for m in matches:
            new_desc = format_description(m.sessions)
            if m.activity.description == new_desc:
                skipped += 1
                continue

            if args.apply:
                client.update_activity_description(m.activity.id, new_desc)
                print(f"updated {m.activity.id} ({m.activity.type})")
            else:
                _print_match(m, new_desc, "WOULD UPDATE")
            updated += 1

    if args.apply:
        print(f"\n{updated} activities updated, {skipped} unchanged.")
    else:
        print(f"\n{updated} would be updated, {skipped} unchanged. Re-run with --apply to write.")
    return 0


def cmd_list_activities(args: argparse.Namespace) -> int:
    since = _resolve_since(args)
    with IntervalsClient.from_env() as client:
        activities = client.list_activities(oldest=since)

    strength = [a for a in activities if a.type in {"WeightTraining", "Workout"}]
    print(f"{len(activities)} total activities, {len(strength)} strength:\n")
    for a in strength:
        desc_preview = (a.description or "").split("\n")[0][:60]
        print(
            f"  {a.start_date_local}  {a.id:>10s}  {a.type:<15s}  {desc_preview}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = _build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "dry-run": cmd_dry_run,
        "sync": cmd_sync,
        "list-activities": cmd_list_activities,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())