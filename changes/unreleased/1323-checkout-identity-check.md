---
type: fixed
issue: 1323
pr: 1368
date: 2026-11-08
box-skill: none
---

`mdstack doctor` and `mdstack up` now catch a half-finished install. When the checkout (`paths.checkout`, else the project directory) has a forge `origin` URL naming a repo other than `[repo]`, doctor's new `checkout` row fails and `up` refuses before rendering, so builders never branch off the wrong repo. A path, `file://` or missing origin only warns. Doctor's new `install` and `mdstack link` rows report bootstrap's `install.json` and the `paths.mdstack` link. Both warn before bootstrap, since bootstrap runs doctor first, and a recorded install whose link is missing fails. `up` refuses a set but missing `paths.mdstack`, so rendered briefs never cite missing docs.
