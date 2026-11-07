"""Build the M25 final-run variant specs (#806) from the committed campaign specs.

Usage: python3 variants.py SCENARIO_DIR OUT_DIR. Writes A03 (row 36 probe), A04 (fixture body + #814 dependency
wake), A17 (no #1070 release workaround), A23 (#743 automatic pick) and A26 (#1098, row 34) to OUT_DIR.
"""
import json, sys
src, out = sys.argv[1], sys.argv[2]
load = lambda a: json.load(open(f"{src}/{a}.json"))
def sub(step, old, new):
    assert old in step["run"], (step["name"], old)
    step["run"] = step["run"].replace(old, new)
# A26 (#1098/#1149): no closed-milestone trigger during the pause; then row 34.
d = load("A26"); s = {x["name"]: x for x in d["steps"]}
d["title"] = "A26 variant (#806): resume from empty baseline, no closed milestone; row 34 queued slot"
sub(s["paused-forge-moves-nothing-queued"], " && ms 3 M3", "")
sub(s["paused-forge-moves-nothing-queued"], "milestone M3 closed, ", "no milestone closed, ")
r = s["resume-catches-up-once-one-overdue-sweep"]
sub(r, 'eq "$(taken)" M3', 'eq "$(taken)" ""')
sub(r, '\ngrep -q "M3" $S/runs/riley-sweep.brief.md || { echo "sweep Item does not name M3"; exit 1; }', "")
c = s["capped-sweep-queued-milestone-taken-only-on-start"]
sub(c, 'eq "$(taken)" M3;', 'eq "$(taken)" "";')
sub(c, 'eq "$(taken)" "M3 M4"', 'eq "$(taken)" "M4"')
prelude = c["run"].split("\nfor i in 11 12;")[0]
d["steps"].append({"name": "row34-completed-sweep-then-new-milestone-starts-sweep", "exit": 0, "run": prelude + r"""
sq() { grep -c '"sweep": true' $S/spawn-queue.jsonl 2>/dev/null || true; }
echo "slot after the dequeued sweep started: $(slot)"
tmux send-keys -t "=$T:riley-sweep" "campaign-exec: echo 'done: triage none' >> \$CREW_STATUS" Enter
for k in $(seq 100); do [ "$(grep -c '^done: triage' $S/status/riley-sweep.status 2>/dev/null)" -ge 2 ] && break; sleep 0.1; done
out=$(tick); $C drain $P >/dev/null; clear; echo "$out" | grep -E "^crew: (killed|started)"
ms 5 M5; for k in 1 2 3; do tick >/dev/null; clear; done
echo "M5 closed after the dequeued sweep finished: slot $(slot); sweeps started $(starts riley-sweep); taken $(taken)"
eq "$(starts riley-sweep)" 3; eq "$(taken)" "M4 M5"
"""})
json.dump(d, open(f"{out}/A26.json", "w"), indent=1)
# A17 (#1050/#1150): no `mdstack schedule release` after a reaped reviewer; the next pass must be admitted at once.
d = load("A17"); n = 0
d["title"] = "A17 variant (#806): no scheduler release after a reaped reviewer (#1070 workaround removed)"
for x in d["steps"]:
    old = x.get("run", "")
    x["run"] = old.replace('CREW_POOL=reviewer $C schedule release --pool reviewer "#$1" $P >/dev/null', "true")
    n += old != x["run"]
assert n, "no release call found"
json.dump(d, open(f"{out}/A17.json", "w"), indent=1)
# A04 (diagnostic): issue fixtures carry a body, as real `gh --json number,body` would.
d = load("A04"); n = 0
d["title"] = "A04 diagnostic (#806): issue-list fixtures include body"
for x in d["steps"]:
    old = x.get("run", "")
    x["run"] = old.replace('"assignees":[{"login":"sandbox-builder"}]}', '"assignees":[{"login":"sandbox-builder"}],"body":""}')
    n += old != x["run"]
json.dump(d, open(f"{out}/A04.json", "w"), indent=1); assert n == 1
# Row 44 (#814): a composed dependency merge dispatches its dependent at once, not at the backstop.
m = {x["name"]: x for x in d["steps"]}["merge-missed-while-watcher-down-reconciled"]["run"]
pre = m.split(" rm -f $S/wake/queue.jsonl;")[0]
d["steps"].append({"name": "dependency-merge-wakes-coordinator-for-dependent-814", "exit": 0, "run": pre + r"""
printf '%s' '[{"number":2,"labels":[{"name":"crew:ready"}],"assignees":[{"login":"sandbox-builder"}],"body":""},{"number":7,"labels":[],"assignees":[],"body":"Depends on #2"}]' > $G/issue-list.json
pr 6 $h "$GREEN" "[]" OPEN; $C poll --once $P >/dev/null; $C route $P >/dev/null; rm -f $S/wake/queue.jsonl
pr 6 $h "$GREEN" "[]" MERGED
out=$($C watch --source "$C poll --once $P" --interval 0.5 --backstop 30 --no-nudge $P); echo "watch: $out"
echo "$out" | head -1 | grep -qx "poll: pr-merged" || exit 1
python3 -c "import json,sys; q=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]; m=[w for w in q if w.get('event')=='pr-merged']; print('queued:', m); assert len(m)==1 and m[0].get('consumer')=='coordinator' and m[0].get('dependents')==['#7']" $S/wake/queue.jsonl
"""})
json.dump(d, open(f"{out}/A04.json", "w"), indent=1)
# Row 32 (#743/#1117): what automatic pick sees for each forge-less host after the check verb landed.
d = load("A23"); d["title"] = "A23 variant (#806): automatic pick after #1117"
d["steps"].append({"name": "row32-automatic-pick-host-check", "exit": 0, "run": r"""SRC={source} ST={state_dir} RUN={run_id}; . $SRC/dev/tests/scripts/fixtures/campaign/a23/lib.sh; h=$(tip)
for x in loop skew gone; do echo "== mdstack host check $x"; (cd "$R" && $C host check $x $P); echo "exit $?"; done
echo "== mdstack host prepare loop"; (cd "$R" && $C host prepare loop $P); echo "exit $?"
echo "== runner, no --host"; runner $h; echo "exit $?"
python3 $SRC/scripts/crew-remote.py --root $H/host-loop runner --interval 1 >$H/svc.log 2>&1 & svc=$!
echo "== runner service started; mdstack host check loop"; (cd "$R" && $C host check loop $P); echo "exit $?"
echo "== runner, no --host, service up"; out=$(runner $h); rc=$?; echo "$out"; echo "exit $rc"; kill $svc
echo "$out" | grep -q "^runner:loop/" && echo "automatic pick chose loop" || echo "BLOCKED: automatic pick fell back; the runner service needs a tmux server outside the sandbox"
"""})
json.dump(d, open(f"{out}/A23.json", "w"), indent=1)
# Row 36: does `mdstack up` / `lead ensure` leave a status directory for a fresh lead's first ack?
d = {"id": "A03", "title": "A03 probe (#806): status directory after mdstack up (row 36)", "steps": [{"name": "row36-status-dir-after-up", "exit": 0, "run": r"""C="python3 {source}/scripts/crew"; P="--project $CREW_PROJECT"; S={state_dir}/campaign__sandbox-{run_id}; G={state_dir}/gh
mkdir -p $G && echo [] > $G/pr-list.json && echo [] > $G/issue-list.json && echo '{"defaultBranchRef":{"name":"main"}}' > $G/repo-view.json
$C up $P >/dev/null || exit 1
for k in $(seq 50); do [ -d $S/status ] && break; sleep 0.1; done
ls -d $S/status 2>/dev/null && ls $S/status || echo "no status directory after mdstack up"
$C send builder-lead work "#2" --wait-ack 10 $P; echo "send exit $?"
ls $S/status 2>/dev/null; cat $S/status/builder-lead.status 2>/dev/null || echo "no builder-lead status file"
"""}]}
json.dump(d, open(f"{out}/A03.json", "w"), indent=1)
