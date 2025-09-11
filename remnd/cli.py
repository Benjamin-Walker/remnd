from __future__ import annotations
import argparse
import datetime as dt
import re

from .storage import add_reminder, list_reminders


def _parse_duration(spec: str) -> dt.timedelta:
    """
    Accepts: 10m, 1h30m, 45s, 2d4h, or just an integer (minutes).
    """
    spec = spec.strip().lower()
    if not spec:
        raise ValueError("Empty duration.")
    if spec.isdigit():
        return dt.timedelta(minutes=int(spec))
    m = re.fullmatch(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", spec)
    if not m:
        raise ValueError('Invalid duration. Try "10m", "1h30m", "45s", or a number for minutes.')
    d, h, mnt, s = (int(x) if x else 0 for x in m.groups())
    td = dt.timedelta(days=d, hours=h, minutes=mnt, seconds=s)
    if td.total_seconds() <= 0:
        raise ValueError("Duration must be positive.")
    return td


def _to_epoch_utc(local_dt: dt.datetime) -> int:
    # Treat naive as local time; convert to timestamp.
    if local_dt.tzinfo is None:
        local_dt = local_dt.astimezone()
    return int(local_dt.timestamp())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="remnd", description="Simple reminder list (add, list).")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a reminder due after a duration.")
    p_add.add_argument("--in", dest="in_", required=True, help='Duration like "10m", "1h30m", or number (minutes).')
    p_add.add_argument("message", help="Reminder message.")
    p_add.add_argument("--title", "-t", help='Optional title (default "Reminder").')

    sub.add_parser("list", help="List all reminders.")

    return p


def cmd_add(args) -> int:
    delta = _parse_duration(args.in_)
    due = dt.datetime.now() + delta
    rid = add_reminder(title=args.title, message=args.message, due_at=_to_epoch_utc(due))
    print(f"added #{rid} @ {due.strftime('%Y-%m-%d %H:%M:%S')}  {args.message}")
    return 0


def cmd_list(args) -> int:
    rows = list_reminders()
    if not rows:
        print("No reminders.")
        return 0

    print(f"{'ID':>4}  {'Due (local)':<19}  {'Title':<20}  Message")
    print("-" * 80)
    for r in rows:
        due_local = dt.datetime.fromtimestamp(int(r["due_at"])).strftime("%Y-%m-%d %H:%M:%S")
        title = (r["title"] or "Reminder")[:20]
        print(f"{r['id']:>4}  {due_local:<19}  {title:<20}  {r['message']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "add":
        return cmd_add(args)
    elif args.cmd == "list":
        return cmd_list(args)
    else:
        parser.error("unknown command")  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())

