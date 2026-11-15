# ISA-101 Dashboard

Tools for an ISA-101 style alarm and overview dashboard in Home Assistant: grey when normal, colour only for abnormal, alarms ranked by priority, and every alarm kept until an operator acknowledges it.

The dashboard itself is built with [button-card](https://github.com/custom-cards/button-card) templates. Its alarm rules live in one place, the `isa_l1_data` template's variables (`l1` point groups, `hosts`, `metrics`, `windows`), and every card (alarm list, alert box, annunciator, group cards) evaluates those same rules.

## Templates
`templates/` holds the ten button-card templates, exported from the dashboard's raw config. Paste them under `button_card_templates:` in your dashboard's raw configuration editor.

| Template | Card |
|---|---|
| `isa_alert_box` | Top alarm band: highest-priority active alarms |
| `isa_annunciator` | Annunciator panel of fixed windows (`windows`) |
| `isa_alarm_list` | Full alarm list: active, suppressed, scheduled |
| `isa_alarm_summary` | Alarm counts by priority |
| `isa_group` | One point group from `l1` (Power, Site, ...) |
| `isa_metric` | Analogue value with limits and a sparkline |
| `isa_host_row` | One host from `hosts` |
| `isa_svc_group` | A short list of services |
| `isa_facts` | Host facts: boot time, heartbeat, last update check |
| `isa_control` | Plain grey control button |

The rules go in one more template, `isa_l1_data`, which is yours to write: see `examples/isa_l1_data.example.yaml` for the format. Give every card both templates, so they all read the same rules:

```yaml
type: custom:button-card
template: [isa_alarm_list, isa_l1_data]
triggers_update: [ ...every entity the rules use... ]
```

`export.py` re-exports the templates from `live.json` (fetched by `build.sh`); it never exports `isa_l1_data`.

## Trend charts

ISA-101 keeps line trends, with rules: a fixed Y axis set to the real operating range, grey pens, colour only on the warning and alarm limit lines, a shaded normal band, and no more than four pens per chart. `examples/trend_charts.example.yaml` has three [apexcharts-card](https://github.com/RomRider/apexcharts-card) charts drawn that way:

| Chart | Shows |
|---|---|
| Analogue value | A fixed range with the normal band and labelled warning and alarm lines |
| Mirrored throughput | Receive below zero, transmit above, on one symmetric axis (a radio or a switch port) |
| Asymmetric WAN | Transmit 0-120 in the top half and receive 0-1200 in the bottom half of one axis; the labels and tooltip undo the scaling |

Throughput points are 5-minute peaks, so short bursts still show on a 24-hour chart. The charts use [card-mod](https://github.com/thomasloven/lovelace-card-mod) for the grey card face and a dark title: without it, a dark theme draws chart titles in a light grey.

## Alarm latch

A dashboard can only show what is wrong *now*. A fault that clears on its own, like a service that dies and restarts at 3 a.m., would vanish before anyone saw it. The latch fixes that: a trigger-based template sensor, `sensor.isa_unacknowledged_alarms`, records each point the moment it goes from normal to abnormal and keeps it until it is acknowledged.

The latch is generated from the dashboard's rules, so the two can't drift apart. Rebuild it whenever the rules change.

### Files
- `gen.py`: the generator. Reads `live.json` (the dashboard config) and writes `template_isa_alarm_latch.yaml`.
- `build.sh`: fetches the dashboard config over SSH, runs `gen.py`, diffs the result against the installed file, and installs it on request.
- `export.py`: writes `templates/` from `live.json`.
- `latch.env.example`: connection settings. Copy it to `latch.env` (ignored by git) and fill it in.

### Use
```
cp latch.env.example latch.env   # then edit it
./build.sh                       # dry run: shows the diff, changes nothing
./build.sh install               # backs up the installed file (.bak-<date>) and installs the new one
```
After `install`, check the configuration and reload **Template entities** in Home Assistant (Developer Tools > YAML).

Requires SSH to the Home Assistant host (for example the Advanced SSH & Web Terminal app) with passwordless `sudo -n`, and a storage-mode dashboard.

### What the generator does
- One trigger per monitored point, firing only on the move from normal to abnormal, so a point already in alarm isn't recorded twice.
- Host services wait 1 minute (`SERVICE_DELAY_MIN`) and camera ingest 2 minutes (`INGEST_DELAY_MIN`), so a planned stop of a few seconds, such as a nightly backup, doesn't latch. Metrics use their own `on_delay`.
- Rule types: plain state, `above`, `below`, `has`/`lacks` (status words such as a UPS's `OL`), and `resolves` (a DNS lookup that goes unavailable). `stale_min` and `same_as` are not state changes and aren't latched.
- Points with an `off_window` (a device that is off on a schedule) are skipped.
- Acknowledge by firing the event `isa_alarm_ack` with `key` set to a point id, or `all`.
- The newest 50 entries are kept.

## Licence
MIT
