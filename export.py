"""Export the ISA dashboard's button-card templates from live.json into templates/*.yaml.

The site-specific rules template (isa_l1_data by default) is not exported: it holds your
entity ids and host names. See examples/isa_l1_data.example.yaml for its format.
Usage: python3 export.py [rules_template_name]
"""
import json
import os
import re
import sys

RULES = sys.argv[1] if len(sys.argv) > 1 else 'isa_l1_data'
T = json.load(open('live.json'))['config']['button_card_templates']
PLAIN = re.compile(r'^[A-Za-z_][A-Za-z0-9_ ./-]*$')
RESERVED = {'true', 'false', 'yes', 'no', 'on', 'off', 'null', 'y', 'n', '~'}


def scalar(v):
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    if PLAIN.match(v) and v.lower() not in RESERVED and not v.endswith(' '):
        return v
    return json.dumps(v, ensure_ascii=False)  # double-quoted YAML scalar


def key(k):
    return scalar(str(k))


def block(s, ind):
    # literal block keeps JavaScript line breaks exactly; indent indicator if a line starts with a space
    ind_ind = '2' if s[:1] in (' ', '\n') else ''
    chomp = '+' if s.endswith('\n') else '-'
    pad = ' ' * (ind + 2)
    body = s[:-1] if s.endswith('\n') else s
    return f'|{ind_ind}{chomp}', [pad + ln if ln else '' for ln in body.split('\n')]


def dump(o, ind=0):
    p = ' ' * ind
    out = []
    if isinstance(o, dict):
        if not o:
            return [p + '{}']
        for k, v in o.items():
            if isinstance(v, str) and '\n' in v:
                head, lines = block(v, ind)
                out.append(f'{p}{key(k)}: {head}')
                out += lines
            elif isinstance(v, (dict, list)) and v:
                out.append(f'{p}{key(k)}:')
                out += dump(v, ind + 2)
            elif isinstance(v, (dict, list)):
                out.append(f'{p}{key(k)}: {"{}" if isinstance(v, dict) else "[]"}')
            else:
                out.append(f'{p}{key(k)}: {scalar(v)}')
    else:
        for it in o:
            if isinstance(it, (dict, list)) and it:
                sub = dump(it, ind + 2)
                sub[0] = p + '- ' + sub[0][ind + 2:]
                out += sub
            elif isinstance(it, str) and '\n' in it:
                head, lines = block(it, ind)
                out.append(f'{p}- {head}')
                out += lines
            else:
                out.append(f'{p}- {scalar(it) if not isinstance(it, (dict, list)) else ("{}" if isinstance(it, dict) else "[]")}')
    return out


os.makedirs('templates', exist_ok=True)
for name in sorted(T):
    if name == RULES:
        continue
    with open(f'templates/{name}.yaml', 'w') as f:
        f.write(f'# button-card template "{name}", exported from the dashboard\'s raw config.\n')
        f.write(f'{name}:\n' + '\n'.join(dump(T[name], 2)) + '\n')
    print('exported', name)
