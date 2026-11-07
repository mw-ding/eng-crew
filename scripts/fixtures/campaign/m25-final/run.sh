#!/bin/bash
# M25 final regression (#806): run each scenario in its own fresh level-a sandbox
# (setup, campaign-run.py --scenario, teardown) and print one summary line each.
# Usage: run.sh PRODUCTION_PROFILE OUT_DIR SCENARIO_DIR [AXX ...]  (default: every spec in SCENARIO_DIR)
# OUT_DIR `auto` makes a fresh directory under $HOME; SCENARIO_DIR `variants` builds variants.py's specs there.
set -u
prod=$1 out=$2 scen=$3; shift 3
unset TMUX TMUX_PANE $(env | sed -n 's/^\(CREW_[A-Z_]*\)=.*/\1/p')
src=$(cd "$(dirname "$0")/../../../.." && pwd)
[ "$out" = auto ] && out=$(mktemp -d "$HOME/.m25f.XXXXXX") && echo "out $out"
[ "$scen" = variants ] && scen=$out/variants && mkdir -p "$scen" &&
  python3 "$src/scripts/fixtures/campaign/m25-final/variants.py" "$src/scripts/fixtures/campaign" "$scen" >/dev/null
ids=${*:-$(ls "$scen" | sed -n 's/^\(A[0-9][0-9]\)\.json$/\1/p')}
mkdir -p "$out" && sent=$out/sentinel.txt && echo "m25 final sentinel" > "$sent"
for id in $ids; do
  root=$out/$id t0=$(date +%s)
  python3 "$src/scripts/campaign-sandbox.py" setup --root "$root" --run-id "m25f-$(echo "$id" | tr A-Z a-z)" \
    --production "$prod" --source "$src" --release "source-$(git -C "$src" rev-parse --short=7 HEAD)" \
    --sentinel "$sent" --scenario "$id" > "$out/$id.setup.log" 2>&1
  python3 "$src/scripts/campaign-run.py" "$root/state/manifest.json" --scenarios "$scen" \
    --out "$root/state/results.json" --seed 806 > "$out/$id.run.log" 2>&1
  python3 "$src/scripts/campaign-sandbox.py" teardown "$root/state/manifest.json" > "$out/$id.teardown.log" 2>&1
  python3 - "$root/state" "$(($(date +%s) - t0))" <<'PY'
import json, sys
st, secs = sys.argv[1], sys.argv[2]
try:
    r = json.load(open(st + "/results.json"))
    c = json.load(open(st + "/cleanup.json"))
except (OSError, ValueError) as e:
    open(st + "/../../not-pass", "a").write(st + "\n")
    sys.exit(print("NO RESULT", st, e))
for x in r["results"]:
    bad = [s["name"] for s in x.get("steps", []) if ("wait" in s and not s["matched"]) or
           ("wait" not in s and s["exit"] != s.get("want", 0))]
    print(x["id"], x["status"], "src=" + r["source_sha"][:7], "seed=%s" % r["seed"], "secs=" + secs,
          "sentinel=" + ("unchanged" if c["sentinel_unchanged"] else "CHANGED"), "retained=%d" % len(c["retained"]),
          ("failed-step=" + bad[0]) if bad else "")
    for s in x.get("steps", []):  # variant probes: show what each one observed
        if s["name"].startswith(("row", "dependency-")):
            print("  " + s["name"] + ":", *s.get("stdout", "").strip().splitlines()[-40:], sep="\n    ")
    if x["status"] != "PASS":
        open(st + "/../../not-pass", "a").write(x["id"] + "\n")
PY
done
[ ! -s "$out/not-pass" ]
