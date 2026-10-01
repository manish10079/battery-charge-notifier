# Design brief: Battery Charge Notifier — modern Windows 11 UI

Copy everything below the line into your design agent.

---

## Your role

You are a senior product designer specialising in Windows 11 Fluent design. You
are redesigning the interface of a small, finished desktop utility. You produce a
**design specification document** — not code, not mockups in prose. Another
engineer will implement your spec in PySide6 (Qt Widgets) afterwards, so every
value you specify must be one Qt can actually express.

## The product

**Battery Charge Notifier** is a system tray utility that watches the battery and
tells you to plug in or unplug your charger, so the battery spends its life
between two configured thresholds instead of pinned at 100%.

What matters about it as a design problem:

- **It has no main window.** It lives in the tray. The entire interface is one
  tray icon, one context menu, a transient popup, and a settings dialog.
- **It is a notifier, not a controller.** It never changes charging behaviour,
  never touches drivers, never needs admin rights, never uses the network.
- **It interrupts.** The popup appears while you are working in another
  application, often a fullscreen one. Every second it is on screen it is
  competing with whatever the user is actually doing.
- **It is mundane and repetitive.** The same two messages, dozens of times a
  week, for years. It must not become irritating. Restraint is the whole design.

## The reference document

If you have repository access, **read `UI_SPEC.md` in the project root first**. It
is an exhaustive, code-derived inventory: every string, every control, every
layout constant, the full colour token set. It is the contract for *content*.
This brief is the contract for *form*. Where they disagree about anything the user
reads, `UI_SPEC.md` wins.

The essential content is reproduced below so you can work without it.

## The design brief

Redesign the four surfaces in **modern Windows 11 Fluent style, minimal**. The
goal is an interface that looks like it shipped with the operating system —
quiet, confident, unornamented — rather than a skinned cross-platform widget
toolkit.

**Target both light and dark themes, following the Windows system setting.**
Light is the primary case, since it is Windows 11's default. Your output must
provide two complete token sets, not one theme with inverted colours: Fluent dark
is not the light palette flipped, it is a different set of layer alphas over a
dark base.

Interpret "minimal" as *reduce*, not *decorate*. Specifically:

- Remove the ornament the current build carries: the 18px card radius, the
  accent-coloured border around the popup, the 46px percent numeral, the
  three-button row where two would do.
- Prefer hierarchy over borders and fills. Separate with space and weight before
  reaching for a line or a background.
- The popup gets roughly two seconds of attention. Design it to be read, not
  studied.

Do not interpret "minimal" as *plain*. Fluent minimalism is precise: exact type
ramp, exact 4px baseline grid, exact focus rectangles. Sloppiness is more visible
in a restrained design, not less.

## What you must not change

These are product decisions already made. Treat them as fixed requirements.

1. **Every user-facing string stays exactly as written.** You may change how
   words are set — size, weight, colour, position, case treatment — but not the
   words themselves. Several are asserted by the test suite. The full list is in
   the appendix; the strings that most constrain the design are the status line
   (`Status  ·  52%  ·  unplug`), the popup headline (`Unplug the charger`) and
   the dialog subtitle (`Changes are saved and applied immediately — there is
   nothing to confirm.`).

2. **The popup must not steal focus.** It appears while the user is typing in
   another application. Activating it would interrupt them. This is achieved
   today with `WA_ShowWithoutActivating` and the `Tool` window type, which means
   the window is *shown but not activated* — `Esc` only works after the user
   clicks it. Keep that behaviour and design the popup so a non-focused window
   still reads as intentional rather than broken.

3. **No information by colour alone.** Amber means "stop charging", coral means
   "start charging". Colour-blind users must still tell the two apart: the tray
   icon differs in *shape* per state, and every surface states the level in words.
   Preserve a non-colour channel for every distinction you introduce.

4. **The settings dialog has no OK or Cancel.** Every valid edit saves and applies
   to the running application immediately. Do not add a confirmation step, an
   Apply button, or a dirty-state indicator. Design for the moment of edit, not
   the moment of submission.

5. **The popup is a single reused instance.** A new warning updates the card in
   place; warnings never stack. Your spec should describe a layout that can change
   content without changing size dramatically — reserve room, do not jump.

6. **Every control keeps a visible text label.** No icon-only buttons anywhere.

7. **`Restore defaults` discards silently.** It is immediate and destructive of
   the user's configuration, with no confirmation today. You may propose a
   lightweight inline confirmation (an undo affordance rather than a modal), but
   do not add a blocking dialog.

## Platform facts to design within

These are properties of the platform and toolkit. Design *with* them, and flag
anything you want that they prevent.

- **The tray context menu is styleable.** Qt draws it itself, so your spec can
  govern its typography, spacing, hover states and separators.
- **The tray balloon notification is not.** It is a native OS notification. You
  control only its title, body, icon severity and timeout. Do not specify its
  appearance.
- **Mica and Acrylic cannot be applied to Qt Widgets windows** without
  platform-specific native calls. You may propose an approximation — layered
  opaque neutrals that read as Mica's tonal depth — but say clearly that it is an
  approximation, and specify the fallback for when the effect is unavailable.
- **Qt stylesheets do not support box-shadow or transitions.** Elevation must be
  expressed as a border plus a background layer step, and hover/press feedback as
  colour changes, not animation. Do not specify motion curves you cannot have.
- The app must keep building on Windows, macOS and Linux from one codebase. Your
  spec should degrade sensibly off Windows rather than assuming Fluent exists.

## What to produce

A single design specification document with these sections, in this order.

### 1. Design principles
Three to five sentences. The rules you will apply when a choice is ambiguous.
Specific to this product — not generic design advice.

### 2. Token architecture
Two complete token sets: **light** and **dark**. For each, specify every token
this interface needs, as a table of `role → value`.

Architect it the way Fluent does — semantic roles, not raw colours:

- Layer fills (base, card, control, alt, subtle) — the tonal steps that replace
  borders
- Text fills (primary, secondary, tertiary, disabled, on-accent)
- Strokes (card, control, divider, focus)
- Accent (default, hover, pressed, disabled, on-accent)
- Status accents: **plug-in** and **unplug**, each with default/hover/pressed and
  a soft wash for the gauge fill

Note explicitly which tokens differ between themes and which are constant. For
each status accent, justify your chosen hue against the Fluent palette and state
its contrast ratio against the surface it appears on — the previous amber and
coral were chosen to be distinguishable from each other at a glance, and that
property must survive the change.

### 3. Type ramp
Map every text element in the interface onto a Fluent/Windows 11 type ramp —
Segoe UI Variable, with the Display/Text/Small optical-size split if you use it.
Give a table of `element → size, weight, line height, optical size`, and name the
fallback for macOS and Linux.

### 4. Component specifications
One block per reusable component. For each, give **anatomy** (the named parts),
**metrics** (sizes, padding, gaps, radius, minimum targets), and **every state**:
default, hover, pressed, keyboard-focus, disabled, and invalid where it applies.

Components to specify at minimum:

- Push button — and the three visual weights the app needs (primary/accent,
  neutral, outline). State the rule for which weight to use where.
- Text input / spin control, including the unit suffix rendered inside the field
  (`80 %`, `15 min`, `60 s`) and its numeric alignment.
- Checkbox.
- Select / dropdown, including its open list.
- Inline field help and inline validation error.
- The battery gauge (see §5 — it needs its own reasoning).
- The focus rectangle. Specify it once, precisely, and reference it everywhere:
  Fluent draws it as a two-tone rounded rectangle offset outside the control, not
  a border swap.

### 5. The battery gauge
This widget deserves dedicated attention because it carries real information and
is the one piece of original visual design in the product.

It is an 18px horizontal bar showing current charge, with vertical tick markers at
the two configured thresholds. It appears only in the warning popup. Answer:

- How do you show charge level, and both thresholds, without three competing
  signals? The thresholds are the actionable information; the level is context.
- What happens visually when the level sits *beyond* a threshold — the state that
  triggered the popup in the first place?
- How does it read when the two thresholds are close together (a 25% gap is
  common; 10% is legal) versus far apart?
- Should it survive at all, or is there a better minimal form for "you are past
  the line you set"? If you think it should be removed or replaced, argue the
  case and propose the alternative.

### 6. Surface specifications
One subsection per surface, describing the composed result. Reference components
by name rather than re-specifying them. Cover layout, spacing on the 4px grid,
responsive behaviour (the popup is 420–520px wide and its text wraps), and
position.

The four surfaces, plus one:

1. **Tray icon and tooltip** — four states (healthy, plug-in, unplug, paused).
   Consider: at 16px on a dark taskbar, in a row with dozens of other icons, what
   actually remains legible? Describe the glyph logic per state. The tooltip is
   up to five lines of plain text.
2. **Tray context menu** — eleven items across three groups, including a
   checkable pause toggle whose label flips between two strings, and a two-item
   submenu. Mind the maximum practical menu width.
3. **Warning popup** — the centrepiece. Frameless, always-on-top, bottom-right,
   not focused. Reused in place. Two content variants. Three actions.
4. **Settings dialog** — nine schema-generated fields, modeless, live-applying,
   no OK/Cancel. Its width is driven by the longest help sentence; check that your
   typography does not force it wider than ~470px.
5. **Tray balloon** — title, body and severity mapping only.

### 7. Implementation notes and risks
For each item you specified, note anything that will be difficult or impossible
in Qt Widgets, and what you propose instead. Be explicit about what is an
approximation. This section is how the engineer avoids discovering the problem
after the work is done.

### 8. Open questions
Anything you could not decide with the information given. Ask, rather than
guessing silently.

## Before you finish, check yourself

- Did you change any user-facing string? You must not have. Verify against the
  appendix.
- Does the popup still work when it is shown but not focused? Would it look
  broken? Would the user know what to do?
- Can a colour-blind user still tell "plug in" from "unplug" on the tray icon and
  in the tooltip?
- Did you specify the focus state for *every* interactive element, or did you
  assume mouse use?
- Did you give a value for every state of every component you named, or did you
  leave the pressed and disabled states implied?
- Did you specify anything Qt cannot do without saying so?
- Is the settings dialog still under ~470px wide with the longest help sentence
  set in your proposed typography?
- Did you keep the popup's size stable across both content variants?

---

## Appendix: content inventory

All strings below are final and must not be reworded.

### Tray icon states

| State | Shown when |
|---|---|
| Healthy | Monitoring on, battery present, no action needed |
| Plug in | At or below the lower limit, on battery power |
| Unplug | At or above the upper limit, plugged in |
| Paused | Monitoring off, or no battery detected |

### Tooltip — up to five lines, all variants

```
Battery Charge Notifier
52%  ·  Running on battery
About 1 h 9 min remaining
Limits: unplug at 80%, plug in at 20%
Polling every 60 s
```

- Line 2: `{percent}%  ·  Charger connected` or `{percent}%  ·  Running on battery`
  or, with no battery, `No battery detected on this machine.`
- Line 3: `About {duration} to full` (plugged) / `About {duration} remaining`
  (unplugged); **omitted entirely** when unknown. Durations read `1 h 32 min` or
  `45 min`.
- Line 5: `Polling every {n} s`, or `Monitoring paused`.
- The separator is a middle dot, `U+00B7`, with two spaces either side.

### Tray context menu

| Item | Type |
|---|---|
| `Status  ·  paused` / `Status  ·  no battery` / `Status  ·  52%` / `Status  ·  52%  ·  unplug` / `Status  ·  52%  ·  plug in` | disabled header |
| `Settings…` | action |
| `Test warnings` | submenu |
| ↳ `Upper warning (unplug)` | action |
| ↳ `Lower warning (plug in)` | action |
| `Pause monitoring` / `Resume monitoring` | checkable |
| `Quit Battery Charge Notifier` | action |

Double-clicking the tray icon opens settings.

### Warning popup

| Element | Upper warning | Lower warning |
|---|---|---|
| Headline | `Unplug the charger` | `Plug in the charger` |
| Detail | `Battery at {pct}% — unplug the charger.` | `Battery at {pct}% — plug in the charger.` |
| Accent | amber (stop charging) | coral (start charging) |

Buttons: `Snooze {n} min` (n is user-configured, default `Snooze 15 min`),
`Settings`, `Dismiss`. The dash in the detail line is an em dash, `U+2014`.

Current metrics, for reference — you are expected to revise these: 420–520px wide,
26px inner padding, 18px card radius, 1px accent-coloured border, 44×44 icon,
percent numeral at 46px/800, gauge 18px tall, 28px from the screen edge.

### Settings dialog

Title `Battery Charge Notifier settings`. Subtitle
`Changes are saved and applied immediately — there is nothing to confirm.`
Footer buttons `Restore defaults` and `Close`.

| # | Label | Control | Range / options | Default | Unit | Help text |
|---|---|---|---|---|---|---|
| 1 | `Upper limit` | spinbox | 1–100 | 80 | `%` | Warn to unplug the charger once the battery reaches this level. |
| 2 | `Lower limit` | spinbox | 1–100 | 20 | `%` | Warn to plug the charger in once the battery falls to this level. |
| 3 | `Minimum gap` | spinbox | 1–99 | 10 | `%` | The upper limit must stay at least this far above the lower limit. |
| 4 | `Re-arm gap` | spinbox | 1–50 | 5 | `%` | Hysteresis. After a warning fires it stays quiet until the battery moves back this far, which prevents nagging. |
| 5 | `Snooze duration` | spinbox | 1–240 | 15 | ` min` | How long the Snooze button suppresses the current warning. |
| 6 | `Poll interval` | spinbox | 5–3600 | 60 | ` s` | How often the battery is sampled, on a background thread. |
| 7 | `Monitoring enabled` | checkbox | — | on | — | Pause or resume all battery monitoring. |
| 8 | `Launch at login` | checkbox | — | on | — | Start Battery Charge Notifier automatically when you sign in. |
| 9 | `Notify via` | dropdown | `popup` / `tray` | `popup` | — | Show an always-on-top popup window, or only a system tray notification. Popups are always mirrored to the tray. |

Two wrinkles that affect your design:

- Checkboxes are labelled `Enabled`, **not** with the field name — the label above
  already names the setting. So the control text carries no information on its own.
- The dropdown's two options read `Popup window (mirrored to the tray)` and
  `Tray notification only`, which are much longer than the stored values. Plan for
  a wide select.

### Validation messages (inline, under the offending field)

| Trigger | Message |
|---|---|
| Non-integer | `{Label} must be a whole number.` |
| Below minimum | `{Label} must be at least {min}{unit}.` |
| Above maximum | `{Label} must be at most {max}{unit}.` |
| Bad dropdown value | `{Label} must be one of: popup, tray.` |
| Bad checkbox value | `{Label} must be yes or no.` |
| Upper ≤ lower | `The upper limit ({u}%) must be greater than the lower limit ({l}%).` |
| Gap too small | `The upper limit must be at least {gap}% above the lower limit (currently {diff}%).` |

The longest of these is the last one. Your error treatment must hold
`The upper limit must be at least 10% above the lower limit (currently 5%).`
in the available width without truncation.

### Current colour tokens

For orientation only — you are replacing these. The build is dark-only today;
light is the new primary theme.

| Role | Current value |
|---|---|
| Surface (base) | `#0E1317` |
| Surface container (low / base / high) | `#141B21` / `#1A232A` / `#222D36` |
| Popup scrim | `rgba(14, 19, 23, 242)` |
| Outline / strong | `#2E3A44` / `#3C4B57` |
| Text primary / secondary / muted | `#E9EFF4` / `#9DAEBB` / `#6C7C89` |
| Text on accent | `#0B1116` |
| Accent unplug (amber) | `#F4B04A` |
| Accent plug-in (coral) | `#FF6B6B` |
| Accent primary (blue) | `#5AA9E6` |
| Accent healthy (green) | `#4FD1A5` |
| Gauge track / tick / major tick | `#202B34` / `#3A4854` / `#5B6D7C` |
| Field label / help / error | `#C3D0DA` / `#7E8E9B` / `#FF8A8A` |

### Type scale in use today

Popup headline 19pt/700 · popup percent 46px/800 · popup detail 11pt · dialog title
16pt/700 · dialog subtitle 10pt · field label 10.5pt/600 · field help and error
9.5pt (error 600) · buttons 10.5pt/600 · inputs 10.5pt.
