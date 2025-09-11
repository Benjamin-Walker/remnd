from __future__ import annotations
import argparse
import datetime as dt
import re

from .storage import add_reminder, delete_reminder, list_reminders, mark_complete


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
    p = argparse.ArgumentParser(prog="remnd", description="Simple reminder list (add, list, comp, del).")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a reminder due after a duration.")
    p_add.add_argument("in_", help='Duration like "10m", "1h30m", or number (minutes).')
    p_add.add_argument("title", help="Reminder title.")
    p_add.add_argument("--note", "-n", help='Optional note (default "-").')

    p_list = sub.add_parser("list", help="List reminders")
    p_list.add_argument("--all", action="store_true", help="Include completed reminders.")

    p_comp = sub.add_parser("comp", help="Mark a reminder as completed by ID.")
    p_comp.add_argument("id", type=int)

    p_del = sub.add_parser("del", help="Delete a reminder by ID.")
    p_del.add_argument("id", type=int)

    return p


def cmd_add(args) -> int:
    delta = _parse_duration(args.in_)
    due = dt.datetime.now() + delta
    rid = add_reminder(title=args.title, note=args.note, due_at=_to_epoch_utc(due))
    print(f"added #{rid} @ {due.strftime('%Y-%m-%d %H:%M:%S')}  {args.note}")
    return 0


def cmd_list(args) -> int:
    rows = list_reminders(include_done=args.all)
    if not rows:
        print("No reminders.")
        return 0

    print(f"{'ID':>4}  {'Due (local)':<19}  {'Title':<20}  {'Done':<5}  {'Note'}")
    print("-" * 80)
    for r in rows:
        due_local = dt.datetime.fromtimestamp(int(r["due_at"])).strftime("%Y-%m-%d %H:%M:%S")
        title = (r["title"] or "Reminder")[:20]
        status = " " + u'\u2705' if r["completed_at"] is not None else " " + u'\u274C'
        print(f"{r['id']:>4}  {due_local:<19}  {title:<20}  {status:<4}  {r['note']}")
    return 0


def cmd_comp(args) -> int:
    ok = mark_complete(args.id)
    if ok:
        print(f"marked #{args.id} as done")
        return 0
    print(f"no active reminder #{args.id} (maybe already done or wrong id)")
    return 1


def cmd_del(args) -> int:
    ok = delete_reminder(args.id)
    if ok:
        print(f"deleted #{args.id}")
        return 0
    print(f"no reminder #{args.id}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "add":
        return cmd_add(args)
    elif args.cmd == "list":
        return cmd_list(args)
    elif args.cmd == "comp":
        return cmd_comp(args)
    elif args.cmd == "del":
        return cmd_del(args)
    else:
        parser.error("unknown command")  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())

