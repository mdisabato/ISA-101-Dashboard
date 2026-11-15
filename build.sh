#!/bin/zsh
# Rebuild the ISA alarm latch from the live dashboard rules.
#   ./build.sh            fetch rules, generate, show the diff against the installed file (changes nothing)
#   ./build.sh install    same, then back up the installed file and install the new one
# After install: check the config and reload template entities in Home Assistant.
# Connection settings come from latch.env (copy latch.env.example and fill it in).
set -e
cd "${0:A:h}"
[[ -f latch.env ]] || { echo "Missing latch.env: copy latch.env.example and fill it in." >&2; exit 1; }
source ./latch.env
: ${HA_HOST:?} ${HA_USER:?} ${HA_SSH_PORT:=22} ${DASHBOARD:?}
DEST=${LATCH_FILE:-/config/templates/template_isa_alarm_latch.yaml}
SSH=(ssh -o BatchMode=yes -p "$HA_SSH_PORT")
[[ -n "$HA_SSH_KEY" ]] && SSH+=(-i "$HA_SSH_KEY")
SSH+=("$HA_USER@$HA_HOST")

"${SSH[@]}" "sudo -n cat /config/.storage/lovelace.$DASHBOARD" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); json.dump({'config': d['data']['config']}, open('live.json','w'))"
python3 gen.py

"${SSH[@]}" "sudo -n cat $DEST" > installed.yaml
if diff -u installed.yaml template_isa_alarm_latch.yaml; then
  echo "No change: the installed latch already matches the rules."
  rm -f installed.yaml
  exit 0
fi
rm -f installed.yaml

if [[ "$1" == "install" ]]; then
  stamp=$(date +%Y%m%d-%H%M)
  "${SSH[@]}" "sudo -n cp $DEST $DEST.bak-$stamp && cat > /tmp/latch.yaml && sudo -n cp /tmp/latch.yaml $DEST" < template_isa_alarm_latch.yaml
  echo "Installed. Backup: $DEST.bak-$stamp"
  echo "Now check the config and reload template entities in Home Assistant."
fi
