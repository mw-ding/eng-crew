# Evidence adapter: web screenshot

Shape: Web. Protocol: [verification](../../docs/verification.md).

## Builder: capture and embed

1. Run the app at the change head. Name the SHA, route and viewport (for
   example 1280x800). Use test data without accounts, emails or tokens.
2. Capture a PNG locally with an available screenshot tool:

   ```sh
   mkdir -p .crew/captures
   <screenshot-tool> --url <url> --viewport 1280x800 \
     --out .crew/captures/view.png
   ```

3. At creation put `![route, viewport, SHA](.crew/captures/view.png)` in the
   body file and pass `--attach .crew/captures/view.png` to `gh pr create`.
   This needs `gh` 2.99.0 or later on GitHub.com / Enterprise Cloud, with
   write access. It produces a durable GitHub user-attachments image URL.
   State what to look at beside the image; no sidecar or evidence commit.
4. Keep the image untracked; apply the 10 MB image and 60,000-character body
   limits. Repo-file links, evidence branches, data URIs and other hosts do
   not count. Do not edit the body or post a plain comment to upload media.
5. Later signed reviews cannot upload with `gh pr review`. Use the
   [Q1 fallback](../../docs/verification.md#q1-how-bots-attach-images-and-video):
   state what the image would show, route, viewport, SHA and exact capture
   command. The validator reproduces and records its observation inline;
   otherwise mark `unverified`, requiring per-change merge-ok. The same
   fallback applies on older CLIs / Enterprise Server. Late evidence at the
   same head needs the coordinator's rereview steer.

## Verifier: check and reproduce

1. Open the embedded attachment and check route, viewport, SHA, claimed change
   and absence of private data; for the fallback, read the capture recipe.
2. Run the app at head, open the same route/viewport and compare by eye. A
   pixel diff is optional; fonts and data may vary.
3. Record your observation inline: `agrees` only if the attachment or fallback
   reproduction shows the claim at head; `disagrees` for mismatches or missing
   proof; `unverified` if reproduction cannot run (say why). Earlier captures
   count only if they still apply at head.
