# Battery Charge Notifier — UI specification

A complete inventory of every screen, control and string in the application.
Extracted from the source, not designed: treat it as the *current* state, and as
the content contract any redesign must satisfy.

There are **four surfaces**. There is no main window — the app lives in the tray.

1. System tray icon (four states) with a tooltip
2. Tray context menu
3. Warning popup (frameless, bottom-right)
4. Settings dialog. Plus an OS tray balloon that mirrors every warning

---

## 0. Purpose and hard constraints

The app watches battery level and tells you when to plug in or unplug. It is a
**notifier only**. Any redesign must preserve these:

- It **never** controls charging, throttles power, or changes a driver or firmware
  setting. It only shows messages.
- It must run without administrator rights.
- It makes **no network connections**. The only socket is a local, per-user,
  same-machine channel used to detect a second launch.
- It must work on Windows, macOS and Linux from one codebase, so no
  platform-specific chrome (no native title bars, no Windows-only widgets).
- Battery is sampled on a background thread. The UI must never block.
- One instance only. A second launch hands off to the running one and exits.
- Colours may only come from the design tokens in §7. A test
  (`tests/test_design_tokens.py`) fails the build if a colour literal appears
  anywhere else.

---

## 1. System tray icon

The icon is the app's primary presence. It is a 16–24 px tray glyph with four
states, chosen automatically:

| State | Icon asset | Shown when |
|---|---|---|
| Healthy | `tray_ok.png` | Monitoring on, battery present, no action needed |
| Plug in | `tray_plug.png` | Battery at/below the lower limit while on battery power |
| Unplug | `tray_unplug.png` | Battery at/above the upper limit while plugged in |
| Paused | `tray_paused.png` | Monitoring disabled **or** no battery detected |

### Tooltip (hover)

Multi-line, up to 5 lines. Exact formats:

```
Battery Charge Notifier
52%  ·  Running on battery
About 1 h 9 min remaining
Limits: unplug at 80%, plug in at 20%
Polling every 60 s
```

Line 2 alternatives:
- `{percent}%  ·  Charger connected` (plugged in)
- `{percent}%  ·  Running on battery` (on battery)

Line 3 is `About {duration} to full` when plugged, `About {duration} remaining`
when not. It is **omitted entirely** when the estimate is unknown or ≤ 0.
Duration format: `1 h 32 min` (hours present) or `45 min` (under an hour, never
`0 min`).

Final line is `Polling every {n} s`, or `Monitoring paused` when disabled.

**No battery variant** — line 2 becomes `No battery detected on this machine.`
and line 3 is dropped:

```
Battery Charge Notifier
No battery detected on this machine.
Limits: unplug at 80%, plug in at 20%
Polling every 60 s
```

---

## 2. Tray context menu (right-click)

```
┌──────────────────────────────────────┐
│ Status  ·  52%  ·  unplug            │  ← disabled, read-only status line
├──────────────────────────────────────┤
│ Settings…                            │
│ Test warnings                      ▸ │
├──────────────────────────────────────┤
│ ✓ Pause monitoring                   │  ← checkable
├──────────────────────────────────────┤
│ Quit Battery Charge Notifier         │
└──────────────────────────────────────┘
```

### Status line

The first row is **disabled** (not clickable), acting as a header. Five variants:

| Condition | Text |
|---|---|
| Paused | `Status  ·  paused` |
| No battery | `Status  ·  no battery` |
| Action: unplug | `Status  ·  52%  ·  unplug` |
| Action: plug in | `Status  ·  52%  ·  plug in` |
| Normal | `Status  ·  52%` |

The separator is `  ·  ` — a middle dot (`U+00B7`) with two spaces either side.

### Items

| Item | Type | Behaviour |
|---|---|---|
| `Settings…` | action | Opens the settings dialog |
| `Test warnings` | submenu | Contains two preview triggers |
| ↳ `Upper warning (unplug)` | action | Shows the popup as if the battery hit the upper limit |
| ↳ `Lower warning (plug in)` | action | Shows the popup as if it hit the lower limit |
| `Pause monitoring` | **checkable** | Toggles monitoring; label flips, see below |
| `Quit Battery Charge Notifier` | action | Exits |

When paused, the toggle's label changes from `Pause monitoring` to
`Resume monitoring` and the tick stays checked. A later change from the settings
dialog must be reflected here immediately.

**Double-clicking the tray icon opens Settings** (no popup, no menu).

---

## 3. Warning popup

A frameless, always-on-top, translucent card shown **bottom-right of the active
screen**, 28 px from the screen edges. It must appear over a fullscreen app
**without stealing focus** — so `WA_ShowWithoutActivating` plus the `Tool` window
type. Clicking it focuses it, which is what makes `Esc` work.

Exactly **one instance exists**, reused in place. Repeated warnings update the
existing card; they never stack.

```
┌────────────────────────────────────────────┐
│  ┌────┐                                    │
│  │ ⚡ │  Unplug the charger                │  ← headline, accent colour, 19 pt bold
│  └────┘                                    │
│                                            │
│  83%                                       │  ← 46 px, weight 800
│                                            │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░ │  ← gauge, ticks at both limits
│                                            │
│  Battery at 83% — unplug the charger.      │  ← detail, 11 pt, secondary
│                                            │
│  [ Snooze 15 min ] [ Settings ]  [Dismiss] │
└────────────────────────────────────────────┘
```

### Layout metrics

| Property | Value |
|---|---|
| Width | min 420 px, max 520 px |
| Card margin (inner padding) | 26 px all sides |
| Card corner radius | 18 px |
| Card border | 1 px solid, **in the accent colour** |
| Card background | translucent scrim `rgba(14, 19, 23, 242)` — desktop shows faintly |
| Vertical spacing between blocks | 18 px |
| Header row spacing | 14 px |
| Button row spacing | 10 px |
| Distance from screen edge | 28 px |

### Contents, top to bottom

1. **Header row** — action icon (fixed 44×44, aspect-preserving, top-aligned)
   beside the headline.
2. **Percent readout** — e.g. `83%`. 46 px, weight 800, primary text colour.
3. **Battery gauge** — an 18 px tall rounded bar (9 px radius):
   - Track in `GAUGE_TRACK`
   - Fill in the **accent colour**, width proportional to charge
   - A minimum fill of one diameter so tiny values don't render as a sliver
   - **Vertical tick at the lower limit** (`GAUGE_TICK`) and at the **upper
     limit** (`GAUGE_TICK_MAJOR`), each overhanging the bar by 4 px top and bottom
   - Height 20 px + 8 px overhang; expands horizontally, fixed vertically
4. **Detail line** — one sentence, 11 pt, secondary text colour, wraps.
5. **Button row** — `Snooze {n} min`, `Settings`, then a stretch, then `Dismiss`.

### Buttons

| Label | Role | Appearance |
|---|---|---|
| `Snooze 15 min` | ACCENT | Filled with the warning's accent colour, dark text |
| `Settings` | NEUTRAL | Filled with `BUTTON_BACKGROUND` |
| `Dismiss` | OUTLINE | Transparent with a 1 px `OUTLINE_STRONG` border |

All buttons: min-height 38 px, min-width 96 px, radius 10 px, 10.5 pt semibold,
pointing-hand cursor. The Snooze label is dynamic — `Snooze {snooze_minutes} min`.

### Exact strings

| Element | Upper warning | Lower warning |
|---|---|---|
| Headline | `Unplug the charger` | `Plug in the charger` |
| Detail | `Battery at {pct}% — unplug the charger.` | `Battery at {pct}% — plug in the charger.` |
| Accent | amber `#F4B04A` | coral `#FF6B6B` |

The dash in the detail line is an em dash (`U+2014`).

### Behaviour

- `Esc` dismisses.
- `Snooze` hides the popup and suppresses the current warning for the snooze
  duration.
- `Settings` opens the settings dialog.
- `Dismiss` hides it. Dismissal does **not** silence the warning permanently — it
  can fire again on a later crossing.

---

## 4. Settings dialog

Modeless, live-applying. **There is no OK or Cancel** — a valid edit is saved and
takes effect across the running app immediately. Minimum width 470 px.

```
┌────────────────────────────────────────────────────────┐
│ Battery Charge Notifier settings                       │  ← 16 pt bold
│ Changes are saved and applied immediately — there is   │  ← 10 pt secondary
│ nothing to confirm.                                    │
│                                                        │
│ Upper limit                                            │  ← 10.5 pt semibold
│ [ 80                                          % ]      │
│ Warn to unplug the charger once the battery reaches    │  ← 9.5 pt help
│ this level.                                            │
│                                                        │
│  … seven more fields …                                 │
│                                                        │
│ ────────────────────────────────────────────────────── │  ← 1 px separator
│ [ Restore defaults ]                      [ Close ]    │
└────────────────────────────────────────────────────────┘
```

### Field anatomy

Every field is generated from a schema, so all nine share one structure:
**label** → **control** → **help text** → (hidden) **error slot**.
Adding a setting requires no dialog code change.

### The nine fields, in order

| # | Label | Control | Range / options | Default | Suffix | Help text |
|---|---|---|---|---|---|---|
| 1 | `Upper limit` | spinbox | 1–100 | 80 | `%` | Warn to unplug the charger once the battery reaches this level. |
| 2 | `Lower limit` | spinbox | 1–100 | 20 | `%` | Warn to plug the charger in once the battery falls to this level. |
| 3 | `Minimum gap` | spinbox | 1–99 | 10 | `%` | The upper limit must stay at least this far above the lower limit. |
| 4 | `Re-arm gap` | spinbox | 1–50 | 5 | `%` | Hysteresis. After a warning fires it stays quiet until the battery moves back this far, which prevents nagging. |
| 5 | `Snooze duration` | spinbox | 1–240 | 15 | ` min` | How long the Snooze button suppresses the current warning. |
| 6 | `Poll interval` | spinbox | 5–3600 | 60 | ` s` | How often the battery is sampled, on a background thread. |
| 7 | `Monitoring enabled` | checkbox | — | on | — | Pause or resume all battery monitoring. |
| 8 | `Launch at login` | checkbox | — | on | — | Start Battery Charge Notifier automatically when you sign in. |
| 9 | `Notify via` | dropdown | see below | `popup` | — | Show an always-on-top popup window, or only a system tray notification. Popups are always mirrored to the tray. |

Notes on controls:
- **Spinboxes** are right-aligned, step 1, with custom up/down arrow images and
  the unit suffix rendered *inside* the field (`80 %`, `15 min`, `60 s`).
- **Checkboxes** are always labelled `Enabled`, never with the field name — the
  field label above already names it. Indicator is 17×17, 5 px radius.
- **Dropdown option labels** are friendlier than the stored values:
  - `popup` → `Popup window (mirrored to the tray)`
  - `tray` → `Tray notification only`

### Footer

| Button | Role | Action |
|---|---|---|
| `Restore defaults` | OUTLINE | Resets all nine fields to the defaults above and saves |
| `Close` | PRIMARY | Closes the dialog (edits are already saved) |

`Restore defaults` sits left, `Close` right, separated by a stretch.

### Inline validation

An edit is validated immediately. A rejected value shows a message **under that
field** in `FIELD_ERROR` (9.5 pt, semibold) and is not saved. Exact messages:

| Trigger | Message |
|---|---|
| Non-integer | `{Label} must be a whole number.` |
| Below minimum | `{Label} must be at least {min}{suffix}.` |
| Above maximum | `{Label} must be at most {max}{suffix}.` |
| Bad dropdown value | `{Label} must be one of: popup, tray.` |
| Bad checkbox value | `{Label} must be yes or no.` |
| Upper ≤ lower | `The upper limit ({u}%) must be greater than the lower limit ({l}%).` |
| Gap too small | `The upper limit must be at least {gap}% above the lower limit (currently {diff}%).` |

Cross-field rules are skipped when either field already failed on its own, so the
user never sees a cascade of derived complaints from one edit.

---

## 5. Tray balloon (OS notification)

Every warning is **also** mirrored to a native tray balloon, even in popup mode,
so it isn't missed if the popup was dismissed or the user is away. It reuses the
popup's headline and detail strings.

| Property | Value |
|---|---|
| Title | the headline (`Unplug the charger` / `Plug in the charger`) |
| Body | the detail sentence |
| Icon | `Critical` for the lower/plug-in warning, `Information` for upper/unplug |
| Timeout | 12 seconds |

In `tray` notification mode the balloon is the only thing shown.

---

## 6. Colour and type tokens

Dark, Material-3-flavoured. All values live in `battery_charge_notifier/colors.py`.

### Surfaces (lowest → highest elevation)

| Token | Value |
|---|---|
| `SURFACE` | `#0E1317` |
| `SURFACE_CONTAINER_LOW` | `#141B21` |
| `SURFACE_CONTAINER` | `#1A232A` |
| `SURFACE_CONTAINER_HIGH` | `#222D36` |
| `SURFACE_OVERLAY` | `#2A3742` |
| `SCRIM` | `rgba(14, 19, 23, 242)` |
| `SCRIM_SOFT` | `rgba(20, 27, 33, 224)` |

### Lines and text

| Token | Value |
|---|---|
| `OUTLINE` | `#2E3A44` |
| `OUTLINE_STRONG` | `#3C4B57` |
| `TEXT_PRIMARY` | `#E9EFF4` |
| `TEXT_SECONDARY` | `#9DAEBB` |
| `TEXT_MUTED` | `#6C7C89` |
| `TEXT_ON_ACCENT` | `#0B1116` |

### Semantic accents

| Token | Value | Meaning |
|---|---|---|
| `ACCENT_UNPLUG` | `#F4B04A` | amber — battery high, **stop** charging |
| `ACCENT_UNPLUG_DIM` | `#8A6528` | |
| `ACCENT_PLUG` | `#FF6B6B` | coral — battery low, **start** charging |
| `ACCENT_PLUG_DIM` | `#8C3A3A` | |
| `ACCENT_PRIMARY` | `#5AA9E6` | neutral/informational, primary buttons |
| `ACCENT_PRIMARY_DIM` | `#356487` | |
| `ACCENT_OK` | `#4FD1A5` | healthy tray state |

### Components

| Token | Value |
|---|---|
| `GAUGE_TRACK` | `#202B34` |
| `GAUGE_TICK` | `#3A4854` |
| `GAUGE_TICK_MAJOR` | `#5B6D7C` |
| `BUTTON_BACKGROUND` | `#212C35` |
| `BUTTON_BACKGROUND_HOVER` | `#2C3A45` |
| `BUTTON_BACKGROUND_PRESSED` | `#18212A` |
| `BUTTON_TEXT` | `#DCE6ED` |
| `INPUT_BACKGROUND` | `#141B21` |
| `INPUT_BORDER` | `#33414C` |
| `INPUT_BORDER_FOCUS` | `#5AA9E6` |
| `INPUT_INVALID_BORDER` | `#FF6B6B` |
| `FIELD_LABEL` | `#C3D0DA` |
| `FIELD_HELP` | `#7E8E9B` |
| `FIELD_ERROR` | `#FF8A8A` |

### Type scale

| Element | Size | Weight |
|---|---|---|
| Popup headline | 19 pt | 700 |
| Popup percent | 46 px | 800 |
| Popup detail | 11 pt | normal |
| Dialog title | 16 pt | 700 |
| Dialog subtitle | 10 pt | normal |
| Field label | 10.5 pt | 600 |
| Field help / error | 9.5 pt | help normal, error 600 |
| Buttons | 10.5 pt | 600 |
| Inputs | 10.5 pt | normal |

---

## 7. Icon assets

Generated by `tools/generate_assets.py`; regenerating them is the supported way
to change the artwork.

| File | Use | Size |
|---|---|---|
| `app.ico` | Window icon, executable icon | multi-resolution |
| `app.png` | Source artwork | — |
| `tray_ok.png` | Healthy tray state | tray size |
| `tray_plug.png` | Plug-in tray state | tray size |
| `tray_unplug.png` | Unplug tray state | tray size |
| `tray_paused.png` | Paused / no battery | tray size |
| `arrow_up.png` / `arrow_down.png` | Spinbox and dropdown arrows | rendered at 9×6 px |

The action icon inside the popup is `tray_plug` / `tray_unplug` matching the
warning, rendered at 44×44.

---

## 8. Accessibility requirements for any redesign

These are behaviours the current build satisfies and a redesign must not lose:

- The popup **must not steal focus**. It appears while you are working in another
  application; activating it would interrupt typing.
- `Esc` must dismiss the popup, and the popup must be focusable by clicking it.
- Every control must keep a visible text label — no icon-only buttons anywhere.
- Inline errors must be text, not colour alone: the message is always shown, and
  `INPUT_INVALID_BORDER` only reinforces it.
- No information may be conveyed by colour alone. The tray icon *shape* differs
  per state, and the tooltip always states the level in text.
- All user-facing text lives in the four surfaces above; there are no
  abbreviations a screen reader would mispronounce.
