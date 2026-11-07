# A23 step helpers, sourced by every A23 step after it sets SRC (eng-crew source), ST (sandbox state) and RUN.
C="python3 $SRC/scripts/crew"
P="--project $CREW_PROJECT --org-profile $ST/org-a23.toml"
S=$ST/campaign__sandbox-$RUN R=$ST/../repo H=$ST/a23 L=$ST/a23/ssh.log
export A23_LOCAL_LOG=$H/local.log
tip() { git -C "$R" rev-parse HEAD; }
# runner SHA [--host H]: the public runner client at SHA for check-repo and the sample test, from the sandbox checkout.
runner() { h=$1; shift; (cd "$R" && $C runner run --poll 0.2 $P --head "$h" "$@" -- check-repo test-a23.py); }
logs() { (cd "$R" && $C runner logs $P "$@"); }
capture() { (cd "$R" && CREW_STATE=$S python3 "$SRC/scripts/evidence-cli.py" --label T1 --runner "$1"); }
# call HOST JSON: one request straight to the host entrypoint over the fake transport.
call() { echo "$2" | ssh -T "$1" crew-host; }
fault() { echo "$*" >> "$H/faults"; }
# field VERB KEY: KEY of every logged call with VERB, one per line.
field() { python3 -c 'import json,sys; [print(r[sys.argv[2]]) for r in map(json.loads, open(sys.argv[3])) if r["verb"] == sys.argv[1]]' "$1" "$2" "$L"; }
job() { echo "$1" | sed -n 's|^runner:[a-z]*/\([^ ]*\) head=.*|\1|p'; }
red() { (cd "$R" && sed -i.bak "s/^RED = .*/RED = $1/" scripts/test-a23.py && rm scripts/test-a23.py.bak &&
  git -c user.name=c -c user.email=c@x commit -qam "test: RED = $1" -m "Engine: claude-code opus medium" &&
  git push -q -f origin HEAD:b23); }
up() {
  mkdir -p "$H/skew/scripts" "$ST/bin" && cp "$SRC/dev/tests/scripts/fixtures/campaign/a23/ssh" "$ST/bin/ssh" &&
  cp "$SRC/scripts/crew-remote.py" "$H/skew/scripts/" && echo v0.0.1 > "$H/skew/VERSION" || return 1
  printf '{"loop": {"entry": "%s", "root": "%s"}, "skew": {"entry": "%s", "root": "%s"}, "gone": {"entry": null, "root": "%s"}}\n' \
    "$SRC/scripts/crew-remote.py" "$H/host-loop" "$H/skew/scripts/crew-remote.py" "$H/host-skew" "$H/host-gone" > "$H/hosts.json"
  { printf '[hosts.primary]\nprimary = true\nmax_runs = 2\ncapabilities = { os = "macos", arch = "arm64", engines = ["claude-code"] }\n'
    for h in loop skew gone; do
      printf '[hosts.%s]\nforge = false\nmax_runs = 2\nroot = "%s"\ncapabilities = { os = "macos", arch = "arm64" }\n' $h "$H/host-$h"
    done; } > "$ST/org-a23.toml"
  (cd "$R" && git checkout -q -B b23 main && cp -R "$SRC/dev/tests/scripts/fixtures/campaign/a23/sample/scripts" . &&
    git add scripts && git -c user.name=c -c user.email=c@x commit -qm "feat: sample checks" -m "Engine: claude-code opus medium" &&
    git push -q -f origin HEAD:b23)
}
