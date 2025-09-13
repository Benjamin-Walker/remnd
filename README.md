<h1 align="center">remnd</h1>

A tiny Python CLI reminder app with desktop notifications.  
**Linux only** — uses **systemd (user)** timers and **notify-send** toasts.

---

## Features

- Add reminders due **in** a duration (`10m`, `1h30m`, `2d4h`, `2w`, …) or **at** a specific time:
  - `DD-MM-YYYY [HH:MM[:SS]]`, `DD-MM-YY`, `DD-MM` (defaults to 09:00)
  - `today HH:MM`, `tomorrow HH:MM`
  - `HH:MM[:SS]` (today, or tomorrow if already passed)
- Desktop toast notifications when reminders are due.
- Auto-repeat (`--every 15m|2h|3d|1w|1mo`).
- Mark reminders complete; repeating ones roll forward automatically.
- Background scheduling via **systemd user** units:
  - **Minute timer** — checks for newly due reminders.
  - **Re-notify** — runs hourly and re-notifies items last notified >24h ago.
  - **Login catch-up** — shows all currently overdue items shortly after login.
- Simple `sqlite3` backend at `~/.local/state/remnd/remnd.sqlite3`.

---

## Install

### Requirements
- Linux with **systemd** (user services)  
- `notify-send` (usually from `libnotify`):
  - Debian/Ubuntu: `sudo apt install libnotify-bin`
  - Fedora: `sudo dnf install libnotify`
  - Arch: `sudo pacman -S libnotify`

### With pipx (recommended)
```bash
pipx install remnd
remnd install
```

### With pip
```bash
pip install --user remnd
remnd install
```

### From source (poetry)
```bash 
poetry install
poetry run remnd install
```

## Quick Start
```bash
# Add a reminder in 10 minutes
remnd in 10m "Tea break"

# Add a reminder at a specific time
remnd at "today 18:00" "Call Alex"

# Specific date formats (DD-MM[-YY|-YYYY] [HH:MM[:SS]])
remnd at "25-12-2025 09:30" "Open presents"
remnd at "25-12 09:00" "Breakfast"        # current year, time defaults to 09:00
remnd at "21:00" "Evening stretch"        # today (or tomorrow if already passed)

# Add a note and make it repeat
remnd in 2h "Stand up" --every 2h -n "Move around"

# List active reminders
remnd list

# Include completed
remnd list --all

# Mark complete (ID from `list`)
remnd comp 3

# Delete a reminder (ID from `list`)
remnd del 2
```

## Background Notifications

`remnd install` sets up the necessary **systemd user** services and timers. To check their status:

```bash
systemctl --user status remnd-notify.timer
systemctl --user status remnd-catchup.timer
systemctl --user status remnd-renotify.timer
```

You can also manually force-run them:

```bash
remnd notify-due
remnd notify-catchup
remnd notify-renotify
```

They can be disabled with:

```bash
remnd uninstall
```

## Database Location

The SQLite database is located at `~/.local/state/remnd/remnd.sqlite3`.
Systemd files are at `~/.config/systemd/user/remnd-*`.


## LICENSE

MIT License. See [LICENSE](LICENSE) for details.

