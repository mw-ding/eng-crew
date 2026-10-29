# Evidence adapter: web screenshot

Shape: Web. Protocol: [verification](../../docs/verification.md).

## Builder: capture

1. Run the app from the PR head commit. Note the commit's short SHA.
2. Open the changed view at a stated viewport (for example 1280x800). Use test
   data only: no real accounts, emails or tokens in the frame.
3. Capture a full-page PNG, or a crop when the change is a small part of the
   page. Any tool is fine, for example a headless browser:

   ```sh
   mkdir -p evidence/<pr>
   <screenshot-tool> --url <url> --viewport 1280x800 \
     --out evidence/<pr>/<name>.png
   ```

4. Add a short sidecar `evidence/<pr>/<name>.md` with the URL or route, the
   viewport, the head short SHA and one line saying what to look at.
5. Commit both files **on the PR branch** and push. The head moves; CI
   re-runs. Never put the image on a side branch.
6. Name the shape and the path: in the PR body `## Acceptance Evidence` if the
   body is still being written, otherwise in the fix-round note (the body is
   not edited after it is posted): `shape: web, evidence/<pr>/<name>.png`. To embed the image in the body, use
   a relative path or a link to the file at the head commit, not a branch link.

## Verifier: check and reproduce

1. Open the PNG from the head commit, with the sidecar next to it.
2. Check that it shows the claimed change, is of the named route and viewport,
   and has no private data.
3. Reproduce: run the app at head, open the same route and viewport, and
   compare by eye (a pixel diff is optional; fonts and data may vary).
4. Record in the validation section: `agrees` if the image matches the claim and
   the reproduction, `disagrees` if the image does not show the change or the
   reproduction differs, `unverified` if the app cannot run in the validator's
   environment (say why).
