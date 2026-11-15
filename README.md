# ISA-101 Dashboard

Tools for an ISA-101 style alarm and overview dashboard in Home Assistant: grey when normal, colour only for abnormal, alarms ranked by priority, and every alarm kept until an operator acknowledges it.

The dashboard itself is built with [button-card](https://github.com/custom-cards/button-card) templates. Its alarm rules live in one place, the `isa_l1_data` template's variables (`l1` point groups, `hosts`, `metrics`, `windows`), and every card (alarm list, alert box, annunciator, group cards) evaluates those same rules.

## Alarm latch

A dashboard can only show what is wrong *now*. A fault that clears on its own, like a service that dies and restarts at 3 a.m., would vanish before anyone saw it. The latch fixes that: a trigger-based template sensor, `sensor.isa_unacknowledged_alarms`, records each point the moment it goes from normal to abnormal and keeps it until it is acknowledged.

The latch is generated from the dashboard's rules, so the two can't drift apart. Rebuild it whenever the rules change.

### Files
- `gen.py`: the generator. Reads `live.json` (the dashboard config) and writes `template_isa_alarm_latch.yaml`.
- `build.sh`: fetches the dashboard config over SSH, runs `gen.py`, diffs the result against the installed file, and installs it on request.
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
