#!/bin/sh
# A20 fake forge: a ready repo for crew doctor, and the control item claimed by tmux@OWNER.
# Usage: forge.sh SOURCE STATE REPO OWNER
set -e
src=$1 d=$2/gh base=$2/gh/api-repos/$3
mkdir -p "$base/collaborators/sandbox-reviewer"
printf 'github.com\n  Logged in to github.com account sandbox-builder (keyring)\n  Logged in to github.com account sandbox-reviewer (keyring)\n' > "$d/auth-status.json"
echo '{"permission":"write"}' > "$base/collaborators/sandbox-reviewer/permission.json"
echo '[[{"title":"M1","state":"open"}]]' > "$base/milestones?state=all&per_page=100.json"
echo '{"data":{"repository":{"projectsV2":{"nodes":[{"id":"P1"}],"pageInfo":{"hasNextPage":false}}}}}' > "$d/api-graphql.json"
echo '{"totalCount":1,"projects":[{"id":"P1","number":1,"title":"sandbox board","closed":false}]}' > "$d/project-list.json"
echo '{"fields":[{"id":"F1","name":"Status","options":[{"name":"Todo"},{"name":"In Progress"},{"name":"In Review"},{"name":"Done"}]}]}' > "$d/project-field-list.json"
python3 - "$src/docs/runbooks/github-tracking.md" "$base/labels?per_page=100.json" "$d/api---paginate---slurp.json" "$4" <<'PY'
import json, re, sys
rows = re.findall(r"^(crew:[^|]+)\|([^|]+)\|(.+)$", open(sys.argv[1]).read(), re.M)
json.dump([[dict(name=n, color=c, description=t) for n, c, t in rows]], open(sys.argv[2], "w"))
claim = ("<!-- crew:v1 role=coordinator pass=handoff handoff=20261105-a20a20 state=claimed from=none to=tmux@%s "
         "cmd-id=a20 sha=%s round=n/a verdict=n/a -->" % (sys.argv[4], "0" * 40))
json.dump([[{"user": {"login": "sandbox-builder"}, "body": claim, "created_at": "2026-11-05T00:00:00Z", "id": 1}]],
          open(sys.argv[3], "w"))
PY
