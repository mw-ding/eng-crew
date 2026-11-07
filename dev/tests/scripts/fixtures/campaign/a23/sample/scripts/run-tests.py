"""A23 sample run-tests: runs each named test file; exit 1 if any fails."""
import os
import subprocess
import sys

if os.environ.get("A23_LOCAL_LOG"):
    open(os.environ["A23_LOCAL_LOG"], "a").write("run-tests.py " + " ".join(sys.argv[1:]) + "\n")
codes = [subprocess.run([sys.executable, t]).returncode for t in sys.argv[1:]]
print("ran %d, failed %d" % (len(codes), sum(map(bool, codes))))
sys.exit(1 if any(codes) else 0)
