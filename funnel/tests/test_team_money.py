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
        self.assertEqual(len(patterns), len(m.FORBIDDEN_PATTERN_KINDS))
        self.assertEqual(m.FORBIDDEN_PATTERN_KINDS, capture._SECRET_KINDS)
        self.assertEqual(len(patterns), len(capture._SECRET_PATTERNS))
        samples = {'api_key': 'sk-abcdefghij', 'ipv4': '192.0.2.10',
                   'repo_url': 'github.com/example', 'env_export': 'export EXAMPLE',
                   'port': 'host:12345'}
        for i, kind in enumerate(m.FORBIDDEN_PATTERN_KINDS):
            for redactor, pattern in ((m.redact_secrets, patterns[i]),
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
        candidate = {'fact': fact, 'scope': 'client:acme', 'type': 'project_fact'}
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
        self.assertFalse(any(re.search(p, blob) for p in m.POLICY['forbidden_patterns']))

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


if __name__ == '__main__':
    unittest.main()
