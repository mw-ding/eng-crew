"""Compatibility shim: this file moved to environments/terminal/crew.d/feedback.py (#1222). The old path is kept for one release.

Usage: as for environments/terminal/crew.d/feedback.py, which this runs.
"""
import os

__file__ = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../environments/terminal/crew.d/feedback.py"))
with open(__file__, encoding="utf-8") as _shim:
    exec(compile(_shim.read(), __file__, "exec"))
