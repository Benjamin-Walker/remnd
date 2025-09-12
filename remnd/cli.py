rom __future__ import annotations
import argparse
import datetime as dt
import re
import os
import shutil
from pathlib import Path
import subprocess
import textwrap

from .storage import (
    add_reminder, delete_reminder, list_reminders, mark_complete,
    due_unnotified, mark_notified, due_active, due_renotify, 
    get_reminder
)


SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"
NOTIFY_SERVICE = "remnd-notify.service"
NOTIFY_TIMER = "remnd-notify.timer"


NOTIFY_SERVICE_UNIT = textwrap.dedent(f"""\
[Unit]
Description=Send notifications for due remnd reminders

[Service]
Type=oneshot
ExecStart={shutil.which("remnd") or "%h/.local/bin/remnd"} notify-due
""")


NOTIFY_TIMER_UNIT = """\
[Unit]
Description=Check for due remnd reminders every minute

[Timer]
OnCalendar=*:0/1
Persistent=true
Unit=remnd-notify.service

[Install]
WantedBy=default.target
"""


CATCHUP_SERVICE = "remnd-catchup.service"
CATCHUP_TIMER = "remnd-catchup.timer"


CATCHUP_SERVICE_UNIT = textwrap.dedent(f"""\
[Unit]
Description=Re-notify all due, uncompleted remnd reminders at login
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=oneshot
ExecStart={shutil.which("remnd") or "%h/.local/bin/remnd"} notify-catchup
""")


CATCHUP_TIMER_UNIT = """\
[Unit]
Description=Run remnd catch-up once shortly after user login

[Timer]
OnActiveSec=5s
AccuracySec=1s
Unit=remnd-catchup.service
Persistent=false

[Install]
WantedBy=default.target
"""


RENOTIFY_SERVICE = "remnd-renotify.service"
RENOTIFY_TIMER = "remnd-renotify.timer"


RENOTIFY_SERVICE_UNIT = textwrap.dedent(f"""\
[Unit]
Description=Re-notify overdue remnd reminders

[Service]
Type=oneshot
ExecStart={shutil.which("remnd") or "%h/.local/bin/remnd"} notify-renotify
""")


RENOTIFY_TIMER_UNIT = """\
[Unit]
Description=Check for overdue remnd reminders every hour

[Timer]
OnCalendar=*:0/60
Persistent=true
Unit=remnd-renotify.service

[Install]
WantedBy=default.target
"""


def _systemctl_user(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", "--user", *args], check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def cmd_install() -> int:
    SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)
    (SYSTEMD_DIR / NOTIFY_SERVICE).write_text(NOTIFY_SERVICE_UNIT)
    (SYSTEMD_DIR / NOTIFY_TIMER).write_text(NOTIFY_TIMER_UNIT)
    (SYSTEMD_DIR / CATCHUP_SERVICE).write_text(CATCHUP_SERVICE_UNIT)
    (SYSTEMD_DIR / CATCHUP_TIMER).write_text(CATCHUP_TIMER_UNIT)
    (SYSTEMD_DIR / RENOTIFY_SERVICE).write_text(RENOTIFY_SERVICE_UNIT)
    (SYSTEMD_DIR / RENOTIFY_TIMER).write_text(RENOTIFY_TIMER_UNIT)
    _systemctl_user("daemon-reload")
    _systemctl_user("enable", "--now", NOTIFY_TIMER)
    _systemctl_user("enable", "--now", CATCHUP_TIMER)
    _systemctl_user("enable", "--now", RENOTIFY_TIMER)
    print(u'\u2705' + " Installed: notifier, renotifier, and login catch-up.")
    return 0


def cmd_uninstall() -> int:
    _systemctl_user("disable", "--now", NOTIFY_TIMER)
    _systemctl_user("disable", "--now", CATCHUP_TIMER)
    _systemctl_user("disable", "--now", RENOTIFY_TIMER)
    try:
        (SYSTEMD_DIR / NOTIFY_SERVICE).unlink(missing_ok=True)
        (SYSTEMD_DIR / NOTIFY_TIMER).unlink(missing_ok=True)
        (SYSTEMD_DIR / CATCHUP_SERVICE).unlink(missing_ok=True)
        (SYSTEMD_DIR / CATCHUP_TIMER).unlink(missing_ok=True)
        (SYSTEMD_DIR / RENOTIFY_SERVICE).unlink(missing_ok=True)
        (SYSTEMD_DIR / RENOTIFY_TIMER).unlink(missing_ok=True)
    except Exception:
        pass
    _systemctl_user("daemon-reload")
    print(u'\u2705' + " Uninstalled notifier, renotifier, and login catch-up.")
    return 0


def _parse_duration(spec: str) -> dt.timedelta:
    """
    Accepts: 10m, 1h30m, 45s, 2d4h, 2w, or just an integer (minutes).
    (For adding the initial due time.)
    """
    spec = spec.strip().lower()
    if not spec:
        raise ValueError("Empty duration.")
    if spec.isdigit():
        return dt.timedelta(minutes=int(spec))
    m = re.fullmatch(r"(?:(\d+)w)?(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", spec)
    if not m:
        raise ValueError('Invalid duration. Try "10m", "1h30m", "2w", "45s", or a number (minutes).')
    w, d, h, mnt, s = (int(x) if x else 0 for x in m.groups())
    td = dt.timedelta(weeks=w, days=d, hours=h, minutes=mnt, seconds=s)
    if td.total_seconds() <= 0:
        raise ValueError("Duration must be positive.")
    return td


_REPEAT_UNIT_MAP = {
    "s": "seconds", "sec": "seconds", "secs": "seconds", "second": "seconds", "seconds": "seconds",
    "m": "minutes", "min": "minutes", "mins": "minutes", "minute": "minutes", "minutes": "minutes",
    "h": "hours", "hr": "hours", "hrs": "hours", "hour": "hours", "hours": "hours",
    "d": "days", "day": "days", "days": "days",
    "w": "weeks", "wk": "weeks", "wks": "weeks", "week": "weeks", "weeks": "weeks",
    "mo": "months", "mon": "months", "month": "months", "months": "months",
}


def _to_epoch_utc(local_dt: dt.datetime) -> int:
    # Treat naive as local time; convert to timestamp.
    if local_dt.tzinfo is None:
        local_dt = local_dt.astimezone()
    return int(local_dt.timestamp())


def _parse_repeat_every(spec: str) -> tuple[int, str]:
    """
    Parse '--every' repeat spec like: 10m, 2h, 3d, 2w, 1mo
    Returns (every:int, unit:str in {'seconds','minutes','hours','days','weeks','months'})
    """
    s = spec.strip().lower()
    m = re.fullmatch(r"(\d+)\s*([a-z]+)", s)
    if not m:
        raise ValueError('Invalid --every value. Try "15m", "2h", "3d", "2w", "1mo".')
    n = int(m.group(1))
    unit_key = m.group(2)
    unit = _REPEAT_UNIT_MAP.get(unit_key)
    if not unit:
        raise ValueError('Unknown repeat unit. Use s, m, h, d, w, or mo.')
    if n <= 0:
        raise ValueError("Repeat interval must be positive.")
    return n, unit


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="remnd", description="Simple reminder list (add, list, comp, del).")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("notify-due", help="Send desktop notifications for due reminders.")
    sub.add_parser("notify-catchup", help="Re-notify all due, uncompleted reminders (once per login).")
    sub.add_parser("notify-renotify", help="Re-notify all overdue, uncompleted reminders (once per hour).")
    sub.add_parser("install", help="Install and start the systemd user timer and login catch-up.")
    sub.add_parser("uninstall", help="Disable and remove the systemd user timer and login catch-up.")

    p_add = sub.add_parser("add", help="Add a reminder due after a duration.")
    p_add.add_argument("in_", help='Duration like "10m", "1h30m", or number (minutes).')
    p_add.add_argument("title", help="Reminder title.")
    p_add.add_argument("--note", "-n", help='Optional note (default "-").')
    p_add.add_argument("--every", "-e", help='Optional repeat interval like "2h", "3d", "1w".')

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

    repeat_every = None
    repeat_unit = None
    if args.every:
        repeat_every, repeat_unit = _parse_repeat_every(args.every)

    rid = add_reminder(
        title=args.title,
        note=args.note,
        due_at=_to_epoch_utc(due),
        repeat_every=repeat_every,
        repeat_unit=repeat_unit,
    )

    suffix = ""
    if repeat_every and repeat_unit:
        suffix = f"  (repeats every {repeat_every} {repeat_unit})"

    print(f"Added #{rid} @ {due.strftime('%Y-%m-%d %H:%M:%S')}  {args.title}{suffix}")
    return 0


def cmd_comp(args) -> int:
    before = get_reminder(args.id)
    if not before or before["completed_at"] is not None:
        print(f"No active reminder #{args.id} (maybe already done or wrong id)")
        return 1

    rolled = (before["repeat_every"] is not None and before["repeat_unit"] is not None)
    ok = mark_complete(args.id)
    if ok and rolled:
        after = get_reminder(args.id)
        next_local = dt.datetime.fromtimestamp(int(after["due_at"])).strftime("%Y-%m-%d %H:%M:%S")
        print(f"Completed occurrence of #{args.id}; next due @ {next_local}")
        return 0
    if ok:
        print(f"Marked #{args.id} as done")
        return 0
    print(f"No active reminder #{args.id} (maybe already done or wrong id)")
    return 1


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


def cmd_del(args) -> int:
    ok = delete_reminder(args.id)
    if ok:
        print(f"Deleted #{args.id}")
        return 0
    print(f"No reminder #{args.id}")
    return 1


def _send_notification(
    title: str,
    body: str,
    *,
    replace_key: str | None = None,
    icon: str | None = None,
    urgency: str = "normal",   # "low" | "normal" | "critical"
    expire_ms: int | None = None,
) -> None:
    """
    Pretty libnotify toast via notify-send with:
      - themed or file icon
      - urgency levels
      - multiline Pango markup body
      - per-ID replacement to collapse duplicates
    """
    if shutil.which("notify-send") is None:
        print(f"[NOTIFY:{urgency}] {title} — {body}")
        return

    cmd = ["notify-send", "--app-name=remnd", f"--urgency={urgency}"]

    if icon:
        cmd += ["--icon", icon]  # e.g. 'alarm', 'appointment-soon', or absolute path
    if expire_ms is not None:
        cmd += ["--expire-time", str(expire_ms)]
    if replace_key:
        # Collapse repeated notifications for the same reminder ID
        cmd += ["--hint", f"string:x-canonical-private-synchronous:{replace_key}"]

    # Helps some daemons theme/style it
    cmd += ["--category=reminder"]

    # Title should be plain; body may use small Pango markup.
    cmd += [title, body]
    subprocess.run(cmd, check=False)



def cmd_notify_due() -> int:
    rows = due_unnotified()
    now = dt.datetime.now().timestamp()

    for r in rows:
        due_ts = int(r["due_at"])
        overdue_s = int(now - due_ts)
        due_local = dt.datetime.fromtimestamp(due_ts).strftime("%a %d %b • %H:%M")

        title = f"{r['title'] or 'Reminder'}"
        note = (r["note"] or "").strip()

        body_lines = [f"{due_local}"]
        if note:
            body_lines.append(note)
        body_lines.append(f"<span size='small' alpha='70%'>ID #{r['id']}</span>")
        body = "\n".join(body_lines)

        urgency = "normal" if overdue_s < 48 * 3600 else "critical"

        _send_notification(
            title,
            body,
            icon="appointment-soon",   # or your PNG path
            replace_key=f"remnd-{r['id']}",
            urgency=urgency,
        )
        mark_notified(int(r["id"]))
    return 0


def cmd_notify_catchup() -> int:
    rows = due_active()

    for r in rows:
        due_local = dt.datetime.fromtimestamp(int(r["due_at"])).strftime("%a %d %b • %H:%M")
        title = f"{r['title'] or 'Reminder'}"
        note = (r["note"] or "").strip()

        body_lines = [f"{due_local}"]
        if note:
            body_lines.append(note)
        body_lines.append(f"<span size='small' alpha='70%'>ID #{r['id']}</span>")
        body = "\n".join(body_lines)

        # Fresh toast at login; keep it gentle and short-lived
        _send_notification(
            title,
            body,
            icon="appointment-soon",
            urgency="low",
            expire_ms=8000,
        )
    return 0


def cmd_notify_renotify() -> int:
    rows = due_renotify()
    now = dt.datetime.now().timestamp()

    for r in rows:
        due_ts = int(r["due_at"])
        overdue_s = int(now - due_ts)
        due_local = dt.datetime.fromtimestamp(due_ts).strftime("%a %d %b • %H:%M")

        title = f"{r['title'] or 'Reminder'}"
        note = (r["note"] or "").strip()

        body_lines = [f"{due_local}"]
        if note:
            body_lines.append(note)
        body_lines.append(f"<span size='small' alpha='70%'>ID #{r['id']}</span>")
        body = "\n".join(body_lines)

        urgency = "normal" if overdue_s < 48 * 3600 else "critical"

        _send_notification(
            title,
            body,
            replace_key=f"remnd-{r['id']}",
            icon="appointment-soon",   # or your PNG path
            urgency=urgency,
            expire_ms=15000,
        )
        mark_notified(int(r["id"]))
    return 0


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
    elif args.cmd == "notify-due":
        return cmd_notify_due()
    elif args.cmd == "notify-catchup":
        return cmd_notify_catchup()
    elif args.cmd == "notify-renotify":
        return cmd_notify_renotify()
    elif args.cmd == "install":
        return cmd_install()
    elif args.cmd == "uninstall":
        return cmd_uninstall()
    else:
        parser.error("unknown command")  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())

