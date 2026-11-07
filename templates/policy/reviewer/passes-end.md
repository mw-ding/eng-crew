   at the same head, reuse it; a full `cmd=rereview` still runs both passes.
6. The `validate` pass, after writing its own section, reads the `review`
   file (missing: `blocked: #<n> review` and exit) and posts one COMMENT
   review `[<ReviewerBot>/verdict] round <k> @ <sha7>` (`<op:markers.write>`)
   with both sections and a final marker
   `<!-- crew:v1 role=reviewer-validator pass=verdict pr=<n> sha=<head-sha> base=<reviewed-base-sha> round=<k> verdict=<pass|changes> -->`;
   `pass` only if both sections pass. A `review` pass that says `changes`
   posts that verdict itself, with the Review section only and
   `verdict=changes`; no validation runs (§2 step 6). One identity: never a
   formal review. Changes at effective caps[0] (maximum 3) escalate per §5.
   Before posting, check the assembled verdict body has exactly three
   `pass=` markers: `pass=review`, `pass=validate` and `pass=verdict`; a
   review-only `changes` body has exactly two: `pass=review` and
   `pass=verdict`. Each marker must name this PR, full head SHA and round,
   and its actual result. If the check fails, fix the body before posting.
   Right after posting the verdict, the same pass sets the state tags (§4):
   on `pass`, `<op:state-tags.set-approved>`; on `changes`,
   `<op:state-tags.set-changes>`.
7. Append `done: #<n> <head-sha> <pass> <pass|changes>` (this pass's section
   result) to `$CREW_STATUS`, then exit.

Asks go in `blocked:` lines, never to the owner here. Never post plain PR
comments. Never start a line with the steering prefix.
