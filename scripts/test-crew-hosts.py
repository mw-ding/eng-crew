"""Inventory command coverage: the shared fake SSH scenarios live in test-crew-host.py and run in CI."""
import importlib.util
import os
import sys
import unittest

spec = importlib.util.spec_from_file_location("host_tests", os.path.join(os.path.dirname(__file__), "test-crew-host.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Hosts(mod.Host):
    def test_empty_inventory(self):
        self.write_profile()
        r = self.crew("hosts")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.splitlines()), 1)
        self.assertFalse(os.path.exists(self.ssh_log))


if __name__ == "__main__":
    result = unittest.TextTestRunner().run(unittest.TestSuite(Hosts(name) for name in
                                           ("test_empty_inventory", "test_inventory_remote_facts_and_unknown_load")))
    sys.exit(not result.wasSuccessful())
