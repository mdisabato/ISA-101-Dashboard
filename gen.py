"""Generate /config/templates/template_isa_alarm_latch.yaml from the live dashboard rules.

One trigger per monitored point, firing only on the move from normal to abnormal.
Each trigger carries k (key = entity id), g (group or host), l (priority), t (label).
An isa_alarm_ack event clears one key, or all of them.
"""
import json

V = json.load(open('live.json'))['config']['button_card_templates']['isa_l1_data']['variables']
NA = ['unavailable', 'unknown']
SERVICE_DELAY_MIN = 1  # host services: a planned stop of a few seconds (e.g. a backup) does not latch
INGEST_DELAY_MIN = 2   # camera ingest dips while a camera server restarts
trig, seen = [], set()


def add(key, g, l, t, tr):
    if key in seen:
        return
    seen.add(key)
    tr['variables'] = {'k': key, 'g': g, 'l': l, 't': t}
    trig.append(tr)


def state_change(eid, ok, g, l, t, mins=None):
    ok = [ok] if isinstance(ok, str) else list(ok)
    tr = {'trigger': 'state', 'entity_id': eid, 'from': ok, 'not_to': ok + NA}
    if mins:
        tr['for'] = {'minutes': mins}  # on-delay: a short stop (weekly backup) does not latch
    add(eid, g, l, t, tr)


def above(eid, x, g, l, t, mins=None):
    tr = {'trigger': 'numeric_state', 'entity_id': eid, 'above': x}
    if mins:
        tr['for'] = {'minutes': mins}
    add(eid + '#hi', g, l, t, tr)


def below(eid, x, g, l, t, mins=None):
    tr = {'trigger': 'numeric_state', 'entity_id': eid, 'below': x}
    if mins:
        tr['for'] = {'minutes': mins}
    add(eid + '#lo', g, l, t, tr)


names = V['group_names']
for gk, items in V['l1'].items():
    g = names.get(gk, gk)
    for it in items:
        eid, want, label, lvl = it[0], it[1], it[2], it[3]
        o = it[5] if len(it) > 5 and it[5] else {}
        if not eid or 'off_window' in o:
            continue  # not instrumented, or off by schedule (printer)
        if isinstance(want, dict):
            if 'above' in want:
                below(eid, want['above'], g, lvl, label)
            elif 'below' in want:
                above(eid, want['below'], g, lvl, label)
            elif 'resolves' in want:
                # DNS IP sensors go unavailable when the lookup keeps failing
                add(eid, g, lvl, label, {'trigger': 'state', 'entity_id': eid,
                                         'to': ['unavailable'], 'not_from': ['unavailable', 'unknown']})
            elif 'has' in want:
                bad = ' or '.join(f"'{x}' in s" for x in want.get('lacks', []))
                # template trigger fires on false -> true, i.e. normal -> abnormal
                add(eid, g, lvl, label, {'trigger': 'template', 'value_template':
                    f"{{% set s = states('{eid}').split() %}}{{{{ s | count > 0 and s[0] not in ['unavailable', 'unknown'] and ('{want['has']}' not in s{(' or ' + bad) if bad else ''}) }}}}"})
            continue  # stale_min / same_as are not state changes
        state_change(eid, want, g, lvl, label)

for c in V['hosts']:
    g = c['name']
    if c.get('agent'):
        state_change(c['agent'], 'ready', g, 2, 'Agent')
    for s in c.get('services') or []:
        lvl = s[3] if isinstance(s[3], int) and not isinstance(s[3], bool) else (3 if s[3] else 1)
        state_change(s[0], s[1], g, lvl, s[2], SERVICE_DELAY_MIN)
    for s in c.get('checks') or []:
        state_change(s[0], s[1], g, s[3], s[2])
    for s in c.get('counts') or []:
        above(s[0], 0, g, s[2], s[1][:1].upper() + s[1][1:])
    for s in c.get('usb') or []:
        above(s[0], 95, g, 2, f'USB backup {s[1]} over 95%')
    for s in c.get('flags') or []:
        state_change(s[0], 'off', g, s[2], s[1])
    for s in (c.get('net') or {}).get('links') or []:
        state_change(s[0], 'on', g, s[2], f'Switch link {s[1]}')
    nas = c.get('kind') == 'nas'
    for t in c.get('temp') or []:
        above(t, 45 if nas else 75, g, 2, 'Drive temp' if nas else 'CPU temp')
    if c.get('mem'):
        above(c['mem'], 90, g, 2, 'Memory %')
    if c.get('disk'):
        above(c['disk'], 80, g, 2, 'Volume %' if nas else 'Disk %')
    if c.get('load'):
        cores = c.get('cores') or 4
        above(c['load'], round((c.get('load_warn') or 100) / 100 * cores, 3), g, 2, f'Load (15 min, {cores} cores)')
    if c.get('swap'):
        above(c['swap'], 75, g, 2, 'Swap %')
    net = c.get('net') or {}
    if net.get('rx_low'):
        below(net['rx'], net['rx_low'] * 1000, g, 2, 'Camera ingest (kbit/s)', INGEST_DELAY_MIN)  # agents report Kbps

for m in V.get('metrics') or []:
    sc = m.get('scale') or 1
    if 'lo_warn' in m:
        below(m['id'], round(m['lo_warn'] / sc + 0.5, 1), m.get('group', 'Power'), 2, m['label'], m.get('on_delay'))
    if 'hi_warn' in m:
        above(m['id'], round(m['hi_warn'] / sc - 0.5, 1), m.get('group', 'Power'), 2, m['label'], m.get('on_delay'))

trig.append({'trigger': 'event', 'event_type': 'isa_alarm_ack', 'variables': {'k': '', 'g': '', 'l': 0, 't': ''}})

EVENTS = r"""{%- set old = (this.attributes.events | default([])) if this is defined and this.attributes is defined else [] -%}
{%- if trigger.platform == 'event' -%}
  {%- set key = trigger.event.data.key | default('all') -%}
  {{ [] if key == 'all' else old | rejectattr('k', 'eq', key) | list }}
{%- elif old | selectattr('k', 'eq', k) | list | count > 0 -%}
  {{ old }}
{%- elif trigger.platform in ['state', 'numeric_state'] and (not trigger.to_state or not trigger.from_state
     or trigger.from_state.state in ['unavailable', 'unknown']) -%}
  {#- a reload or restart: the entity was removed, re-created or had no value yet; not a real fault -#}
  {{ old }}
{%- else -%}
  {%- set st = trigger.to_state.state if trigger.to_state is defined and trigger.to_state else '' -%}
  {%- set u = trigger.to_state.attributes.unit_of_measurement | default('') if trigger.to_state is defined and trigger.to_state else '' -%}
  {{ (old + [{'k': k, 'g': g, 'l': l, 't': t ~ (': ' ~ st ~ ((' ' ~ u) if u else '') if st else ''), 'at': now().isoformat()}])[-50:] }}
{%- endif -%}"""

out = [{
    'trigger': trig,
    'sensor': [{
        'name': 'ISA unacknowledged alarms',
        'unique_id': 'isa_unacknowledged_alarms',
        'icon': 'mdi:alarm-light-outline',
        'state': "{{ now().isoformat() }}",
        'attributes': {'events': EVENTS},
    }],
}]
hdr = ('# ISA-101 alarm latch for the ISA-101 dashboard.\n'
       '# GENERATED from the dashboard rules (isa_l1_data) by Claude, 2026-11-15. Edits here are lost on regeneration.\n'
       '# Records each monitored point the moment it goes from normal to abnormal, so a failure that\n'
       '# clears on its own stays listed until acknowledged (event isa_alarm_ack, key = id or "all").\n')
open('template_isa_alarm_latch.yaml', 'w').write(hdr + json.dumps(out, indent=1))
print(len(trig) - 1, 'points')


def q(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(v)  # double-quoted YAML scalar


def dump(o, ind=0):
    p = ' ' * ind
    lines = []
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, str) and '\n' in v:
                lines.append(f'{p}{k}: >-')
                lines += [p + '  ' + ln for ln in v.split('\n')]
            elif isinstance(v, dict) and all(not isinstance(x, (dict, list)) and not (isinstance(x, str) and '\n' in x) for x in v.values()):
                lines.append(f'{p}{k}: {{' + ', '.join(f'{a}: {q(b)}' for a, b in v.items()) + '}')
            elif isinstance(v, list) and all(not isinstance(x, (dict, list)) for x in v):
                lines.append(f'{p}{k}: [' + ', '.join(q(x) for x in v) + ']')
            elif isinstance(v, (dict, list)):
                lines.append(f'{p}{k}:')
                lines += dump(v, ind + 2)
            else:
                lines.append(f'{p}{k}: {q(v)}')
    else:
        for it in o:
            sub = dump(it, ind + 2)
            sub[0] = p + '- ' + sub[0][ind + 2:]
            lines += sub
    return lines


open('template_isa_alarm_latch.yaml', 'w').write(hdr + '\n'.join(dump(out)) + '\n')
