Secret retrieval: never suggest a command that prints a secret value
(`printenv API_KEY`, `cat .env`); `!`-run output enters the transcript, so
say so. Give a clipboard pipe (`| pbcopy`, `| xclip -selection clipboard`)
or the revealing UI; verify by fingerprint, length or last 4, never the value.
