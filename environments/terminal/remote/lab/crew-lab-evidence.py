#!/usr/bin/env python3
"""Lab run manifest and evidence record (M20.1 lab G, #1361).

crew-lab-scenarios.py calls write() once per run. It writes state/lab/runs/<started>.json and a Markdown copy to
paste as PR evidence for #207 and #345-#348. The record names lab C, the hosts, the image digest, the staged bundle
hashes and source SHA, the client bundle, the transport, every injected event and a timeline. It labels what is
simulated or a stub: loopback SSH and Docker network controls are simulated, the sample checks and the engine, forge
and mirror origin behind the partition's placed run are stubs, and nothing is a real device. A scenario that did not run is `skipped` with
`evidence: false`, so it supplies no evidence.
"""
import datetime
import json
import os
from pathlib import Path

CONTROLS = dict(disconnect="docker network disconnect, then connect", pause="docker pause, then unpause",
                runner="docker exec kill of the runner pid; its supervisor restarts it",
                recreate="docker rm -f of the container and network, then a new container")
STUBS = ["sample repo branch lab: scripts/check-repo.py and dev/tests/lab/test-lab.py, not the project's checks",
         "partition: mdstack spawn places a real run, but its engine is a shell loop installed as claude and the host's "
         "gh a stub answering for lab-bot; the primary has the sandbox's fake forge, and the host's mirror is seeded "
         "from a bundle and is its own origin",
         "attach: a run planted by docker exec as crew (record, tmux window and step summary); no spawn, engine or forge"]


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def event(control, phase):
    """An injected event: always simulated, with the Docker control that made it."""
    return dict(t=now(), event=control, phase=phase, simulated=True, control=CONTROLS[control])


def record(m, host, client_sha, started, timeline, report, names):
    lab = m["lab"]
    scenarios = {n: dict(status="skipped", evidence=False) for n in names}
    for n, r in report.items():
        scenarios[n] = dict(status="pass" if r["passed"] else "fail", evidence=True, seconds=r["seconds"],
                            failures=r["failures"])
    hosts = {h: dict(container=x["container"], network=x["network"], port=x.get("port"), host_key=x.get("host_key"),
                     bundle_sha256=(x.get("activated") or {}).get("bundle_sha256"),
                     source_sha=(x.get("activated") or {}).get("source_sha")) for h, x in lab["hosts"].items()}
    port = hosts[host]["port"]
    return dict(lab="C", run=lab["run"], simulated=True, real_device=False, started=started, finished=now(),
                context=lab.get("context"), endpoint=lab.get("endpoint"), image=lab.get("image"), tag=lab.get("tag"),
                stage=lab["stage"], source_sha=lab.get("source_sha"), client_bundle_sha256=client_sha, hosts=hosts,
                transport=dict(kind="ssh", host=host, path="127.0.0.1:%s" % port, simulated=True,
                               client="mdstack runner, the hardened -F none call",
                               note="loopback-published Docker port, not a device network or overlay"),
                stubs=STUBS, events=[e for e in timeline if e.get("simulated")], timeline=timeline,
                scenarios=scenarios)


def markdown(rec):
    t = rec["transport"]
    out = ["## Lab %s run %s: simulated, not a real device" % (rec["lab"], rec["run"]), "",
           "- Window: %s to %s" % (rec["started"], rec["finished"]),
           "- Image: `%s`; tag `%s`; source SHA `%s`" % (rec["image"], rec["tag"], rec["source_sha"]),
           "- Bundle: %s; client `%s`" % (", ".join("`%s` `%s`" % kv for kv in sorted(rec["stage"].items())),
                                           rec["client_bundle_sha256"]),
           "- Transport: %s to `%s` via %s (simulated: %s)" % (t["kind"], t["path"], t["client"], t["note"])]
    out += ["- Host `%s`: container `%s`, network `%s`, port %s, bundle `%s`, source `%s`" % (
        h, x["container"], x["network"], x["port"], x["bundle_sha256"], x["source_sha"])
        for h, x in sorted(rec["hosts"].items())]
    out += ["- Stub: " + s for s in rec["stubs"]]
    out += ["", "| Scenario | Status | Evidence |", "|---|---|---|"]
    out += ["| %s | %s | %s |" % (n, s["status"], "yes" if s["evidence"] else "no: did not run")
            for n, s in rec["scenarios"].items()]
    out += ["", "~~~text"] + ["%s %s %s%s" % (e["t"], e.get("scenario", "-"), e["event"], (
        " %s (simulated: %s)" % (e["phase"], e["control"]) if e.get("simulated") else " " + e["phase"]))
        for e in rec["timeline"]] + ["~~~", ""]
    return "\n".join(out)


def write(d, rec):
    """state/lab/runs/<started>.json and .md; returns the JSON path."""
    os.makedirs(os.path.join(d, "runs"), exist_ok=True)
    base = os.path.join(d, "runs", rec["started"].replace(":", ""))
    Path(base + ".json").write_text(json.dumps(rec, indent=2, default=str) + "\n")
    Path(base + ".md").write_text(markdown(rec))
    return base + ".json"
