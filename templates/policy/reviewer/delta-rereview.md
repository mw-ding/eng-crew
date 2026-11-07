Delta re-review (protocol §7): on a builder fix for a conflicting or
content-different base update, read the signed fix note's verified base/head
and updated base/head pairs. Review only the patch hunks that differ between
those pairs, with surrounding context and dependency checks as needed.
Independent validation reruns affected acceptance checks at the new head.
Post a normal head-pinned verdict under the normal round cap; if the delta
cannot be bounded or affects wider behavior, do full review and validation.
Record the full reviewed merge-base SHA in the Review and final verdict
markers' `base=` field, pinned at review start. Validation and the final
verdict reuse the Review marker's base. Never reject or re-review
solely because a change is behind: identical clean updates go to the
synthesizer's portability check with no new reviewer session.
