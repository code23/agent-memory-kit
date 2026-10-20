#!/usr/bin/env python3
"""Exercise the daily cron wrapper with a fixture CLI; no live queues or models."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parent.parent


class CronTests(unittest.TestCase):
    def run_cron(self, *, candidates=False, triage_rc=0, weekly_rc=0, private_root=False):
        with tempfile.TemporaryDirectory(prefix="memory-cron-test-") as td:
            root = Path(td)
            (root / "bin").mkdir()
            state = root / "private-state" if private_root else root
            (state / "candidates").mkdir(parents=True)
            if candidates:
                (state / "candidates" / "fixture.yaml").write_text("fact: fixture\n")
            shutil.copy2(REPO / "bin" / "triage-cron", root / "bin" / "triage-cron")
            cli = root / "bin" / "memory"
            cli.write_text(
                f"#!{sys.executable}\n"
                "import os,sys\n"
                "from pathlib import Path\n"
                "root=Path(__file__).resolve().parent.parent\n"
                "with (root/'calls').open('a') as f: f.write(' '.join(sys.argv[1:])+'\\n')\n"
                "rc={'run':os.environ['TEST_TRIAGE_RC'], 'deadlocks-weekly':os.environ['TEST_WEEKLY_RC']}\n"
                "sys.exit(int(rc.get(sys.argv[1], 0)))\n"
            )
            cli.chmod(0o700)
            env = {k: v for k, v in os.environ.items() if k != "MEMORY_ROOT"}
            env.update({"TEST_TRIAGE_RC": str(triage_rc), "TEST_WEEKLY_RC": str(weekly_rc)})
            if private_root:
                env["MEMORY_ROOT"] = str(state)
            result = subprocess.run(["bash", str(root / "bin" / "triage-cron")],
                                    env=env, capture_output=True, text=True, timeout=10)
            return result, (root / "calls").read_text().splitlines(), (state / "ledger" / "triage-cron.log").read_text()

    def test_empty_queue_still_checks_weekly_work(self):
        result, calls, _ = self.run_cron()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["maintain", "deadlocks-weekly --apply"])

    def test_candidates_then_weekly_work(self):
        result, calls, log = self.run_cron(candidates=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["run --apply", "router-rebuild-if-dirty", "deadlocks-weekly --apply"])
        self.assertIn("done (exit 0)", log)

    def test_private_memory_root_candidates_are_triaged(self):
        result, calls, log = self.run_cron(candidates=True, private_root=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["run --apply", "router-rebuild-if-dirty", "deadlocks-weekly --apply"])
        self.assertIn("triaging 1 candidate(s)", log)

    def test_empty_queue_reports_weekly_failure(self):
        result, _, log = self.run_cron(weekly_rc=7)
        self.assertEqual(result.returncode, 7)
        self.assertIn("weekly deadlocks failed (exit 7)", log)

    def test_populated_queue_reports_weekly_failure(self):
        result, _, log = self.run_cron(candidates=True, weekly_rc=7)
        self.assertEqual(result.returncode, 7)
        self.assertIn("done (exit 0)", log)
        self.assertIn("weekly deadlocks failed (exit 7)", log)

    def test_triage_failure_is_preserved(self):
        result, calls, log = self.run_cron(candidates=True, triage_rc=4, weekly_rc=7)
        self.assertEqual(result.returncode, 4)
        self.assertEqual(calls[-1], "deadlocks-weekly --apply")
        self.assertIn("done (exit 4)", log)


if __name__ == "__main__":
    unittest.main()
