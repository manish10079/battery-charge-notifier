# BatteryLimit

A small, cross-platform desktop utility that sits in your system tray and tells
you when to **unplug** or **plug in** your charger, so your battery spends less
time pinned at 100 % or flattened to 0 %.

BatteryLimit is a **notification tool only**. It reads battery status and shows a
popup. It never controls charging, never touches drivers or firmware, never needs
administrator rights and makes no network calls.

---

## What it does

- Watches the battery on a background thread and stays out of the way.
- Warns you when the battery reaches the **upper limit** while charging
  (*"Unplug the charger"*) and when it drops to the **lower limit** on battery
  power (*"Plug in the charger"*).
- Warns **once per crossing**, not once per poll. After a warning the channel
  stays quiet until the battery moves back past a re-arm point, which prevents
  nagging while still catching a genuine second crossing.
- Lets you snooze a warning for a configurable number of minutes.
- Lives in the tray with a live status line, a pause switch and a settings
  dialog. Everything applies immediately - there is no restart and no OK button.
- Optionally starts automatically when you sign in.

### Limits at a glance

| Setting         | Default | Meaning                                                           |
| --------------- | ------- | ----------------------------------------------------------------- |
| Upper limit     | 80 %    | Warn to unplug once the battery reaches this level while charging |
| Lower limit     | 20 %    | Warn to plug in once the battery falls to this level on battery   |
| Minimum gap     | 10 %    | Upper limit must stay at least this far above the lower limit     |
| Re-arm gap      | 5 %     | Hysteresis: how far the battery must move back before a channel can warn again |
| Snooze duration | 15 min  | How long the Snooze button suppresses the current warning         |
| Poll interval   | 60 s    | How often the battery is sampled, on a background thread          |
| Monitoring      | on      | Pause or resume all monitoring                                    |
| Launch at login | on      | Start automatically when you sign in                              |
| Notify via      | popup   | Popup window (mirrored to the tray) or a tray notification only   |

With the defaults, the upper channel warns at 80 % and only re-arms below 75 %;
the lower channel warns at 20 % and only re-arms above 25 %.

---

## Requirements

- Python 3.12 or newer
- PySide6 6.8+ and psutil 5.9+ (installed automatically as dependencies)
- A desktop session with a system tray. Without one the application still runs
  and shows popups, but the tray icon and its menu are unavailable.

## Install

```console
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS and Linux
pip install -e .
```

## Run

```console
python -m batterylimit
```

or, once installed, either of the console/graphical entry points:

```console
batterylimit
batterylimit-gui
```

### Command line options

| Option              | Effect                                                |
| ------------------- | ----------------------------------------------------- |
| `--version`         | Print the version and exit                            |
| `--show-settings`   | Open the settings dialog immediately after starting   |
| `--no-startup-sync` | Never create or update the launch-at-login entry      |
| `-v`, `--verbose`   | Enable debug logging                                  |

Only one instance runs at a time. Launching a second copy hands a
"show your settings" command to the running one and exits.

---

## Using it

**Tray menu**

| Item                | Effect                                                       |
| ------------------- | ------------------------------------------------------------ |
| *Status line*       | Live charge level and the action required right now, if any  |
| *Settings…*         | Open the settings dialog (also on a tray double-click)       |
| *Test warnings ▸*   | Preview the upper or lower warning                           |
| *Pause monitoring*  | Stop sampling without quitting                               |
| *Quit BatteryLimit* | Exit                                                         |

**Warning popup** - a frameless, always-on-top card showing the required action,
the charge level, a gauge marked with your limits, and three buttons: *Snooze*,
*Settings* and *Dismiss*. Press `Esc` to dismiss. The window is shown without
activating, so it will not pull focus away from a fullscreen application. A
second warning updates the same window rather than stacking a new one, and every
warning is mirrored to a tray notification so it is not missed if you are away.

---

## Where settings are stored

A single JSON file, written atomically:

| Platform | Location                                                     |
| -------- | ------------------------------------------------------------ |
| Windows  | `%APPDATA%\BatteryLimit\config.json`                         |
| macOS    | `~/Library/Application Support/BatteryLimit/config.json`      |
| Linux    | `$XDG_CONFIG_HOME/batterylimit/config.json` (or `~/.config/...`) |

The file is validated on load. A hand-edited or corrupt file is repaired rather
than fatal: unknown keys are ignored, out-of-range values are clamped, and a file
that cannot be repaired falls back to the defaults, so a bad config can never
stop the application from starting. Invalid edits made in the dialog are rejected
outright and explained inline, and the previous configuration is left untouched.

**Launch at login** is per-user and never needs administrator rights:

| Platform | Mechanism                                            |
| -------- | ---------------------------------------------------- |
| Windows  | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |
| macOS    | `~/Library/LaunchAgents/com.batterylimit.plist`      |
| Linux    | `$XDG_CONFIG_HOME/autostart/batterylimit.desktop`    |

`--no-startup-sync` leaves all of this alone.

---

## Development

### Layout

```
batterylimit/
    __main__.py          python -m batterylimit
    main.py              entry point, argument parsing, single-instance gate
    controller.py        dependency injection and signal wiring
    app_config.py        configuration schema, validation, atomic persistence
    battery_service.py   BatteryService protocol + psutil implementation
    monitor.py           warning state machine + threaded polling facade
    viewmodels/          presentation logic (status, warning, settings)
    widgets/             reusable presentation-only widgets
    warning_window.py    the popup (a pure View)
    settings_dialog.py   the schema-driven settings dialog (a pure View)
    tray.py              the system tray icon and menu (a pure View)
    notifier.py          warning dispatch to popup + tray notification
    startup.py           per-platform launch-at-login
    single_instance.py   QLocalServer-based single-instance gate
    colors.py            every colour token in the project
    resources.py         loading the bundled icons
    assets/              generated icons (package data)
packaging/
    batterylimit.spec    PyInstaller build definition
    launcher.py          frozen-build entry point
tools/
    generate_assets.py   regenerates the icons
tests/
```

### Architecture

The project follows MVVM with a service layer, and the dependencies only ever
point one way:

```
View  ──▶  ViewModel  ──▶  Service
(widgets)  (viewmodels)    (battery, config, startup)
```

- **Views** render what they are given and report user intent through Qt signals.
  They contain no business logic: no widget decides *whether* to warn, and none
  formats a message.
- **ViewModels** own all formatting and decisions, and are unit-testable without
  a window.
- **Services** are injected through `AppController`, so the whole application can
  be assembled against fakes. Nothing reaches for a global.

**Colour discipline:** every colour is a named token in `batterylimit/colors.py`.
`tests/test_design_tokens.py` fails the build if a colour literal appears
anywhere else, so the rule is enforced rather than merely documented.

### The warning state machine

Each of the two warning channels (upper and lower) is an independent three-state
machine:

```
ARMED ──condition met──▶ fired (QUIET)
  ▲                          │
  └──battery re-armed────────┘
                             │
                          SNOOZED ──snooze expires──▶ ARMED
```

The `QUIET` phase is what stops a warning from repeating on every poll, and the
re-arm test is what allows a genuine second crossing to be reported. The machine
is a plain object driven by explicit timestamps, so every scenario is tested
deterministically without sleeping (`tests/test_warning_state_machine.py`).

### Regenerating the icons

The icons are committed as package data. After changing the artwork or a colour
token, regenerate them:

```console
python tools/generate_assets.py
```

### Tests

```console
python -m pytest
```

Tests drive the real object graph with a stubbed battery service, a temporary
configuration file and a no-op autostart service, so the suite never touches your
battery, your config or your login items. `tests/test_app_smoke.py` boots the
complete application - monitor thread, tray, notifier - and checks the end-to-end
behaviour, including the "warn exactly once, then stay quiet" guarantee.

If your machine has no display, run headless with
`QT_QPA_PLATFORM=offscreen`.

### Building a single-file executable

```console
pip install -e ".[dev]"
pyinstaller packaging/batterylimit.spec
```

The result is `dist/BatteryLimit.exe` (`dist/BatteryLimit` on macOS and Linux):
one self-contained file, windowed rather than console, with the icons bundled
inside it.

`packaging/launcher.py` exists because PyInstaller runs its entry script as a
top-level module named `__main__`, which has no parent package. An entry point
inside the package would fail on its relative import - and the build would still
succeed, producing an executable that crashes on startup.
`tests/test_packaging.py` pins this down.

To watch the log output of a build, change `console=False` to `console=True` in
the spec before building.

### Adding a setting

Adding a setting never requires touching the dialog. Add a `FieldSpec` to
`FIELDS` in `batterylimit/app_config.py`; the schema drives validation, repair,
persistence and the generated controls.

---

## Scope

BatteryLimit deliberately does **not** control charging. It does not touch charge
thresholds, drivers, firmware, ACPI or vendor tools, and it never needs
administrator rights - it only reads the battery and tells you what to do. It
also makes no network requests and collects no telemetry: the only files it
writes are its own configuration and the optional autostart entry described
above.

## License

MIT.
