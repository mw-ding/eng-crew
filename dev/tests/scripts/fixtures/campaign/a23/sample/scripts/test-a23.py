"""A23 sample test: red when RED is True at the head under test."""
import sys

RED = False
print("test-a23 FAILED: red at head" if RED else "test-a23 ok")
sys.exit(1 if RED else 0)
