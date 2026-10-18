#!/usr/bin/env python3
"""Quote-aware judgment-marker exception: temp sources/registry/vault, no models, no live data."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_batched_judges import Env, m
from test_retriage_batches import judges, parked, run, tree

GOOD = ('On Northwind, "the tests pass and I think it\'s done" NEVER closes a ticket; '
        "the author's own opinion is not evidence.")


def gate(e, name, fact, reason="judgment-marker", **kw):
    kw.setdefault("type", "boundary")
    p = parked(e, name, reason=reason, fact=fact, **kw)
    fs = judges()
    before = tree(e.mem.parent)
    row = m._retriage_one(p, False, gates_only=True)
    assert before == tree(e.mem.parent), "gates-only wrote"
    assert all(f.calls["batch"] == f.calls["single"] == 0 for f in fs)
    return row


class QuotedJudgment(unittest.TestCase):
    def test_source_backed_boundary_passes_gates_only(self):
        with Env() as e:
            self.assertEqual(gate(e, "ok", GOOD)["decision"], "needs-judge")

    def test_historical_marker_revalidates_but_run_still_uses_judges(self):
        with Env() as e:
            parked(e, "ok", reason="judgment-marker", fact=GOOD, type="boundary")
            fs = judges()
            self.assertEqual(run()[0]["decision"], "reject")
            self.assertEqual([f.calls["batch"] for f in fs], [1, 1, 1])

    def blocked(self, fact, **kw):
        with Env() as e:
            row = gate(e, "bad", fact, **kw)
            self.assertEqual((row["decision"], row["reason_code"]), ("park", "judgment-marker"), fact)

    def test_blocked_variants(self):
        self.blocked("On Northwind I think the ticket is closed.")
        self.blocked('On Northwind, "the tests pass" and I think it is done.')
        self.blocked('On Northwind, "I think it is done" closes a ticket.')  # unsupported quote
        self.blocked('On Northwind, "I think it is done" NEVER closes a ticket; probably opinion is not evidence.')
        self.blocked('On Northwind, "I think it\'s done NEVER closes a ticket; opinion is not evidence.')  # unclosed
        self.blocked('On Northwind, "I think it\'s done" NEVER closes a ticket; opinion is not evidence "x.')
        self.blocked("On Northwind, “I think it's done” NEVER closes a ticket; opinion is not evidence.")
        # demonstrated defect: established-conclusion quote accepted as fact, unrelated not-evidence clause
        self.blocked('The established conclusion "I think it is done" is accepted as fact; unrelated old logs are not evidence.')
        # generic never (not "NEVER closes a ticket") plus unrelated not-evidence clause
        self.blocked('On Northwind, "I think it is done" NEVER fails validation; the author\'s own opinion is not evidence.')
        self.blocked('On Northwind, "I think it is done" is quoted; NEVER closes a ticket; the author\'s own opinion is not evidence.')
        self.blocked('On Northwind, "I think it is done" NEVER closes a ticket; unrelated old logs are not evidence.')
        self.blocked('On Northwind, "I think" and "it is done" NEVER closes a ticket; the author\'s own opinion is not evidence.')
        self.blocked('"I think so" is fine, but I think it is not evidence.')
        self.blocked(GOOD, type="workflow")  # not boundary: wrongtype guard unchanged

    def test_non_low_risk_gets_no_exception(self):
        with Env() as e:  # marker gate runs before the risk gate, as before; either way it parks
            row = gate(e, "r", GOOD, risk="medium")
            self.assertEqual((row["decision"], row["reason_code"]), ("park", "judgment-marker"))
        with Env() as e:
            row = gate(e, "r2", "Backups run on Sunday.", risk="medium")
            self.assertEqual((row["decision"], row["reason_code"]), ("park", "risk"))

    def test_wrongtype_unchanged(self):
        with Env() as e:
            row = gate(e, "t", GOOD, type="nonsense")
            self.assertEqual((row["decision"], row["reason_code"]), ("park", "disallowed-type"))

    def test_changed_missing_secret_sources_cannot_judge(self):
        with Env() as e:
            p = parked(e, "chg", reason="judgment-marker", fact=GOOD, type="boundary")
            judges(); e.src.write_text("# s\n\nDifferent text now.\n")
            self.assertEqual(m._retriage_one(p, False, gates_only=True)["reason_code"], "source-changed")
        with Env() as e:
            p = parked(e, "miss", reason="judgment-marker", fact=GOOD, type="boundary")
            judges(); e.src.unlink()
            self.assertEqual(m._retriage_one(p, False, gates_only=True)["reason_code"], "source-missing")
        with Env() as e:
            ex = "Contact test@example.com about the weekly backup job runs."
            e.src.write_text("# s\n\n" + ex + "\n")
            p = parked(e, "sec", reason="judgment-marker", fact=GOOD, type="boundary",
                       source={"kind": "note", "path": str(e.src), "excerpt": ex})
            judges()
            self.assertEqual(m._retriage_one(p, False, gates_only=True)["reason_code"], "forbidden-pattern")

    def test_dry_run_keeps_bytes_and_parked_age(self):
        with Env() as e:
            p = parked(e, "ok", reason="judgment-marker", fact=GOOD, type="boundary")
            judges(); b = p.read_bytes()
            run(apply=False)
            self.assertEqual(b, p.read_bytes())
            self.assertIn("parked_at", b.decode())


if __name__ == "__main__":
    unittest.main()
