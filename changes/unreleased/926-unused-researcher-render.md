---
type: fixed
issue: 926
pr: 1038
date: 2026-11-05
box-skill: none (the GitHub render is byte-identical)
---

A pack that does not run the researcher, or whose markers backend declares
`markers.write-item` unsupported, no longer fails the render on the
researcher brief or needs a copied template overlay. `runtime.options.researchers`
now accepts `0` to run no researcher: the render skips the researcher's
registry templates and so needs none of its operations, and `resolve` refuses
`researchers = 0` with `triage.enabled = true`. A new `<op:a.b|c.d>` operation
placeholder renders the first listed operation the backend supports; the
researcher brief records its finding with `markers.write-item`, else
`tracker.comment`. Profiles that run the researcher on a backend with
`write-item`, including the tmux and Grok Bot profiles, validate, resolve and
render as before.
