#!/usr/bin/env python3
"""duplicate_gate exact-fact equality. Synthetic temporary vault only.
Run: python3 tests/test_exact_duplicate_gate.py
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import memory as m

FACT = "Northwind renews its hosting contract every March with a fourteen day notice period"
DUP = ("discard", "duplicate", "duplicate (fact already in target note)")


class Gate(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.vault = Path(self.td.name) / "vault"
        self.vault.mkdir()
        (self.vault / "notes").mkdir()
        self.addCleanup(self.td.cleanup)

    def note(self, body, name="notes/a.md"):
        (self.vault / name).write_text(body)
        return name

    def gate(self, target, fact=FACT):
        return m.duplicate_gate(fact, target, vault=self.vault)

    def test_six_word_collision_is_not_duplicate(self):
        six = " ".join(FACT.split()[:6])
        t = self.note(f"# Northwind\n- {six} in a different way entirely\n{six}, and other things\n")
        self.assertIsNone(self.gate(t))

    def test_exact_plain_and_bullet(self):
        self.assertEqual(self.gate(self.note(f"# H\n{FACT}\n")), DUP)
        self.assertEqual(self.gate(self.note(f"# H\n- {FACT}\n")), DUP)
        self.assertEqual(self.gate(self.note(f"# H\n  * {FACT}  \n")), DUP)

    def test_case_and_whitespace(self):
        t = self.note("- NORTHWIND  renews its hosting\tcontract every march with a   fourteen day notice PERIOD\n")
        self.assertEqual(self.gate(t), DUP)
        self.assertEqual(self.gate(t, fact="  " + FACT.lower() + "\n"), DUP)

    def test_provenance_suffixes(self):
        for label in ("auto-promoted", "human-approved"):
            b = m.render_promote_bullet({"fact": FACT}, {"kind": "chat", "path": "/x/y (1).md"},
                                        "L123", {"human": 1} if label[0] == "h" else {})
            self.assertIn(label, b)
            self.assertEqual(self.gate(self.note(b + "\n")), DUP)

    def test_suffix_like_text_in_fact_not_chopped(self):
        longer = FACT + " _(auto-promoted 2026-10-05, source: chat p, ledger:1)_ and more"
        self.assertIsNone(self.gate(self.note(f"- {longer}\n")))
        # fact that itself ends in suffix-like text only matches the full line
        self.assertIsNone(self.gate(self.note(f"- {FACT}\n"), fact=longer))

    def test_longer_fact_prefix_substring_header_cross_entry(self):
        for body in (f"- {FACT} and also something more\n",
                     f"- Note that {FACT}\n",
                     f"# {FACT}\n",
                     f"- {' '.join(FACT.split()[:7])}\n- {' '.join(FACT.split()[7:])}\n",
                     f"{FACT.split(' every')[0]}\n"):
            self.assertIsNone(self.gate(self.note(body)), body)

    def test_literal_suffix_with_real_annotation_preserves_whole_fact(self):
        longer = FACT + " _(auto-promoted 2026-10-05, source: chat p, ledger:1)_ and more"
        bullet = m.render_promote_bullet({"fact": longer},
                                       {"kind": "chat", "path": "/synthetic.md"},
                                       "1234abcd", {})
        target = self.note(bullet + "\n")
        self.assertIsNone(self.gate(target))
        self.assertEqual(self.gate(target, fact=longer), DUP)

    def test_distinct_and_missing_target(self):
        self.note(f"- {FACT}\n", "notes/a.md")
        other = self.note("- something else\n", "notes/b.md")
        self.assertIsNone(self.gate(other))
        self.assertIsNone(self.gate("notes/missing.md"))

    def test_unsafe_target(self):
        (self.vault.parent / "outside.md").write_text(f"- {FACT}\n")
        for t in ("../outside.md", "/etc/hosts", "~/x.md", "notes/a.txt", None):
            self.assertIsNone(self.gate(t), t)

    def test_empty_fact(self):
        t = self.note("\n- \n")
        self.assertIsNone(self.gate(t, fact=""))
        self.assertIsNone(self.gate(t, fact=None))


if __name__ == "__main__":
    unittest.main()
