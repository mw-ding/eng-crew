"""A23 sample check-repo: prints where it ran and any forge, crew or agent variable it can see."""
import os
import re
import sys

seen = sorted(k for k in os.environ if re.match(r"(GH_|GITHUB_|CREW_|CAMPAIGN_|SSH_AUTH_SOCK)", k))
if os.environ.get("A23_LOCAL_LOG"):
    open(os.environ["A23_LOCAL_LOG"], "a").write("check-repo.py\n")
print("sample check-repo ok in " + os.getcwd())
print("env: " + (" ".join(seen) or "clean"))
sys.exit(0)
