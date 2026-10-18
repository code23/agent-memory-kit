#!/usr/bin/env python3
"""Review batching: temporary files and mocked judges only; no live memory/model calls."""
import contextlib
import io
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_batched_judges import Env, m, stub, yaml


def parked(e, name, reason="deadlock", **kw):
    e.add(name, **kw)
    src = e.mem / "candidates" / (name + ".yaml")
    c, err = m.load_candidate(src)
    assert not err
    c["review"] = m.build_review_envelope(reason, "fixture", candidate=c)
    dest = e.mem / "review" / src.name
    dest.write_text(m.dump_candidate(c))
    src.unlink()
    return dest


def judges(verdict="reject"):
    fs = [stub(lambda _p, v=verdict: v) for _ in range(3)]
    m._JUDGE_FNS.update(dict(zip(("judge_a", "judge_b", "tiebreak"), fs)))
    return fs


def run(apply=True, limit=None):
    with contextlib.redirect_stdout(io.StringIO()):
        return m.cmd_retriage_review(SimpleNamespace(apply=apply, limit=limit))


def tree(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class ReviewBatching(unittest.TestCase):
    def test_chunked_rejections_use_batches_not_per_item_calls(self):
        with Env() as e:
            for i in range(5): parked(e, "item" + str(i))
            fs = judges()
            os.environ["MEMORY_JUDGE_BATCH"] = "2"
            rows = run()
            self.assertEqual([r["decision"] for r in rows], ["reject"] * 5)
            self.assertEqual([f.calls["batch"] for f in fs], [3, 3, 0])
            self.assertEqual([f.calls["single"] for f in fs], [0, 0, 0])
            self.assertEqual(len(e.lane("rejected")), 5)

    def test_sorted_limit_applies_before_batching_and_preserves_remainder(self):
        with Env() as e:
            for name in ("c", "a", "b"): parked(e, name)
            fs = judges()
            untouched = (e.mem / "review" / "c.yaml").read_bytes()
            rows = run(limit=2)
            self.assertEqual([r["id"] for r in rows], ["a", "b"])
            self.assertEqual([f.calls["batch"] for f in fs], [1, 1, 0])
            self.assertEqual(e.lane("review"), ["c"])
            self.assertEqual((e.mem / "review" / "c.yaml").read_bytes(), untouched)

    def test_dryrun_writes_nothing_and_still_batches(self):
        with Env() as e:
            parked(e, "a"); parked(e, "b")
            fs = judges("promote")
            before = tree(e.mem.parent)
            self.assertEqual([r["decision"] for r in run(apply=False)], ["promote", "promote"])
            self.assertEqual(before, tree(e.mem.parent))
            self.assertEqual([f.calls["batch"] for f in fs], [1, 1, 0])
            self.assertEqual([f.calls["single"] for f in fs], [0, 0, 0])

    def test_hard_stops_and_malformed_records_never_enter_batch(self):
        with Env() as e:
            for code in ("forbidden-pattern", "risk", "weak-excerpt"):
                parked(e, code, reason=code)
            parked(e, "unmapped", reason="unknown-scope", scope="project:unmapped")
            parked(e, "missing", source={"kind": "note", "path": str(e.mem / "gone"), "excerpt": e.excerpt})
            malformed = e.mem / "review" / "malformed.yaml"
            malformed.write_text("this: [invalid")
            fs = judges()
            before = malformed.read_bytes()
            rows = run()
            self.assertEqual({r["decision"] for r in rows}, {"park"})
            self.assertTrue(all(f.calls["batch"] == f.calls["single"] == 0 for f in fs))
            self.assertEqual(malformed.read_bytes(), before)

    def test_verified_source_hard_stop_can_reenter_batch(self):
        with Env() as e:
            parked(e, "restored", reason="source-missing")
            fs = judges()
            self.assertEqual(run()[0]["decision"], "reject")
            self.assertEqual([f.calls["batch"] for f in fs], [1, 1, 0])

    def _map_scope(self, e, scope, dest):
        reg = e.mem / "registry.yaml"
        d = m.yaml.safe_load(reg.read_text())
        slug = m.scope_to_slug(scope)
        d["aliases"][slug] = slug
        d["destinations"][slug] = dest
        reg.write_text(m.yaml.safe_dump(d, sort_keys=False))

    def test_historical_unknown_scope_batches_only_after_mapping_resolves(self):
        with Env() as e:
            sc = "project:newmap"
            parked(e, "old_unknown", reason="unknown-scope", scope=sc)
            fs = judges()
            row = run()[0]
            self.assertEqual((row["decision"], row["reason_code"]), ("park", "unknown-scope"))
            self.assertTrue(all(f.calls["batch"] == f.calls["single"] == 0 for f in fs))
            self._map_scope(e, sc, "03-resources/agent-systems/captured-org.md")
            self.assertEqual(run()[0]["decision"], "reject")
            self.assertEqual([f.calls["batch"] for f in fs], [1, 1, 0])

    def test_historical_unknown_scope_invalid_source_blocks_even_when_mapped(self):
        with Env() as e:
            sc = "project:newmap"
            p = parked(e, "bad", reason="unknown-scope", scope=sc)
            self._map_scope(e, sc, "03-resources/agent-systems/captured-org.md")
            c, _ = m.load_candidate(p)
            Path(c["source"]["path"]).write_text("Different evidence entirely.")
            fs = judges()
            row = run()[0]
            self.assertEqual((row["decision"], row["reason_code"]), ("park", "source-changed"))
            self.assertTrue(all(f.calls["batch"] == f.calls["single"] == 0 for f in fs))

    def test_historical_unknown_scope_unsafe_resolved_path_blocks(self):
        with Env() as e:
            sc = "project:newmap"
            parked(e, "unsafe", reason="unknown-scope", scope=sc)
            self._map_scope(e, sc, "../../escape.md")
            fs = judges()
            row = run()[0]
            self.assertEqual((row["decision"], row["reason_code"]), ("park", "unsafe-target-path"))
            self.assertTrue(all(f.calls["batch"] == f.calls["single"] == 0 for f in fs))

    def test_gates_only_resolved_unknown_scope_has_no_writes_or_judge_calls(self):
        with Env() as e:
            sc = "project:newmap"
            p = parked(e, "dry", reason="unknown-scope", scope=sc)
            self._map_scope(e, sc, "03-resources/agent-systems/captured-org.md")
            fs = judges()
            before = tree(e.mem.parent)
            row = m._retriage_one(p, False, gates_only=True)
            self.assertEqual(row["decision"], "needs-judge")
            self.assertEqual(before, tree(e.mem.parent))
            self.assertTrue(all(f.calls["batch"] == f.calls["single"] == 0 for f in fs))

    def test_historical_duplicate_rechecks_current_gates_before_batch(self):
        with Env() as e:
            parked(e, "old_duplicate", reason="duplicate")
            fs = judges()
            self.assertEqual(run()[0]["decision"], "reject")
            self.assertEqual([f.calls["batch"] for f in fs], [1, 1, 0])

    def test_current_duplicate_never_enters_batch(self):
        with Env() as e:
            p = parked(e, "still_duplicate", reason="duplicate")
            c, err = m.load_candidate(p)
            self.assertIsNone(err)
            _, target, _ = m.resolve_scope_target(c["scope"])
            m.safe_target_path(target).write_text("# Fixture\n- " + c["fact"] + "\n")
            fs = judges()
            row = run()[0]
            self.assertEqual((row["decision"], row["reason_code"]), ("park", "duplicate"))
            self.assertTrue(all(f.calls["batch"] == f.calls["single"] == 0 for f in fs))

    def test_historical_duplicate_cannot_bypass_changed_source(self):
        with Env() as e:
            p = parked(e, "bad_source", reason="duplicate")
            c, err = m.load_candidate(p)
            self.assertIsNone(err)
            Path(c["source"]["path"]).write_text("Different evidence entirely.")
            fs = judges()
            row = run()[0]
            self.assertEqual((row["decision"], row["reason_code"]), ("park", "source-changed"))
            self.assertTrue(all(f.calls["batch"] == f.calls["single"] == 0 for f in fs))

    def test_empty_and_zero_limit_do_not_call_judges(self):
        with Env() as e:
            fs = judges()
            self.assertEqual(run(), [])
            parked(e, "a")
            self.assertEqual(run(limit=0), [])
            self.assertTrue(all(f.calls["batch"] == f.calls["single"] == 0 for f in fs))

    def test_boundary_requires_tiebreak_even_when_primaries_promote(self):
        with Env() as e:
            parked(e, "boundary", type="boundary")
            fs = judges("promote")
            fs[2] = stub(lambda _p: "hold")
            m._JUDGE_FNS["tiebreak"] = fs[2]
            rows = run()
            self.assertEqual(rows[0]["decision"], "park")
            self.assertEqual([f.calls["batch"] for f in fs], [1, 1, 1])
            self.assertFalse(m.LEDGER.exists())

    def test_invalid_batch_item_uses_existing_single_fallback(self):
        with Env() as e:
            parked(e, "a"); parked(e, "b")
            fs = judges()
            fs[0].raw = lambda _p, _t: "[]"
            rows = run()
            self.assertEqual([r["decision"] for r in rows], ["reject", "reject"])
            self.assertEqual(fs[0].calls["single"], 2)
            self.assertEqual(fs[1].calls["single"], 0)

    def test_candidate_change_discards_cached_verdicts(self):
        with Env() as e:
            p = parked(e, "a")
            fs = judges("promote")
            original = m.batch_precompute
            def changed(*args, **kw):
                result = original(*args, **kw)
                c = yaml.safe_load(p.read_text())
                c["fact"] = "Changed durable workflow: backups run on Sunday."
                p.write_text(m.dump_candidate(c))
                return result
            with patch.object(m, "batch_precompute", changed):
                rows = run()
            self.assertEqual(rows[0]["decision"], "promote")
            self.assertEqual([f.calls["single"] for f in fs], [1, 1, 0])
            self.assertIn("Changed durable workflow", m.LEDGER.read_text())

    def test_source_change_after_batch_parks_without_fresh_judge_calls(self):
        with Env() as e:
            parked(e, "a")
            fs = judges("promote")
            original = m.batch_precompute
            def changed(*args, **kw):
                result = original(*args, **kw)
                e.src.write_text("Changed source with no original evidence.")
                return result
            with patch.object(m, "batch_precompute", changed): rows = run()
            self.assertEqual(rows[0]["decision"], "park")
            self.assertEqual([f.calls["single"] for f in fs], [0, 0, 0])
            self.assertFalse(m.LEDGER.exists())

    def test_target_change_after_batch_requires_fresh_judges(self):
        with Env() as e:
            parked(e, "a")
            fs = judges("promote")
            original = m.batch_precompute
            def changed(*args, **kw):
                result = original(*args, **kw)
                e.vault.joinpath("03-resources/ai-memory/captured-personal.md").write_text("# New target context")
                return result
            with patch.object(m, "batch_precompute", changed): rows = run()
            self.assertEqual(rows[0]["decision"], "promote")
            self.assertEqual([f.calls["single"] for f in fs], [1, 1, 0])

    def test_earlier_promotion_invalidates_later_target_context(self):
        with Env() as e:
            parked(e, "a"); parked(e, "b")
            fs = judges("promote")
            self.assertEqual([r["decision"] for r in run()], ["promote", "promote"])
            self.assertEqual([f.calls["single"] for f in fs], [1, 1, 0])

    def test_already_promoted_cleanup_does_not_judge_or_repeat_promotion(self):
        with Env() as e:
            p = parked(e, "a")
            raw, _ = m.load_candidate(p)
            # Ledger proof is controlled, vault-safe fixture setup.
            m.LEDGER.write_text(__import__("json").dumps({"candidate_sha256": m.candidate_sha256(raw)}) + "\n")
            fs = judges()
            before = m.LEDGER.read_bytes()
            rows = run()
            self.assertEqual(rows[0]["decision"], "done")
            self.assertEqual(m.LEDGER.read_bytes(), before)
            self.assertTrue(all(f.calls["batch"] == f.calls["single"] == 0 for f in fs))

    def test_envelope_hard_stop_added_after_batch_blocks_apply(self):
        with Env() as e:
            p = parked(e, "a")
            fs = judges("promote")
            original = m.batch_precompute
            def changed(*args, **kw):
                result = original(*args, **kw)
                c = yaml.safe_load(p.read_text())
                c["review"]["reason_code"] = "forbidden-pattern"
                p.write_text(m.dump_candidate(c))
                return result
            with patch.object(m, "batch_precompute", changed): rows = run()
            self.assertEqual(rows[0]["decision"], "park")
            self.assertEqual([f.calls["single"] for f in fs], [0, 0, 0])
            self.assertFalse(m.LEDGER.exists())


    def test_registry_change_after_batch_uses_new_destination_and_fresh_judges(self):
        with Env() as e:
            parked(e, "a")
            fs = judges("promote")
            old = e.vault / "03-resources/ai-memory/captured-personal.md"
            before = old.read_bytes()
            new = e.vault / "03-resources/ai-memory/captured-new.md"
            new.write_text("# Fresh destination")
            original = m.batch_precompute
            def changed(*args, **kw):
                result = original(*args, **kw)
                reg = yaml.safe_load((e.mem / "registry.yaml").read_text())
                reg["destinations"]["personal"] = "03-resources/ai-memory/captured-new.md"
                (e.mem / "registry.yaml").write_text(yaml.safe_dump(reg))
                return result
            with patch.object(m, "batch_precompute", changed): rows = run()
            self.assertEqual(rows[0]["decision"], "promote")
            self.assertEqual([f.calls["single"] for f in fs], [1, 1, 0])
            self.assertEqual(old.read_bytes(), before)
            self.assertIn("Fact a", new.read_text())

    def test_source_change_during_fresh_judging_blocks_mutation(self):
        with Env() as e:
            parked(e, "a")
            fs = judges("promote")
            batch = m.batch_precompute
            invoke = m.invoke_judge
            def changed_batch(*args, **kw):
                result = batch(*args, **kw)
                (e.vault / "03-resources/ai-memory/captured-personal.md").write_text("# Changed context")
                return result
            def changed_single(name, prompt, *args, **kw):
                result = invoke(name, prompt, *args, **kw)
                if name == "judge_a": e.src.write_text("Evidence changed while judging.")
                return result
            with patch.object(m, "batch_precompute", changed_batch), patch.object(m, "invoke_judge", changed_single):
                rows = run()
            self.assertEqual(rows[0]["decision"], "park")
            self.assertTrue((e.mem / "review" / "a.yaml").exists())
            self.assertFalse(m.LEDGER.exists())

    def test_identical_fact_promoted_once_within_same_batch(self):
        with Env() as e:
            for name in ("a", "b"): parked(e, name, fact="The weekly backup runs on Sundays.")
            fs = judges("promote")
            rows = run()
            self.assertEqual([r["decision"] for r in rows], ["promote", "done"])
            self.assertEqual(len(m.LEDGER.read_text().splitlines()), 1)
            self.assertEqual([f.calls["single"] for f in fs], [0, 0, 0])


    def test_newly_eligible_item_source_changes_during_single_judging_stays_parked(self):
        with Env() as e:
            late_source = e.mem.parent / "restored-source.md"
            parked(e, "a", reason="source-missing", source={
                "kind": "note", "path": str(late_source), "excerpt": e.excerpt,
            })
            parked(e, "b")
            judges("promote")
            batch = m.batch_precompute
            invoke = m.invoke_judge
            def restore_after_batch(*args, **kw):
                result = batch(*args, **kw)
                late_source.write_text(e.excerpt)
                return result
            def change_during_single(name, prompt, *args, **kw):
                result = invoke(name, prompt, *args, **kw)
                if name == "judge_a" and "Fact a:" in prompt:
                    late_source.write_text("The restored evidence changed during judging.")
                return result
            with patch.object(m, "batch_precompute", restore_after_batch), patch.object(m, "invoke_judge", change_during_single):
                rows = run()
            a = next(r for r in rows if r["id"] == "a")
            self.assertEqual(a["decision"], "park")
            self.assertTrue((e.mem / "review" / "a.yaml").exists())
            if m.LEDGER.exists(): self.assertNotIn("Fact a:", m.LEDGER.read_text())

    def test_boundary_unanimous_rejection_rejects_with_recovery(self):
        with Env() as e:
            parked(e, "bnd", type="boundary")
            fs = judges("reject")
            note = e.vault / "03-resources" / "ai-memory" / "captured-personal.md"
            before = note.read_bytes()
            rows = run()
            self.assertEqual((rows[0]["decision"], rows[0]["reason_code"]), ("reject", "judges-rejected"))
            self.assertEqual([f.calls["batch"] for f in fs], [1, 1, 1])
            self.assertEqual(e.lane("rejected"), ["bnd"])
            self.assertEqual(e.lane("review"), [])
            self.assertEqual(note.read_bytes(), before)
            feed = b"".join(v for k, v in tree(e.mem).items() if "rejected/" not in k).decode()
            self.assertIn("judges_rejected", feed)
            self.assertIn("memory unreject bnd", feed)

    def test_boundary_split_or_hold_still_parks(self):
        for vs in (("reject", "reject", "promote"), ("promote", "promote", "reject"), ("reject", "reject", "hold")):
            with Env() as e:
                parked(e, "bnd", type="boundary")
                for n, v in zip(("judge_a", "judge_b", "tiebreak"), vs):
                    m._JUDGE_FNS[n] = stub(lambda _p, v=v: v)
                self.assertEqual(run()[0]["decision"], "park", vs)
                self.assertEqual(e.lane("review"), ["bnd"])

    def test_boundary_unanimous_promote_keeps_notify(self):
        with Env() as e:
            parked(e, "bnd", type="boundary")
            judges("promote")
            row = run()[0]
            self.assertEqual(row["decision"], "promote")
            self.assertIn("boundary_promoted", str(tree(e.mem)))

    def test_boundary_unsafe_source_rejection_never_reaches_judges(self):
        with Env() as e:
            p = parked(e, "bnd", reason="duplicate", type="boundary")
            c, _ = m.load_candidate(p)
            Path(c["source"]["path"]).write_text("Different evidence entirely.")
            fs = judges("reject")
            self.assertEqual(run()[0]["decision"], "park")
            self.assertTrue(all(f.calls["batch"] == f.calls["single"] == 0 for f in fs))
            self.assertEqual(e.lane("rejected"), [])


if __name__ == "__main__": unittest.main()
