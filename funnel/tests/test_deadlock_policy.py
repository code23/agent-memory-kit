#!/usr/bin/env python3
"""Weekly deadlock policy. All lanes, sources, vault and archive are temporary;
all judges mocked. Run: python3 tests/test_deadlock_policy.py
"""
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_batched_judges import Env as BatchEnv, stub, m, yaml

class Env(BatchEnv):
    def __enter__(self):
        result = super().__enter__()
        self.capacity_patch = patch.object(m, '_weekly_capacity', return_value=59)
        self.capacity_patch.start()
        return result

    def __exit__(self, *args):
        self.capacity_patch.stop()
        return super().__exit__(*args)


NOW = dt.datetime(2026, 10, 2, 17, 0, tzinfo=dt.timezone.utc)


def park(e, name, age=7, **fields):
    e.add(name, **fields)
    src = e.mem / 'candidates' / (name + '.yaml')
    c, err = m.load_candidate(src)
    c['review'] = m.build_review_envelope('deadlock', 'no majority', candidate=c,
                                         parked_at=(NOW - dt.timedelta(days=age)).isoformat())
    dest = e.mem / 'review' / src.name
    dest.write_text(m.dump_candidate(c)); src.unlink()
    return dest


def judges(a='hold', b='hold', t='hold'):
    fns = [stub(lambda _i, v=v: v) for v in (a, b, t)]
    m._JUDGE_FNS.update(dict(zip(('judge_a', 'judge_b', 'tiebreak'), fns)))
    return fns


def run(e, apply=True, now=NOW):
    root = e.mem.parent / 'archive'
    root.mkdir(exist_ok=True)
    return m.cmd_deadlocks_weekly(SimpleNamespace(apply=apply), now=now, archive_root=root)


def tree(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


class DeadlockPolicy(unittest.TestCase):
    def test_dst_clocks_in_isolated_process(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), '_dst_clock_suite'],
            env={**os.environ, 'TZ': 'Europe/London'},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_exact_seven_days_batch_and_preserved_clock(self):
        with Env() as e:
            old = park(e, 'due', 7); park(e, 'young', 6.99999)
            first = yaml.safe_load(old.read_text())['review']['parked_at']
            fns = judges()
            rows = run(e)
            self.assertEqual([r['id'] for r in rows], ['due'])
            self.assertEqual([f.calls['batch'] for f in fns], [1, 1, 1])
            self.assertEqual([f.calls['single'] for f in fns], [0, 0, 0])
            env = yaml.safe_load(old.read_text())['review']
            self.assertEqual(env['parked_at'], first)
            self.assertEqual(env['deadlock_attempted_at'], NOW.isoformat())
            before = tree(e.mem.parent)
            self.assertEqual(run(e, now=NOW+dt.timedelta(days=6, hours=23)), [])
            self.assertEqual(tree(e.mem.parent), before)

    def test_exact_thirty_days_verified_archive_and_idempotency(self):
        with Env() as e:
            p = park(e, 'old', 30); park(e, 'notyet', 29.9999)
            judges(); rows = run(e)
            self.assertEqual([r['decision'] for r in rows], ['park', 'expire'])
            self.assertFalse(p.exists())
            archive = e.mem.parent / 'archive'
            manifest = json.loads(next(archive.glob('*.manifest.json')).read_text())
            blob = archive / manifest['archive']
            self.assertEqual(hashlib.sha256(blob.read_bytes()).hexdigest(), manifest['sha256'])
            self.assertEqual(manifest['bytes'], len(blob.read_bytes()))
            self.assertEqual(yaml.safe_load(blob.read_text())['fact'], 'Fact old: backups run on Sunday.')
            report = next((e.mem / 'ledger').glob('weekly-memory-report-*.md')).read_text()
            self.assertEqual(len(report.splitlines()), 1)
            self.assertNotIn('Fact old', report)
            before = tree(e.mem.parent); self.assertEqual(run(e), [])
            self.assertEqual(before, tree(e.mem.parent))

    def test_normal_consensus_promotes_and_rejects(self):
        for verdict, lane in [('promote', 'done'), ('reject', 'rejected')]:
            with Env() as e:
                park(e, 'item', 30); judges(verdict, verdict)
                self.assertEqual(run(e)[0]['decision'], verdict)
                self.assertEqual(e.lane(lane), ['item'])
                self.assertEqual(list((e.mem.parent / 'archive').iterdir()), [])

    def test_invalid_judge_never_expires_and_retry_is_suppressed(self):
        with Env() as e:
            p = park(e, 'old', 60); fns = judges('invalid', 'hold', 'hold')
            first = yaml.safe_load(p.read_text())['review']['parked_at']
            with self.assertRaises(RuntimeError): run(e)
            self.assertTrue(p.exists())
            self.assertEqual(yaml.safe_load(p.read_text())['review']['parked_at'], first)
            state = json.loads((e.mem / 'ledger' / 'deadlocks-weekly-state.json').read_text())
            self.assertNotIn('last_successful_at', state)
            calls = [(f.calls['single'], f.calls['batch']) for f in fns]
            run(e, now=NOW + dt.timedelta(days=1))
            self.assertEqual(calls, [(f.calls['single'], f.calls['batch']) for f in fns])

    def test_bad_dates_no_models(self):
        for bad in [None, 'garbage', '', 123]:
            with Env() as e:
                p = park(e, 'item', 40); c = yaml.safe_load(p.read_text())
                c['review']['parked_at'] = bad; p.write_text(m.dump_candidate(c))
                fns = judges()
                with self.assertRaises(RuntimeError): run(e)
                self.assertTrue(p.exists())
                self.assertTrue(all(f.calls['single'] == f.calls['batch'] == 0 for f in fns))

    def test_dryrun_zero_writes(self):
        with Env() as e:
            park(e, 'old', 40); judges()
            (e.mem.parent / 'archive').mkdir()
            before = tree(e.mem.parent)
            self.assertEqual(run(e, apply=False)[0]['decision'], 'expire')
            self.assertEqual(before, tree(e.mem.parent))

    def test_source_changes_before_apply_stays_parked(self):
        with Env() as e:
            p = park(e, 'old', 40); judges('promote', 'promote')
            orig = m.batch_precompute
            def batch(*a, **kw):
                result = orig(*a, **kw); e.src.write_text('Changed source without evidence.'); return result
            with patch.object(m, 'batch_precompute', batch):
                with self.assertRaises(RuntimeError): run(e)
            self.assertTrue(p.exists()); self.assertEqual(e.lane('done'), [])

    def test_destination_change_discards_cached_judges(self):
        with Env() as e:
            p = park(e, 'old', 40); fns = judges('promote', 'promote')
            orig = m.batch_precompute
            def batch(*a, **kw):
                result = orig(*a, **kw)
                note = e.vault / '03-resources/ai-memory/captured-personal.md'
                note.write_text(note.read_text() + '\nNew destination context\n')
                m._JUDGE_FNS.update({n: stub(lambda _i: 'reject') for n in ('judge_a','judge_b','tiebreak')})
                return result
            with patch.object(m, 'batch_precompute', batch): rows = run(e)
            self.assertEqual(rows[0]['decision'], 'reject')
            self.assertEqual(m._JUDGE_FNS['judge_a'].calls['single'], 1)
            self.assertEqual(e.lane('done'), [])

    def test_archive_unavailable_and_failed_write_keep_source(self):
        for mode in ['missing', 'write']:
            with Env() as e:
                p = park(e, 'old', 40); judges()
                root = e.mem.parent / 'missing'
                if mode == 'write': root.mkdir()
                ctx = patch.object(m, '_deadlock_write', side_effect=OSError('failed')) if mode == 'write' else patch.dict(m.os.environ, {'MEMORY_ARCHIVE_MOUNT': '/nonexistent-mount-point'})
                with ctx:
                    with self.assertRaises((RuntimeError, OSError)):
                        m.cmd_deadlocks_weekly(SimpleNamespace(apply=True), now=NOW, archive_root=root if mode == 'write' else None)
                self.assertTrue(p.exists())

    def test_candidate_changed_during_capacity_is_freshly_batched(self):
        with Env() as e:
            p = park(e, 'item', 8); fns = judges('reject', 'reject')
            changed = 'The changed backup schedule now runs on Friday evenings.'
            def capacity():
                c = yaml.safe_load(p.read_text()); c['fact'] = changed
                p.write_text(m.dump_candidate(c)); return 59
            with patch.object(m, '_weekly_capacity', capacity):
                rows = run(e)
            self.assertEqual(rows[0]['decision'], 'reject')
            self.assertTrue(all(changed in f.calls['prompts'][0] for f in fns[:2]))
            self.assertTrue(all(f.calls['single'] == 0 for f in fns))

    def test_payload_changed_before_snapshot_never_uses_old_verdict(self):
        with Env() as e:
            p = park(e, 'item', 8); fns = judges('promote', 'promote'); real = m._deadlock_snapshot
            calls = [0]
            changed = 'The changed backup schedule now runs on Friday evenings.'
            def snapshot(path, c):
                calls[0] += 1
                if calls[0] == 1:
                    fresh = yaml.safe_load(p.read_text()); fresh['fact'] = changed
                    p.write_text(m.dump_candidate(fresh))
                    m._JUDGE_FNS.update({n: stub(lambda _i: 'reject') for n in ('judge_a','judge_b','tiebreak')})
                return real(path, c)
            with patch.object(m, '_deadlock_snapshot', snapshot): rows = run(e)
            self.assertEqual(rows[0]['decision'], 'reject')
            self.assertEqual(m._JUDGE_FNS['judge_a'].calls['single'], 1)
            self.assertEqual(e.lane('done'), [])

    def test_capacity_known_thresholds_and_unknown(self):
        allowed = ['5.1', '8', '30', '59', '100']
        blocked = ['0', '5', '101']
        cases = [(v, SimpleNamespace(returncode=0, stdout=f'status=ok remaining_percent={v} ')) for v in allowed + blocked]
        cases += [('missing', SimpleNamespace(returncode=0, stdout='status=ok ')),
                  ('unknown', SimpleNamespace(returncode=0, stdout='status=unknown')),
                  ('nonzero', SimpleNamespace(returncode=1, stdout='status=ok remaining_percent=59 ')),
                  ('malformed', SimpleNamespace(returncode=0, stdout='status=ok remaining_percent=abc '))]
        with patch.dict(m.os.environ, {'MEMORY_CAPACITY_CMD': 'capacity-check --json'}):
            for label, result in cases:
                runner = lambda *a, _r=result, **kw: _r
                if label in allowed:
                    self.assertEqual(m._weekly_capacity(runner), float(label), label)
                else:
                    with self.assertRaises(RuntimeError, msg=label): m._weekly_capacity(runner)
        with patch.dict(m.os.environ, {'MEMORY_CAPACITY_CMD': ''}):
            self.assertEqual(m._weekly_capacity(lambda *a, **kw: self.fail('unset gate must not run a command')), 100.0)

    def test_capacity_defer_preserves_every_byte_and_calls_no_models(self):
        with Env() as e:
            p = park(e, 'old', 40); fns = judges(); (e.mem.parent / 'archive').mkdir()
            before = tree(e.mem.parent)
            with patch.object(m, '_weekly_capacity', side_effect=RuntimeError('capacity deferred')):
                with self.assertRaises(RuntimeError): run(e)
            self.assertEqual(before, tree(e.mem.parent))
            self.assertTrue(all(f.calls['single'] == f.calls['batch'] == 0 for f in fns))

    def test_legacy_local_clock_and_explicit_offset(self):
        naive = dt.datetime(2026, 10, 2, 17, 0)
        self.assertEqual(m._deadlock_time(naive.isoformat()), naive.astimezone(dt.timezone.utc))
        self.assertEqual(m._deadlock_time('2026-10-02T18:00:00+01:00'), NOW)

    def test_multiple_items_batch_not_individual_and_backlog_excluded(self):
        with Env() as e:
            park(e, 'a', 8); park(e, 'b', 8); p = park(e, 'backlog', 40)
            c = yaml.safe_load(p.read_text()); c['review']['reason_code'] = 'risk'; p.write_text(m.dump_candidate(c))
            fns = judges('reject', 'reject')
            rows = run(e)
            self.assertEqual([r['id'] for r in rows], ['a', 'b'])
            self.assertEqual([f.calls['batch'] for f in fns], [1, 1, 0])
            self.assertTrue(all(f.calls['single'] == 0 for f in fns)); self.assertTrue(p.exists())

    def test_same_run_duplicate_does_not_replay_promotion(self):
        with Env() as e:
            fact = 'Backups run Sunday evenings on the office computer.'
            park(e, 'a', 8, fact=fact); park(e, 'b', 8, fact=fact); judges('promote', 'promote')
            rows = run(e)
            self.assertEqual([r['decision'] for r in rows], ['promote', 'done'])
            self.assertEqual(len(m.LEDGER.read_text().splitlines()), 1)

    def test_source_changes_during_judging_never_expires(self):
        with Env() as e:
            p = park(e, 'old', 40); judges()
            original = m.judge_pipeline
            def changed(*a, **kw):
                result = original(*a, **kw); e.src.write_text('Removed source evidence.'); return result
            with patch.object(m, 'judge_pipeline', changed):
                with self.assertRaises(RuntimeError): run(e)
            self.assertTrue(p.exists()); self.assertEqual(list((e.mem.parent / 'archive').glob('*.yaml')), [])

    def test_report_or_state_failure_never_prints_success(self):
        import io
        from contextlib import redirect_stdout
        for suffix in ['.md', 'deadlocks-weekly-state.json']:
            with Env() as e:
                park(e, 'old', 8); judges(); real = m._deadlock_write
                def fail(path, data, replace=False):
                    if str(path).endswith(suffix): raise OSError('state/report unavailable')
                    return real(path, data, replace)
                out = io.StringIO()
                with redirect_stdout(out), patch.object(m, '_deadlock_write', fail):
                    with self.assertRaises(OSError): run(e)
                self.assertNotIn('0 failures', out.getvalue())
                self.assertFalse((e.mem / 'ledger' / 'deadlocks-weekly-state.json').exists())

    def test_missing_or_bad_attempted_date_fails_closed(self):
        with Env() as e:
            p = park(e, 'old', 40); c = yaml.safe_load(p.read_text())
            c['review']['deadlock_attempted_at'] = 'bad-date'; p.write_text(m.dump_candidate(c)); fns = judges()
            with self.assertRaises(RuntimeError): run(e)
            self.assertTrue(p.exists()); self.assertTrue(all(f.calls['batch'] == f.calls['single'] == 0 for f in fns))

    def test_quota_envelope_and_hard_stop_changes_preserve_bytes_no_judges(self):
        changes = [('parked_at', 'bad-date'), ('parked_at', (NOW-dt.timedelta(days=50)).isoformat()),
                   ('deadlock_attempted_at', 'bad-date'), ('deadlock_attempted_at', NOW.isoformat()),
                   ('reason_code', 'forbidden-pattern'), ('reason_code', 'risk')]
        for key, value in changes:
            with self.subTest(key=key, value=value), Env() as e:
                p = park(e, 'old', 40); fns = judges('promote', 'promote'); expected = []
                def capacity():
                    c = yaml.safe_load(p.read_text()); c['review'][key] = value
                    p.write_text(m.dump_candidate(c)); expected.append(p.read_bytes()); return 59
                with patch.object(m, '_weekly_capacity', capacity):
                    with self.assertRaises(RuntimeError): run(e)
                self.assertEqual(p.read_bytes(), expected[0]); self.assertEqual(e.lane('done'), [])
                self.assertTrue(all(f.calls['single'] == f.calls['batch'] == 0 for f in fns))

    def test_envelope_changes_between_batch_and_apply_never_use_verdict(self):
        for key, value in [('parked_at', 'bad-date'), ('reason_code', 'forbidden-pattern'),
                           ('deadlock_attempted_at', 'bad-date')]:
            with self.subTest(key=key), Env() as e:
                p = park(e, 'old', 40); fns = judges('promote', 'promote'); batch = m.batch_precompute; expected = []
                def changed(*a, **kw):
                    result = batch(*a, **kw); c = yaml.safe_load(p.read_text()); c['review'][key] = value
                    p.write_text(m.dump_candidate(c)); expected.append(p.read_bytes()); return result
                with patch.object(m, 'batch_precompute', changed):
                    with self.assertRaises(RuntimeError): run(e)
                self.assertEqual(p.read_bytes(), expected[0]); self.assertEqual(e.lane('done'), [])
                self.assertTrue(all(f.calls['single'] == 0 for f in fns))

    def test_completed_outcomes_report_and_state_retry_counts_once(self):
        for verdict, decision, label in [('promote','promote','promoted'), ('reject','reject','rejected'), ('hold','expire','expired')]:
            for suffix in ['.md', 'deadlocks-weekly-state.json']:
                with self.subTest(verdict=verdict, suffix=suffix), Env() as e:
                    p = park(e, 'old', 40); fns = judges(verdict, verdict); real = m._deadlock_write
                    def fail(path, data, replace=False):
                        if str(path).endswith(suffix): raise OSError('publication interrupted')
                        return real(path, data, replace)
                    with patch.object(m, '_deadlock_write', fail):
                        with self.assertRaises(OSError): run(e)
                    self.assertFalse(p.exists())
                    journal = json.loads((e.mem/'ledger/deadlocks-weekly-pass.json').read_text())
                    self.assertEqual(journal['rows']['old']['decision'], decision); self.assertFalse(journal['published'])
                    calls = [(f.calls['batch'], f.calls['single']) for f in fns]
                    with patch.object(m, '_weekly_capacity', side_effect=AssertionError('recovery read quota')):
                        rows = run(e)
                    self.assertEqual(rows[0]['decision'], decision)
                    self.assertEqual(calls, [(f.calls['batch'], f.calls['single']) for f in fns])
                    report = next((e.mem/'ledger').glob('weekly-memory-report-*.md')).read_text()
                    self.assertIn(f'1 {label}', report); self.assertIn('1 attempted', report)
                    before = tree(e.mem.parent); self.assertEqual(run(e), []); self.assertEqual(before, tree(e.mem.parent))

    def test_pending_result_recovers_existing_evidence_without_replay(self):
        for verdict, decision in [('promote','promote'), ('reject','reject'), ('hold','expire')]:
            with self.subTest(verdict=verdict), Env() as e:
                p = park(e, 'old', 40); fns = judges(verdict, verdict); real = m._deadlock_write
                def fail_result(path, data, replace=False):
                    if Path(path).name == 'deadlocks-weekly-pass.json' and json.loads(data).get('rows'):
                        raise OSError('result publication interrupted')
                    return real(path, data, replace)
                with patch.object(m, '_deadlock_write', fail_result):
                    with self.assertRaises(OSError): run(e)
                self.assertFalse(p.exists())
                self.assertEqual(json.loads((e.mem/'ledger/deadlocks-weekly-pass.json').read_text())['rows'], {})
                calls = [(f.calls['batch'],f.calls['single']) for f in fns]
                before = tree(e.mem.parent)
                self.assertEqual(run(e, apply=False)[0]['decision'], decision)
                self.assertEqual(before, tree(e.mem.parent))
                self.assertEqual(run(e)[0]['decision'], decision)
                self.assertEqual(calls, [(f.calls['batch'],f.calls['single']) for f in fns])
                report = next((e.mem/'ledger').glob('weekly-memory-report-*.md')).read_text()
                self.assertIn('1 attempted', report); self.assertIn('0 failures', report)

    def test_ambiguous_pending_result_remains_visibly_incomplete(self):
        with Env() as e:
            p = park(e, 'old', 40); fns = judges(); journal = {'pass_id':'missing-proof', 'now':NOW.isoformat(),
                'base':[0]*7, 'pending':['old'], 'rows':{}, 'failures':0, 'published':False}
            (e.mem/'ledger/deadlocks-weekly-pass.json').write_text(json.dumps(journal))
            with self.assertRaises(RuntimeError): run(e)
            self.assertTrue(p.exists()); self.assertTrue(all(f.calls['single']==f.calls['batch']==0 for f in fns))
            self.assertNotIn('last_successful_at', json.loads((e.mem/'ledger/deadlocks-weekly-state.json').read_text()))
            self.assertIn('1 failures', next((e.mem/'ledger').glob('weekly-memory-report-*.md')).read_text())

    def test_quota_source_hard_stop_preserves_candidate_and_calls_no_models(self):
        with Env() as e:
            p = park(e, 'old', 40); fns = judges('promote', 'promote'); original = p.read_bytes()
            def capacity():
                e.src.write_text('The source evidence has been removed.'); return 59
            with patch.object(m, '_weekly_capacity', capacity):
                with self.assertRaises(RuntimeError): run(e)
            self.assertEqual(p.read_bytes(), original)
            self.assertTrue(all(f.calls['single'] == f.calls['batch'] == 0 for f in fns))

    def test_publication_retry_retains_prior_week_totals_once(self):
        with Env() as e:
            park(e, 'old', 40); fns = judges('reject', 'reject')
            report = e.mem/'ledger/weekly-memory-report-2026-W40.md'
            report.write_text('deadlocks-weekly 2026-W40: 2 attempted; 1 promoted; 0 rejected; 0 expired; 0 already done; 1 parked; 0 failures\n')
            real = m._deadlock_write
            def fail(path, data, replace=False):
                if Path(path).name == 'deadlocks-weekly-state.json': raise OSError('interrupted state')
                return real(path, data, replace)
            with patch.object(m, '_deadlock_write', fail):
                with self.assertRaises(OSError): run(e)
            expected = report.read_bytes()
            run(e)
            self.assertEqual(report.read_bytes(), expected)
            self.assertIn('3 attempted; 1 promoted; 1 rejected', report.read_text())

    def test_failed_promoted_move_cleans_up_next_week_without_repromotion(self):
        with Env() as e:
            p = park(e, 'old', 40); fns = judges('promote', 'promote'); real = m._route_file
            def fail_done(src, dest, content=None):
                if Path(dest).name == 'done': raise OSError('done move failed')
                return real(src, dest, content)
            with patch.object(m, '_route_file', fail_done):
                with self.assertRaises(RuntimeError): run(e)
            self.assertTrue(p.exists())
            note = e.vault/'03-resources/ai-memory/captured-personal.md'
            ledger, vault = m.LEDGER.read_bytes(), note.read_bytes()
            self.assertEqual(len(ledger.splitlines()), 1)
            calls = [(f.calls['batch'], f.calls['single']) for f in fns]
            with patch.object(m, '_weekly_capacity', side_effect=AssertionError('cleanup read quota')):
                rows = run(e, now=NOW+dt.timedelta(days=7))
            self.assertEqual(rows[0]['decision'], 'done'); self.assertFalse(p.exists())
            self.assertEqual(e.lane('done'), ['old'])
            self.assertEqual(m.verify_source_status(e.excerpt, e.src), m.SOURCE_VERIFIED)
            self.assertEqual(m.LEDGER.read_bytes(), ledger); self.assertEqual(note.read_bytes(), vault)
            self.assertEqual(calls, [(f.calls['batch'], f.calls['single']) for f in fns])
            reports = [x.read_text() for x in (e.mem/'ledger').glob('weekly-memory-report-*.md')]
            self.assertEqual(sum(m._weekly_report_counts(x)[1] for x in (e.mem/'ledger').glob('weekly-memory-report-*.md')), 1)
            self.assertTrue(any('0 promoted' in text and '1 already done' in text for text in reports))

    def test_proven_duplicate_cleanup_still_obeys_hard_stops(self):
        variants = ('missing-source', 'changed-source', 'bad-park-date', 'bad-attempt-date',
                    'forbidden-envelope', 'riskenvelope', 'riskfield', 'unsafe-target', 'bad-observed-date')
        for variant in variants:
            with self.subTest(variant=variant), Env() as e:
                p = park(e, 'old', 40); c = yaml.safe_load(p.read_text()); fns = judges('promote','promote')
                if variant == 'bad-park-date': c['review']['parked_at'] = 'bad-date'
                elif variant == 'bad-attempt-date': c['review']['deadlock_attempted_at'] = 'bad-date'
                elif variant == 'forbidden-envelope': c['review']['reason_code'] = 'forbidden-pattern'
                elif variant == 'riskenvelope': c['review']['reason_code'] = 'risk'
                elif variant == 'riskfield': c['risk'] = 'high'
                elif variant == 'unsafe-target': c['target_note'] = '../outside.md'
                elif variant == 'bad-observed-date': c['observed_at'] = 'bad-date'
                p.write_text(m.dump_candidate(c))
                m.LEDGER.write_text(json.dumps({'candidate_sha256':m.candidate_sha256(c)})+'\n')
                note = e.vault/'03-resources/ai-memory/captured-personal.md'
                note.write_text(note.read_text()+'\n- '+c['fact']+'\n')
                if variant == 'missing-source': e.src.unlink()
                elif variant == 'changed-source': e.src.write_text('Removed supporting evidence.')
                before = p.read_bytes()
                with patch.object(m, '_weekly_capacity', side_effect=AssertionError('cleanup read quota')):
                    try: run(e)
                    except RuntimeError: pass
                self.assertTrue(p.exists()); self.assertEqual(p.read_bytes(), before); self.assertEqual(e.lane('done'), [])
                self.assertTrue(all(f.calls['batch']==f.calls['single']==0 for f in fns))

    def test_duplicate_without_ledger_proof_never_gets_cleanup(self):
        with Env() as e:
            p = park(e, 'old', 40); c = yaml.safe_load(p.read_text()); fns = judges('promote','promote')
            note = e.vault/'03-resources/ai-memory/captured-personal.md'
            note.write_text(note.read_text()+'\n- '+c['fact']+'\n'); before=p.read_bytes()
            with patch.object(m, '_weekly_capacity', side_effect=AssertionError('duplicate read quota')):
                with self.assertRaises(RuntimeError): run(e)
            self.assertTrue(p.exists()); self.assertEqual(p.read_bytes(),before); self.assertEqual(e.lane('done'), [])
            self.assertTrue(all(f.calls['batch']==f.calls['single']==0 for f in fns))

    def test_cleanup_rechecks_source_and_envelope_after_selection(self):
        for variant in ('missing-source', 'forbidden-envelope', 'bad-park-date'):
            with self.subTest(variant=variant), Env() as e:
                p = park(e, 'old', 40); c = yaml.safe_load(p.read_text()); fns = judges('promote','promote')
                m.LEDGER.write_text(json.dumps({'candidate_sha256':m.candidate_sha256(c)})+'\n')
                note = e.vault/'03-resources/ai-memory/captured-personal.md'
                note.write_text(note.read_text()+'\n- '+c['fact']+'\n')
                real = m._retriage_one; expected=[]
                def changed(*args, **kw):
                    if variant == 'missing-source': e.src.unlink()
                    else:
                        current=yaml.safe_load(p.read_text())
                        current['review']['reason_code' if variant=='forbidden-envelope' else 'parked_at'] = 'forbidden-pattern' if variant=='forbidden-envelope' else 'bad-date'
                        p.write_text(m.dump_candidate(current))
                    expected.append(p.read_bytes())
                    return real(*args, **kw)
                with patch.object(m, '_retriage_one', changed), patch.object(m, '_weekly_capacity', side_effect=AssertionError('cleanup read quota')):
                    with self.assertRaises(RuntimeError): run(e)
                self.assertTrue(p.exists()); self.assertEqual(p.read_bytes(),expected[0]); self.assertEqual(e.lane('done'), [])
                self.assertTrue(all(f.calls['batch']==f.calls['single']==0 for f in fns))

    def test_archive_interruption_recovery(self):
        with Env() as e:
            p = park(e, 'old', 40); root = e.mem.parent / 'archive'; root.mkdir()
            original = p.read_bytes(); real = m._deadlock_write
            def fail_manifest(path, data, replace=False):
                if str(path).endswith('.manifest.json'): raise OSError('interrupted')
                return real(path, data, replace)
            with patch.object(m, '_deadlock_write', fail_manifest):
                with self.assertRaises(OSError): m._archive_deadlock(p, root)
            self.assertEqual(p.read_bytes(), original)
            self.assertEqual(len(list(root.glob('*.yaml'))), 1)
            blob = m._archive_deadlock(p, root)
            self.assertEqual(blob.read_bytes(), original); self.assertFalse(p.exists())
            self.assertEqual(len(list(root.glob('*.yaml'))), 1)


def _dst_clock_suite():
    """Run local-time regressions in a child so the parent TZ is untouched."""
    time.tzset()
    repeated = dt.datetime(2026, 10, 25, 1, 30, tzinfo=dt.timezone.utc)
    legacy = '2026-10-25T01:30:00'

    class DSTClockPolicy(unittest.TestCase):
        def test_legacy_fold_gap_offset_and_ordinary_date_parity(self):
            # Assert the child really has London DST, independent of its host TZ.
            ordinary = dt.datetime(2026, 10, 2, 17, 0)
            self.assertEqual(ordinary.astimezone().utcoffset(), dt.timedelta(hours=1))
            self.assertEqual(m._deadlock_time(ordinary.isoformat()),
                             ordinary.astimezone(dt.timezone.utc))
            self.assertEqual(m._deadlock_time(legacy), repeated)
            self.assertEqual(m._deadlock_time(legacy + '+01:00'),
                             repeated - dt.timedelta(hours=1))
            self.assertEqual(m._deadlock_time(legacy + '+00:00'), repeated)
            self.assertEqual(m._deadlock_time('2026-10-25T01:30:00Z'), repeated)
            self.assertIsNone(m._deadlock_time('2026-03-29T01:30:00'))
            self.assertEqual(m._deadlock_time('2026-03-29T01:30:00+00:00'),
                             dt.datetime(2026, 3, 29, 1, 30, tzinfo=dt.timezone.utc))
            midnight = dt.datetime(2026, 10, 2).astimezone(dt.timezone.utc)
            self.assertEqual(m._deadlock_time('2026-10-02'), midnight)
            self.assertEqual(m._deadlock_time(dt.date(2026, 10, 2)), midnight)

        def test_new_envelope_preserves_both_repeated_hour_instants(self):
            for fixed in (repeated - dt.timedelta(hours=1), repeated):
                with self.subTest(instant=fixed), Env():
                    class FrozenDateTime(dt.datetime):
                        @classmethod
                        def now(cls, tz=None):
                            if tz is None:
                                return fixed.astimezone().replace(tzinfo=None)
                            return fixed.astimezone(tz)
                    with patch.object(m.datetime, 'datetime', FrozenDateTime):
                        stamp = m.build_review_envelope('deadlock', 'fixture')['parked_at']
                    self.assertEqual(stamp, fixed.isoformat())
                    self.assertEqual(m._deadlock_time(stamp), fixed)

        def test_seven_day_retry_boundaries_for_park_attempt_and_state(self):
            boundary = repeated + dt.timedelta(days=7)
            for clock in ('parked_at', 'deadlock_attempted_at', 'state'):
                with self.subTest(clock=clock), Env() as e:
                    p = park(e, 'item', 40)
                    c = yaml.safe_load(p.read_text())
                    if clock == 'state':
                        (e.mem / 'ledger/deadlocks-weekly-state.json').write_text(
                            json.dumps({'last_attempted_at': legacy}))
                    else:
                        c['review'][clock] = legacy
                        p.write_text(m.dump_candidate(c))
                    fns = judges(); before = tree(e.mem.parent)
                    self.assertEqual(run(e, apply=False,
                                         now=boundary-dt.timedelta(microseconds=1)), [])
                    self.assertEqual(tree(e.mem.parent), before)
                    self.assertTrue(all(f.calls['single'] == f.calls['batch'] == 0 for f in fns))
                    rows = run(e, now=boundary)
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]['decision'], 'park' if clock == 'parked_at' else 'expire')
                    if clock == 'parked_at':
                        env = yaml.safe_load(p.read_text())['review']
                        self.assertEqual(env['parked_at'], legacy)
                        self.assertEqual(env['deadlock_attempted_at'], boundary.isoformat())

        def test_thirty_day_expiry_waits_for_latest_fold_instant(self):
            with Env() as e:
                p = park(e, 'item', 40); c = yaml.safe_load(p.read_text())
                c['review']['parked_at'] = legacy; p.write_text(m.dump_candidate(c))
                judges(); boundary = repeated + dt.timedelta(days=30)
                before = tree(e.mem.parent)
                self.assertEqual(run(e, apply=False,
                                     now=boundary-dt.timedelta(microseconds=1))[0]['decision'], 'park')
                self.assertEqual(tree(e.mem.parent), before)
                self.assertEqual(run(e, now=boundary)[0]['decision'], 'expire')
                self.assertFalse(p.exists())

        def test_nonexistent_park_or_attempt_clock_holds_without_judges(self):
            for clock in ('parked_at', 'deadlock_attempted_at'):
                with self.subTest(clock=clock), Env() as e:
                    p = park(e, 'item', 40); c = yaml.safe_load(p.read_text())
                    c['review'][clock] = '2026-03-29T01:30:00'
                    p.write_text(m.dump_candidate(c)); fns = judges()
                    before = p.read_bytes()
                    with self.assertRaises(RuntimeError):
                        run(e)
                    self.assertEqual(p.read_bytes(), before)
                    self.assertTrue(all(f.calls['single'] == f.calls['batch'] == 0 for f in fns))

    return unittest.defaultTestLoader.loadTestsFromTestCase(DSTClockPolicy)


if __name__ == '__main__': unittest.main()
