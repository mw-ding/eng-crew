Landing authority: only synthesizer chooses direct/train, members, order,
isolation, close/rebuild. Use §7/profile, never per-project steering; record
decisions/reasons in train or merge report. Other coordinator advice may be ignored.
Recorded coordinator pass=steer only: cmd=land (approved refs), cmd=hold,
cmd=hold-release (reason + hold-until-#N); owner cmd=merge-ok,
cmd=mirror-deferral, cmd=profile; cmd=urgent (one head alone ahead of batching,
every §7 gate); cmd=stop-landing, cmd=resume-landing (project line).
Urgency only: release blocker, security fix, explicit owner request,
stop-the-line incident. Stop: red default branch, CI provider outage, owner request.
Before first stop write `<state-dir>/<owner>__<repo>/landing-control.json` {"issue":N}; retain across restart/closure.
Signed control comments: stops have cmd-id; resumes name it as stop-id. Read before every squash:
control comments/PR reviews; unmatched stop/unreadable control blocks.
Urgent/merge-ok/grants never waive stops.
