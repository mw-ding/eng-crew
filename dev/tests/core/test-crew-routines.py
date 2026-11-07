"""Role routine tests (#1247; docs/routines.md), stdlib only.

Schedule parsing and validation (durations, interval keys and jitter, five-field cron, the miss policies, actions and
due_on events against the actions contract's vocabulary), miss handling in due() (first run, on time, skip,
catch-up-once, escalate, retry, due_on events, enable switches, cron slots in the owner's timezone), and parity: the
migrated researcher and coordinator routines keep today's cadence (triage every interval_hours, default 6 h; docs pass
every interval_days, default 7 d; 10 min retries; a 30 min backstop backing off to x16) and every seat package has a
routines/ folder. Run in CI.
"""
import datetime
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
spec = importlib.util.spec_from_file_location("crew_routines", os.path.join(ROOT, "core", "crew-routines.py"))
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)
spec = importlib.util.spec_from_file_location("actions_contract", os.path.join(ROOT, "actions", "contract.py"))
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)

BASE = {"description": "d", "skill": "digest", "actions": ["read", "report"], "schedule": {"every": "6h"},
        "inputs": [], "outputs": ["report"], "deadline": "1h", "on_miss": "catch-up-once"}
H = 3600


def routine(**over):
    r = dict(BASE, **over)
    return {k: v for k, v in r.items() if v is not None}


class Validation(unittest.TestCase):
    def problems(self, data, **kw):
        return [(key, reason) for _, key, reason in cr.check("x.toml", data, **kw)]

    def test_valid_interval_and_cron(self):
        self.assertEqual(self.problems(routine()), [])
        self.assertEqual(self.problems(routine(schedule={"cron": "*/15 9-17 * * 1-5", "timezone": "owner"})), [])
        self.assertEqual(self.problems(routine(schedule={"every": "1d", "every_key": "docs.interval_days",
                                                         "jitter": "5m"})), [])

    def test_durations(self):
        self.assertEqual([cr.seconds(t) for t in ("90s", "10m", "6h", "7d", "0s", "6", "1w", 6)],
                         [90, 600, 21600, 604800, None, None, None, None])

    def test_required_unknown_and_types(self):
        data = routine(deadline=None, extra=1, actions="read")
        self.assertEqual(self.problems(data), [("actions", "expected list"), ("extra", "unknown key"),
                                               ("deadline", "required")])

    def test_schedule_rules(self):
        cases = [
            ({}, ("schedule", "expected exactly one of every and cron")),
            ({"every": "6h", "cron": "0 9 * * *"}, ("schedule", "expected exactly one of every and cron")),
            ({"every": "6"}, ("schedule.every", "expected a duration such as 90s, 10m, 6h or 7d")),
            ({"cron": "0 9 * *"}, ("schedule.cron", "expected five fields: minute hour day-of-month month day-of-week")),
            ({"cron": "60 9 * * *"}, ("schedule.cron", "field '60' outside 0-59")),
            ({"cron": "0 9 * * 7"}, ("schedule.cron", "field '7' outside 0-6")),
            ({"cron": "0 9 * * *", "jitter": "5m"}, ("schedule.jitter", "only with every")),
            ({"every": "6h", "every_key": "triage.interval"},
             ("schedule.every_key", "expected a profile key ending in _seconds, _minutes, _hours, _days")),
            ({"every": "10m", "jitter": "10m"}, ("schedule.jitter", "expected a duration shorter than every, such as 0s or 5m")),
            ({"every": "6h", "timezone": "UTC"}, ("schedule.timezone", "expected \"owner\" (the profile's runtime.timezone)")),
            ({"every": "6h", "at": "9"}, ("schedule.at", "unknown key")),
        ]
        for sched, want in cases:
            with self.subTest(sched=sched):
                self.assertIn(want, self.problems(routine(schedule=sched)))

    def test_miss_policy_and_fields(self):
        self.assertIn(("on_miss", "expected one of skip, catch-up-once, escalate"), self.problems(routine(on_miss="retry")))
        self.assertIn(("retry", "expected a duration such as 90s, 10m, 6h or 7d"), self.problems(routine(retry="soon")))
        self.assertIn(("outputs", "expected at least one output"), self.problems(routine(outputs=[])))
        self.assertIn(("actions", "expected at least one generic action"), self.problems(routine(actions=[])))
        self.assertIn(("inputs", "expected distinct nonempty strings"), self.problems(routine(inputs=["a", "a"])))
        self.assertIn(("idle_backoff", "expected an integer >= 1"), self.problems(routine(idle_backoff=0)))
        self.assertIn(("enabled_key", "use enabled or enabled_key, not both"),
                      self.problems(routine(enabled=False, enabled_key="triage.enabled")))
        self.assertIn(("skill", "expected a skill ID"), self.problems(routine(skill="Digest Run")))
        self.assertIn(("skill", "expected a skill ID under the package's skills/"),
                      self.problems(routine(), skills={"other"}))

    def test_generic_vocabulary_only(self):
        actions, events = set(contract.ACTIONS), {"dev.eng-crew.milestone.closed"}
        self.assertEqual(self.problems(routine(due_on=["dev.eng-crew.milestone.closed"]), actions=actions,
                                       events=events), [])
        self.assertEqual(self.problems(routine(actions=["read", "crew-spawn"], due_on=["milestone-closed"]),
                                       actions=actions, events=events),
                         [("actions", "'crew-spawn' is not an action of the actions contract"),
                          ("due_on", "'milestone-closed' is not an event type of the actions contract")])

    def test_cli_and_load(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        folder = os.path.join(tmp, "roles", "ops", "analyst", "routines")
        os.makedirs(folder)
        with open(os.path.join(folder, "digest.toml"), "w") as f:
            f.write('description = "d"\nskill = "digest"\nactions = ["read"]\nschedule = { every = "1d" }\n'
                    'inputs = []\noutputs = ["digest"]\ndeadline = "1h"\non_miss = "skip"\n')
        with open(os.path.join(folder, "Bad_Name.toml"), "w") as f:
            f.write("")
        open(os.path.join(folder, ".gitkeep"), "w").close()
        found, problems = cr.load(os.path.join(tmp, "roles"))
        self.assertEqual(list(found), [("analyst", "digest")])
        self.assertEqual((found[("analyst", "digest")]["path"], found[("analyst", "digest")]["team"]),
                         ("roles/ops/analyst/routines/digest.toml", "ops"))
        self.assertEqual(problems, [("roles/ops/analyst/routines/Bad_Name.toml", "file",
                                     "expected <routine>.toml with a kebab-case name")])
        r = subprocess.run([sys.executable, os.path.join(ROOT, "core", "crew-routines.py"), os.path.join(tmp, "roles"),
                            "--actions", "report"], capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.splitlines()), (1, [
            "roles/ops/analyst/routines/Bad_Name.toml:file: expected <routine>.toml with a kebab-case name",
            "roles/ops/analyst/routines/digest.toml:actions: 'read' is not an action of the actions contract"]))


class Due(unittest.TestCase):
    NOW = 1_800_000_000

    def due(self, r, last, now=None, values=None, events=()):
        return cr.due(r, values or {}, last, self.NOW if now is None else now, events)

    def test_first_run_anchors(self):
        self.assertEqual(self.due(routine(), None), ("run", self.NOW))

    def test_on_time_and_not_yet(self):
        last = {"at": self.NOW, "outcome": "started"}
        self.assertEqual(self.due(routine(), last, self.NOW + 6 * H - 1), (None, None))
        self.assertEqual(self.due(routine(), last, self.NOW + 6 * H + 60), ("run", self.NOW + 6 * H))

    def test_miss_policies(self):
        last = {"at": self.NOW, "outcome": "started"}
        later = self.NOW + 6 * H + 2 * H  # the 6 h slot's 1 h deadline passed
        self.assertEqual(self.due(routine(on_miss="skip"), last, later), ("skip", self.NOW + 6 * H))
        self.assertEqual(self.due(routine(on_miss="catch-up-once"), last, later), ("run", self.NOW + 6 * H))
        self.assertEqual(self.due(routine(on_miss="escalate"), last, later), ("escalate", self.NOW + 6 * H))

    def test_long_gap_takes_the_latest_slot_once(self):
        last = {"at": self.NOW, "outcome": "started"}
        later = self.NOW + 48 * H + 30 * 60  # eight slots later, 30 min into the latest
        self.assertEqual(self.due(routine(on_miss="skip"), last, later), ("run", self.NOW + 48 * H))
        later = self.NOW + 50 * H  # 2 h into the latest slot: every slot of the gap missed
        self.assertEqual(self.due(routine(on_miss="catch-up-once"), last, later), ("run", self.NOW + 48 * H))
        self.assertEqual(self.due(routine(on_miss="skip"), {"at": self.NOW + 48 * H, "outcome": "skipped: missed"},
                                  later), (None, None), "a recorded skip waits for the next slot")

    def test_retry_after_failure(self):
        last = {"at": self.NOW, "outcome": "failed: exit 1"}
        r = routine(retry="10m")
        self.assertEqual(self.due(r, last, self.NOW + 599), (None, None))
        self.assertEqual(self.due(r, last, self.NOW + 600), ("run", self.NOW + 600))
        self.assertEqual(self.due(routine(), last, self.NOW + 600), (None, None), "no retry: the next slot")

    def test_due_on_event(self):
        r = routine(due_on=["dev.eng-crew.milestone.closed"])
        last = {"at": self.NOW, "outcome": "started"}
        self.assertEqual(self.due(r, last, self.NOW + 60, events=[("dev.eng-crew.milestone.closed", self.NOW + 30)]),
                         ("run", self.NOW + 60))
        self.assertEqual(self.due(r, last, self.NOW + 60, events=[("dev.eng-crew.milestone.closed", self.NOW - 30)]),
                         (None, None), "an event before the last run was already taken")
        self.assertEqual(self.due(r, last, self.NOW + 60, events=[("dev.eng-crew.item.changed", self.NOW + 30)]),
                         (None, None))

    def test_enable_switches(self):
        self.assertEqual(self.due(routine(enabled=False), None), (None, None))
        r = routine(enabled_key="triage.enabled")
        self.assertEqual(self.due(r, None, values={"triage.enabled": False}), (None, None))
        self.assertEqual(self.due(r, None, values={"triage.enabled": True}), ("run", self.NOW))

    def test_interval_key_and_jitter(self):
        r = routine(schedule={"every": "6h", "every_key": "triage.interval_hours"})
        self.assertEqual(cr.interval(r, {}), 6 * H)
        self.assertEqual(cr.interval(r, {"triage.interval_hours": 2}), 2 * H)
        r = routine(schedule={"every": "6h", "jitter": "10m"}, role="analyst", path="a.toml")
        last = {"at": self.NOW, "outcome": "started"}
        start = cr.slot(r, {}, self.NOW, self.NOW + 7 * H)
        self.assertTrue(self.NOW + 6 * H <= start <= self.NOW + 6 * H + 600)
        self.assertEqual(start, cr.slot(r, {}, self.NOW, self.NOW + 7 * H), "stable across scans")
        self.assertEqual(self.due(r, last, start - 1), (None, None))

    def test_cron_in_owner_timezone(self):
        r = routine(schedule={"cron": "0 9 * * 1"}, deadline="4h", on_miss="skip")  # Mondays 09:00
        values = {"runtime.timezone": "America/Los_Angeles"}
        tz = cr.zone(values)
        monday = datetime.datetime(2026, 11, 9, 9, 0, tzinfo=tz).timestamp()
        last = {"at": monday - 7 * 86400, "outcome": "started"}
        self.assertEqual(self.due(r, last, monday - 60, values), (None, None))
        self.assertEqual(self.due(r, last, monday + 3600, values), ("run", monday))
        self.assertEqual(self.due(r, last, monday + 5 * 3600, values), ("skip", monday))
        utc = cr.slot(r, {}, last["at"], monday + 3600)
        self.assertNotEqual(utc, monday, "09:00 UTC is not 09:00 in the owner's timezone")


class Migrated(unittest.TestCase):
    """Parity: the routine files reproduce the cadence the watcher had before #1247."""

    @classmethod
    def setUpClass(cls):
        cls.routines, cls.problems = cr.load(os.path.join(ROOT, "roles"))

    def test_all_valid_against_the_contract(self):
        self.assertEqual(self.problems, [])
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check-repo.py"), "--only", "routines"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_inventory(self):
        self.assertEqual(sorted(self.routines), [
            ("coordinator", "decision-log-status"), ("coordinator", "metrics-refresh"), ("coordinator", "stale-sweep"),
            ("researcher", "docs-pass"), ("researcher", "milestone-close-sweep"), ("researcher", "triage-sweep")])

    def test_triage_cadence(self):
        for name in ("triage-sweep", "milestone-close-sweep"):
            r = self.routines[("researcher", name)]
            self.assertEqual(cr.interval(r, {}), 6 * H)  # [triage] interval_hours default
            self.assertEqual(cr.interval(r, {"triage.interval_hours": 3}), 3 * H)
            self.assertEqual(cr.seconds(r["retry"]), 600)  # the old SWEEP_RETRY
            self.assertFalse(cr.enabled(r, {}))  # [triage] enabled defaults off
            self.assertTrue(cr.enabled(r, {"triage.enabled": True}))
            self.assertEqual(cr.due(r, {"triage.enabled": True}, None, 0), ("run", 0), "overdue sweeps at once")
        self.assertEqual(self.routines[("researcher", "milestone-close-sweep")]["due_on"],
                         ["dev.eng-crew.milestone.closed"])

    def test_docs_cadence(self):
        r = self.routines[("researcher", "docs-pass")]
        self.assertEqual(cr.interval(r, {}), 7 * 86400)
        self.assertEqual(cr.interval(r, {"docs.interval_days": 2}), 2 * 86400)
        self.assertEqual(cr.seconds(r["retry"]), 600)
        self.assertFalse(cr.enabled(r, {}))

    def test_backstop_cadence(self):
        r = self.routines[("coordinator", "stale-sweep")]
        self.assertEqual((cr.interval(r, {}), r["idle_backoff"], r["on_miss"]), (1800, 16, "skip"))

    def test_manual_jobs_stay_unscheduled(self):
        for name in ("metrics-refresh", "decision-log-status"):
            r = self.routines[("coordinator", name)]
            self.assertEqual(cr.due(r, {}, None, 0), (None, None))

    def test_seat_packages_have_routines(self):
        seats = os.path.join(ROOT, "roles", "seats")
        for seat in sorted(n for n in os.listdir(seats) if os.path.isdir(os.path.join(seats, n))):
            self.assertTrue(os.path.isdir(os.path.join(seats, seat, "routines")), seat)


if __name__ == "__main__":
    unittest.main()
