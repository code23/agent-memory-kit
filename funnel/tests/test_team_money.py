"""Client money and contacts survive capture and routing; private finance stays local. Offline."""
import os
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import capture
import memory as m


class TeamMoneyTests(unittest.TestCase):
    def test_redaction_alignment_and_client_price(self):
        patterns = m.POLICY['forbidden_patterns']
        self.assertIsInstance(patterns, dict)
        self.assertEqual(m.FORBIDDEN_PATTERN_KINDS, capture._SECRET_KINDS)
        self.assertEqual(len(patterns), len(capture._SECRET_PATTERNS))
        samples = {'api_key': 'sk-abcdefghij', 'ipv4': '192.0.2.10',
                   'repo_url': 'github.com/example', 'env_export': 'export EXAMPLE',
                   'port': 'host:12345', 'card_number': '4111111111111111',
                   'uk_bank_account': '12-34-56 12345678'}
        for i, kind in enumerate(m.FORBIDDEN_PATTERN_KINDS):
            for redactor, pattern in ((m.redact_secrets, patterns[kind]),
                                      (capture.redact_secrets, capture._SECRET_PATTERNS[i])):
                with self.subTest(kind=kind, redactor=redactor.__module__):
                    out, hits = redactor(samples[kind], [pattern], [kind])
                    self.assertIn('[REDACTED:' + kind + ']', out)
                    self.assertEqual(hits, [kind])
        for redactor in (m.redact_secrets, capture.redact_secrets):
            text = 'Acme agreed a £450 fee, $200 setup and €75 monthly support.'
            self.assertEqual(redactor(text), (text, []))

    def route(self, fact, excerpt):
        scope = 'org' if 'org' in m.POLICY['allowed_scope_prefixes'] else 'code23'
        registry = {'team_share_scopes': [scope, 'client:acme']}
        candidate = {'fact': fact, 'scope': 'client:acme', 'type': 'project_fact', 'source': {'excerpt': excerpt}}
        with patch.dict(os.environ, {'MEMORY_TEAM_ROUTING': '1',
                                     'MEMORY_TEAM_BIN': '/opt/example/team-memory'}), \
             patch.object(m, 'load_registry', return_value=registry), \
             patch.object(m, '_team_submitted_hashes', return_value=set()), \
             patch.object(m, '_TEAM_SEEN_FACTS', set()), \
             patch.object(m.subprocess, 'run', return_value=SimpleNamespace(
                 returncode=0, stdout='', stderr='')) as run:
            result = m.team_route(candidate, {'excerpt': excerpt}, candidate['scope'])
        return result, run.call_args_list

    def test_client_price_reaches_team_route_unmasked(self):
        fact = 'Acme agreed a £450 fee.'
        result, calls = self.route(fact, 'Acme agreed a £450 fee and £50 setup.')
        self.assertEqual(result['status'], 'submitted')
        submit = next(c.args[0] for c in calls if c.args[0][1] == 'submit')
        self.assertEqual(submit[submit.index('--title') + 1], fact)
        self.assertIn('£450 fee and £50 setup', submit[submit.index('--body') + 1])
        self.assertNotIn('[REDACTED:money]', ' '.join(submit))

    def test_business_contacts_reach_team_route_unmasked(self):
        fact = 'Acme business contact is owner@example.com on +44 7700 900123.'
        excerpt = 'For Acme support, email support@example.com or call 01865 123456.'
        for redactor in (capture.redact_secrets, m.redact_secrets):
            fact, hits = redactor(fact)
            self.assertEqual(hits, [])
            excerpt, hits = redactor(excerpt)
            self.assertEqual(hits, [])
        candidate, hits = m.redact_candidate({'fact': fact, 'source': {'excerpt': excerpt}})
        self.assertEqual(hits, [])
        result, calls = self.route(candidate['fact'], candidate['source']['excerpt'])
        self.assertEqual(result['status'], 'submitted')
        submit = next(c.args[0] for c in calls if c.args[0][1] == 'submit')
        self.assertEqual(submit[submit.index('--title') + 1], fact)
        body = submit[submit.index('--body') + 1]
        self.assertIn(fact, body)
        self.assertIn(excerpt, body)
        self.assertNotIn('[REDACTED:', body)
        blob = fact + '\n' + excerpt
        self.assertFalse(any(re.search(p, blob) for p in m.POLICY['forbidden_patterns'].values()))

    def test_api_key_still_masked(self):
        text = 'Acme API key is sk-abcdefghij.'
        for redactor in (capture.redact_secrets, m.redact_secrets):
            with self.subTest(redactor=redactor.__module__):
                out, hits = redactor(text)
                self.assertNotIn('sk-abcdefghij', out)
                self.assertIn('[REDACTED:api_key]', out)
                self.assertEqual(hits, ['api_key'])

    def test_private_finance_still_denied(self):
        for fact, excerpt in [('Payroll is £450 monthly.', 'Recorded by the team.'),
                              ('Acme agreed a £450 fee.', 'This funds payroll at £450 monthly.')]:
            with self.subTest(fact=fact):
                result, calls = self.route(fact, excerpt)
                self.assertEqual(result['status'], 'skipped')
                self.assertEqual(result['detail'], 'denied: private payroll')
                self.assertEqual(calls, [])


    def test_typical_client_fees_are_submitted(self):
        for fact in ('Acme upgrade is priced at £7,700 +VAT.',
                     'Acme invoice 0006595 is £500 plus VAT.',
                     'Acme pricing strategy sets the fee at £500.',
                     'Acme fee is £500 including tax.'):
            with self.subTest(fact=fact):
                self.assertEqual(m.collect_sensitivity_tags({'fact': fact}), [])
                result, calls = self.route(fact, fact)
                self.assertEqual(result['status'], 'submitted')
                submit = next(c.args[0] for c in calls if c.args[0][1] == 'submit')
                self.assertIn(fact, submit[submit.index('--body') + 1])

    def test_card_and_bank_identifiers_are_masked(self):
        for kind, texts in {
            'card_number': ('4111111111111', '4111 1111 1111 1111',
                            '4111-1111-1111-1111', '1234567890123456789'),
            'uk_bank_account': ('12-34-56 12345678', '12 34 56 / 12345678',
                                '123456 12345678', 'sort code: 12-34-56 account number: 12345678',
                                'Sort code 12-34-56, Account no. 12345678',
                                '12-34-56 and account number 12345678')
        }.items():
            for value in texts:
                for redact in (m.redact_secrets, capture.redact_secrets):
                    with self.subTest(value=value, redactor=redact.__module__):
                        self.assertEqual(redact(value), ('[REDACTED:' + kind + ']', [kind]))
                self.assertTrue(any(re.search(p, value) for p in m.POLICY['forbidden_patterns'].values()))

    def test_ordinary_phones_and_short_numbers_survive(self):
        for value in ('01865 123456', '+44 7700 900123', '07700-900123',
                      '+1 212 555 0123', '+123456789012345', '0006595', '12345678',
                      '123456789012', '12345678901234567890'):
            for redact in (m.redact_secrets, capture.redact_secrets):
                with self.subTest(value=value, redactor=redact.__module__):
                    self.assertEqual(redact(value), (value, []))

    def test_legacy_policy_fails_at_startup_and_doctor(self):
        import subprocess
        import tempfile
        import shutil
        import yaml
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy = dict(m.POLICY)
            policy['forbidden_patterns'] = [r'legacy-pattern'] * 8
            (root / 'policy.yaml').write_text(yaml.safe_dump(policy))
            code = Path(m.__file__).resolve().parent
            # The live copy resolves policy beside its code; the kit accepts MEMORY_POLICY.
            for name in ('memory.py', 'secret_patterns.py', 'safe_io.py'):
                if (code / name).exists():
                    shutil.copy2(code / name, root / name)
            env = dict(os.environ, MEMORY_ROOT=str(root), MEMORY_POLICY=str(root / 'policy.yaml'))
            for command in ('--help', 'doctor'):
                run = subprocess.run([sys.executable, str(root / 'memory.py'), command],
                                     env=env, capture_output=True, text=True)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn('forbidden_patterns must be a mapping keyed by kind', run.stdout + run.stderr)
            if hasattr(capture, 'active_patterns'):
                with patch.object(capture, '_policy_path', return_value=root / 'policy.yaml'):
                    with self.assertRaisesRegex(ValueError, 'mapping keyed by kind'):
                        capture.active_patterns()

    def test_policy_kinds_survive_reordering(self):
        import yaml
        patterns = m.POLICY['forbidden_patterns']
        self.assertIsInstance(patterns, dict)
        with patch.dict(m.POLICY, {'forbidden_patterns': dict(reversed(list(patterns.items())))}):
            self.assertEqual(m.redact_secrets('sk-abcdefghij'), ('[REDACTED:api_key]', ['api_key']))

    def assert_private_denied(self, term):
        private = term + ' of £2,000 was recorded.'
        for fact, excerpt in ((private, 'Recorded by the team.'), ('Acme agreed a £450 fee.', private)):
            with self.subTest(fact=fact, excerpt=excerpt):
                result, calls = self.route(fact, excerpt)
                self.assertEqual(result['status'], 'skipped')
                self.assertTrue(result['detail'].startswith('denied: private '), result)
                self.assertEqual(calls, [])

    def test_private_finance_00_salary(self):
        self.assert_private_denied('salary')

    def test_private_finance_01_salaries(self):
        self.assert_private_denied('salaries')

    def test_private_finance_02_payroll(self):
        self.assert_private_denied('payroll')

    def test_private_finance_03_dividend(self):
        self.assert_private_denied('dividend')

    def test_private_finance_04_dividends(self):
        self.assert_private_denied('dividends')

    def test_private_finance_05_directors_loan(self):
        self.assert_private_denied("director's loan")

    def test_private_finance_06_directors_loan(self):
        self.assert_private_denied('directors loan')

    def test_private_finance_07_director_loan(self):
        self.assert_private_denied('director loan')

    def test_private_finance_08_directors_loan(self):
        self.assert_private_denied('director’s loan')

    def test_private_finance_09_drawings(self):
        self.assert_private_denied('drawings')

    def test_private_finance_10_pension(self):
        self.assert_private_denied('pension')

    def test_private_finance_11_pensions(self):
        self.assert_private_denied('pensions')

    def test_private_finance_12_self_assessment(self):
        self.assert_private_denied('self assessment')

    def test_private_finance_13_self_assessment(self):
        self.assert_private_denied('self-assessment')

    def test_private_finance_14_tax_return(self):
        self.assert_private_denied('tax return')

    def test_private_finance_15_tax_returns(self):
        self.assert_private_denied('tax returns')

    def test_private_finance_16_paid_james(self):
        self.assert_private_denied('paid James')

    def test_private_finance_17_pays_james(self):
        self.assert_private_denied('pays James')

    def test_private_finance_18_payment_to_james(self):
        self.assert_private_denied('payment to James')

    def test_private_finance_19_payments_to_james(self):
        self.assert_private_denied('payments to James')

    def test_private_finance_20_corporation_tax(self):
        self.assert_private_denied('corporation tax')

    def test_private_finance_21_vat_return(self):
        self.assert_private_denied('VAT return')

    def test_private_finance_22_vat_returns(self):
        self.assert_private_denied('VAT returns')

    def test_private_finance_23_hmrc(self):
        self.assert_private_denied('HMRC')

    def test_private_finance_24_consultancy_invoice(self):
        self.assert_private_denied('consultancy invoice')



    def test_private_loan_plural_0(self):
        self.assert_private_denied("director's loans")

    def test_private_loan_plural_1(self):
        self.assert_private_denied('directors loans')

    def test_private_loan_plural_2(self):
        self.assert_private_denied('director loans')

    def test_capture_masks_identifiers_before_extraction(self):
        import tempfile
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            note = root / '4111111111111111.md'
            note.write_text('Card 4111 1111 1111 1111 and account 12-34-56 12345678.')
            with patch.object(capture, 'CAND', root / 'candidates'), \
                 patch.object(capture, 'load_registry', return_value={}), \
                 patch.object(capture, 'write_capture_state'), \
                 patch.object(capture, 'extract', return_value=[]) as extractor, \
                 patch.object(sys, 'argv', ['capture.py', str(note)]), \
                 contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                try:
                    capture.main()
                except SystemExit:
                    pass
            title, body = extractor.call_args.args
            self.assertEqual(title, '[REDACTED:card_number]')
            self.assertIn('[REDACTED:card_number]', body)
            self.assertIn('[REDACTED:uk_bank_account]', body)
            self.assertNotIn('4111', body)
            self.assertNotIn('12345678', body)


    def test_docs_assign_personal_contacts_to_council(self):
        docs = Path(__file__).resolve().parents[2] / 'docs'
        for name in ('how-agents-use-it.md', 'promotion-protocol.md', 'first-real-run.md'):
            with self.subTest(doc=name):
                text = (docs / name).read_text()
                self.assertIn('Deterministic secret checks refuse secrets only', text)
                self.assertIn('Cockpit council judges flag personal contacts', text)


if __name__ == '__main__':
    unittest.main()
