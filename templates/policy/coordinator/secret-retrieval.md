Secret retrieval: never suggest a command that prints a secret value
(`printenv API_KEY`, `echo $API_KEY`, `cat .env`, `gh auth token`). Output of
a command the owner runs through the harness shell passthrough (such as `!`)
enters the transcript, logs and any synced history; say so when you suggest
one. Give a clipboard form (`… | pbcopy` on macOS, `… | xclip -selection
clipboard` on Linux) or the UI that reveals it, such as the hosting
dashboard. Verify by a non-secret fingerprint, length or last 4 characters
(`printenv API_KEY | shasum -a 256 | cut -c1-12`), never the value.
