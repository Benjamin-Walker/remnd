# remnd

A tiny python CLI reminder app with desktop notifications.  
Built for Linux with `systemd` + `notify-send`.

---

## Features

- Add reminders due after a duration (`10m`, `1h30m`, `2d`, …) or at a specific time (`14:30`, `2024-12-31 23:59`, …).
- Desktop toast notifications when reminders are due.
- Auto-repeat reminders (every X minutes/hours/days/weeks/months).
- Mark reminders complete; repeating ones roll forward automatically.
- Background timers via `systemd`:
  - **Minute timer** → checks for newly due reminders.
  - **Daily re-notify** → reminds again every 24h until done.
  - **Login catch-up** → shows all overdue reminders at login.
- Simple `sqlite3` backend stored under `~/.local/state/remnd/`.

