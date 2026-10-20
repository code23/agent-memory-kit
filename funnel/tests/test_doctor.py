#!/usr/bin/env python3
"""Tests for `memory.py doctor`: fixture folders, the offline stub, no real models."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FUNNEL = Path(__file__).resolve().parent.parent
KIT = FUNNEL.parent
STUB = f"{sys.executable} {KIT / 'examples' / 'judge_stub.py'}"
ADAPTER = f"{sys.executable} {FUNNEL / 'judges' / 'judge.py'}"


class Doctor(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="memory-doctor-test-")
        self.root = Path(self.td) / "state"
        self.vault = Path(self.td) / "vault"

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def ready_folders(self):
        (self.root / "candidates").mkdir(parents=True)
        shutil.copy2(FUNNEL / "policy.example.yaml", self.root / "policy.yaml")
        shutil.copy2(FUNNEL / "registry.example.yaml", self.root / "registry.yaml")
        self.vault.mkdir()
        subprocess.run(["git", "-C", str(self.vault), "init", "-q"], check=True)

    def doctor(self, extra_env=None, *args):
        env = {k: v for k, v in os.environ.items()
               if not (k.startswith("MEMORY_") or k.endswith("_API_KEY")
                       or k in ("VAULT_ROOT", "STAGING_ROOT"))}
        env.update({"MEMORY_ROOT": str(self.root), "VAULT_ROOT": str(self.vault)})
        env.update(extra_env or {})
        return subprocess.run([sys.executable, str(FUNNEL / "memory.py"), "doctor", *args],
                              env=env, capture_output=True, text=True, timeout=60)

    def test_empty_setup_lists_what_is_missing(self):
        self.root.mkdir()
        r = self.doctor()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("Judge A has no model (MEMORY_JUDGE_A_CMD is not set)", r.stdout)
        self.assertIn("No registry.yaml", r.stdout)
        self.assertIn("Trusted vault not found", r.stdout)
        self.assertIn("thing(s) to fix", r.stdout)

    def test_ready_with_stub_seats(self):
        self.ready_folders()
        r = self.doctor({"MEMORY_JUDGE_A_CMD": STUB, "MEMORY_JUDGE_B_CMD": STUB + " ",
                         "MEMORY_TIEBREAK_CMD": STUB + "  ", "MEMORY_GIT_COMMIT": "1"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("uses the offline stub", r.stdout)
        self.assertIn("Ready.", r.stdout)

    def test_missing_provider_key_is_named_not_shown(self):
        self.ready_folders()
        seat = f"{ADAPTER} --provider anthropic --model m"
        r = self.doctor({"MEMORY_JUDGE_A_CMD": seat,
                         "MEMORY_JUDGE_B_CMD": STUB, "MEMORY_TIEBREAK_CMD": STUB + " "})
        self.assertEqual(r.returncode, 1)
        self.assertIn("Judge A uses anthropic but ANTHROPIC_API_KEY is not set", r.stdout)

    def test_same_provider_twice_is_flagged(self):
        self.ready_folders()
        a = f"{ADAPTER} --provider openai --model m1"
        b = f"{ADAPTER} --provider openai --model m2"
        r = self.doctor({"MEMORY_JUDGE_A_CMD": a, "MEMORY_JUDGE_B_CMD": b,
                         "MEMORY_TIEBREAK_CMD": STUB, "OPENAI_API_KEY": "sk-test-not-real"})
        self.assertIn("Two seats use the same provider", r.stdout)
        self.assertNotIn("sk-test-not-real", r.stdout + r.stderr)

    def test_stub_next_to_a_real_model_fails(self):
        self.ready_folders()
        real = f"{ADAPTER} --exec 'some-model-cli -p'"
        r = self.doctor({"MEMORY_JUDGE_A_CMD": real, "MEMORY_JUDGE_B_CMD": STUB,
                         "MEMORY_TIEBREAK_CMD": STUB + " "})
        self.assertEqual(r.returncode, 1)
        self.assertIn("The offline stub is in Judge B, Tiebreak next to real models", r.stdout)
        self.assertIn("Judge A: CLI: some-model-cli -p", r.stdout)

    def test_ping_uses_each_seat(self):
        self.ready_folders()
        r = self.doctor({"MEMORY_JUDGE_A_CMD": STUB, "MEMORY_JUDGE_B_CMD": STUB + " ",
                         "MEMORY_TIEBREAK_CMD": STUB + "  "}, "--ping")
        for seat in ("Judge A", "Judge B", "Tiebreak"):
            self.assertIn(f"{seat} answered the test prompt", r.stdout)

    def test_ping_flags_chatty_output(self):
        self.ready_folders()
        chatty = f'{sys.executable} -c "import sys; sys.stdin.read(); print(\'Sure! I think hold.\')"'
        r = self.doctor({"MEMORY_JUDGE_A_CMD": chatty, "MEMORY_JUDGE_B_CMD": STUB,
                         "MEMORY_TIEBREAK_CMD": STUB + " "}, "--ping")
        self.assertIn("Judge A answered, but not with clean JSON", r.stdout)
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
