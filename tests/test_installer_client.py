"""Binding unit tests with a permissive approval fake, never native acceptance.

The fake uses the same binding helpers as production. Real
approval and controlled-child environment checks live in test_installer_context.
"""

from contextlib import contextmanager, nullcontext
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from memory_kit import client, context_authority


class FakeKeychain:
    def __init__(self):
        self.values = {}
        self.puts = []
        self.readiness_checks = 0

    def check_ready(self):
        self.readiness_checks += 1

    def get(self, instance, role):
        return self.values.get((instance, role))

    def put(self, instance, role, secret):
        self.puts.append((instance, role))
        self.values[(instance, role)] = secret


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.project = self.base / "project"
        self.project.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        self.home_patch = patch.object(client, "_home", return_value=self.home)
        self.home_patch.start()
        self.account_patch = patch.object(client, "standard_coding_identity", return_value={"uid": os.getuid()})
        self.account_patch.start()
        self.native_home_patch = patch.dict(os.environ, {"CODEX_HOME": str(self.home / ".codex"),
                                                        "CLAUDE_CONFIG_DIR": str(self.home / ".claude")})
        self.native_home_patch.start()
        # Legacy binding unit tests explicitly mock ONLY the new approval boundary.
        # Its real protected-custody/native-contract behavior has focused tests.
        # Match reviewed binding validation; the fake admits more than production.
        @contextmanager
        def approved_binding(project, workspace, url, instance, argv):
            context_authority._arguments(argv)
            if Path(argv[0]).name != "claude":
                context_authority._native(argv)
            if (project / client.PROFILE_NAME).exists():
                client._verify(project, client._load_profile(project / client.PROFILE_NAME))
            else:
                client._prepare_binding(project, workspace, url, instance)
            yield {'identity': {'environment': context_authority._environment(),
                                'executable': {'path': argv[0]}, 'argv': argv}}
        # Same explicit legacy approval-boundary fixture: early metadata-only
        # admission is tested with real roots in test_installer_context.py.
        self.early_patch = patch.object(context_authority, "_early_reads", return_value=nullcontext())
        self.early_patch.start()
        self.addCleanup(self.early_patch.stop)
        self.planner_patch = patch.object(context_authority, "_plan_sources", return_value=None)
        self.planner_patch.start()
        self.addCleanup(self.planner_patch.stop)
        self.authority_patch = patch.object(context_authority, "decision", approved_binding)
        self.authority_patch.start()
        self.addCleanup(self.authority_patch.stop)
        self.context_env_patch = patch.object(context_authority, "_environment", return_value={})
        self.context_env_patch.start()
        self.addCleanup(self.context_env_patch.stop)
        self.keychain = FakeKeychain()
        self.token = b"offline-fixture-agent-token"
        # Binding tests must explicitly mock any child they intend to exercise.
        self.enterContext(patch.object(subprocess, 'Popen', side_effect=AssertionError('unmocked child launch')))

    def tearDown(self):
        self.home_patch.stop()
        self.account_patch.stop()
        self.native_home_patch.stop()
        self.temporary.cleanup()

    def connect(self, **kwargs):
        args = dict(project=self.project, workspace="business-fixture", url="http://127.0.0.1:4237/mcp",
                    token=self.token, keychain=self.keychain, instance="fixture", native_argv=["claude"])
        args.update(kwargs)
        return client.connect(**args)

    def tree(self):
        return {str(path.relative_to(self.project)): path.read_bytes()
                for path in self.project.rglob("*") if path.is_file()}

    def test_connect_preserves_existing_settings_and_instructions_without_secret(self):
        (self.project / ".mcp.json").write_text('{"mcpServers":{"other":{"type":"http","url":"http://127.0.0.1:77/mcp"}},"other":true}\n')
        (self.project / ".codex").mkdir()
        original = 'model = "existing-model"\n\n[mcp_servers.other]\nurl = "http://127.0.0.1:77/mcp"\n'
        (self.project / ".codex/config.toml").write_text(original)
        (self.project / "AGENTS.md").write_text("# Existing\nKeep this text.\n")
        profile = self.connect()
        self.assertEqual(json.loads((self.project / client.PROFILE_NAME).read_text()), profile)
        self.assertTrue((self.project / ".codex/config.toml").read_text().startswith(original))
        self.assertTrue((self.project / "AGENTS.md").read_text().startswith("# Existing\nKeep this text.\n"))
        self.assertEqual(json.loads((self.project / ".mcp.json").read_text())["mcpServers"]["other"]["type"], "http")
        self.assertEqual(len(profile["managed_hashes"]), 4)
        self.assertNotIn(self.token, b"".join(self.tree().values()))
        self.assertEqual(self.keychain.get("fixture", "agent"), self.token)
        self.assertEqual(self.keychain.puts, [("fixture", "agent")])

    def test_idempotent_connect_adds_one_block(self):
        first = self.connect()
        before = self.tree()
        self.assertEqual(first, self.connect())
        self.assertEqual(before, self.tree())
        for relative in ("AGENTS.md", "CLAUDE.md"):
            self.assertEqual((self.project / relative).read_text().count(client.BEGIN), 1)

    def test_workspace_rebinding_refused(self):
        self.connect()
        before = self.tree()
        with self.assertRaises(client.ClientError):
            self.connect(workspace="another-business")
        self.assertEqual(before, self.tree())

    def test_invalid_urls_and_workspace_leave_no_files_or_credentials(self):
        for url in ("https://127.0.0.1:123/mcp", "http://localhost:123/mcp", "http://127.0.0.1:123/other",
                    "http://127.0.0.1:123/mcp?token=fixture", "http://user@127.0.0.1:123/mcp", "http://127.0.0.1:0/mcp"):
            with self.subTest(url=url), self.assertRaises(client.ClientError):
                self.connect(url=url)
        with self.assertRaises(client.ClientError):
            self.connect(workspace="business\nextra")
        self.assertEqual(self.tree(), {})
        self.assertEqual(self.keychain.puts, [])

    def test_workspace_and_instance_use_shared_runtime_contracts_before_mutation(self):
        for workspace in ("0", "my_team", "Business", "a", "a" * 32, "a" * 41, "business.fixture"):
            with self.subTest(workspace=workspace), self.assertRaises(client.ClientError):
                self.connect(workspace=workspace)
        for instance in ("Caps", ".bad", "a" * 41, "a.b"):
            with self.subTest(instance=instance), self.assertRaises(client.ClientError):
                self.connect(instance=instance)
        self.assertEqual(self.tree(), {})
        self.assertEqual(self.keychain.puts, [])

    def test_invalid_credentials_are_never_written(self):
        for value in (b"", b"one\ntwo", b"two words", b"\xff", "not-bytes"):
            with self.subTest(value=type(value).__name__), self.assertRaises(client.ClientError):
                self.connect(token=value)
        self.assertEqual(self.tree(), {})
        self.assertEqual(self.keychain.puts, [])


    def test_existing_mcp_name_collision_preserves_all_data(self):
        (self.project / ".mcp.json").write_text('{"mcpServers":{"business-memory":{"url":"existing"}}}')
        before = self.tree()
        with self.assertRaises(client.ClientError):
            self.connect()
        self.assertEqual(before, self.tree())
        self.assertEqual(self.keychain.puts, [])

    def test_duplicate_json_fields_are_not_silently_discarded(self):
        path = self.project / ".mcp.json"
        path.write_text('{"mcpServers":{"business-memory":{}},"mcpServers":{}}')
        before = self.tree()
        with self.assertRaises(client.ClientError):
            self.connect()
        self.assertEqual(before, self.tree())
        self.assertEqual(self.keychain.puts, [])

    def test_existing_codex_name_collision_preserves_all_data(self):
        (self.project / ".codex").mkdir()
        (self.project / ".codex/config.toml").write_text('[mcp_servers."business-memory"]\nurl = "existing"\n')
        before = self.tree()
        with self.assertRaises(client.ClientError):
            self.connect()
        self.assertEqual(before, self.tree())

    def test_toml_parser_rejects_escaped_collision_malformed_and_inline_namespace(self):
        (self.project / ".codex").mkdir()
        path = self.project / ".codex/config.toml"
        examples = ('[mcp_servers."business\\u002dmemory"]\nurl = "existing"\n',
                    'model = "unfinished\n', 'mcp_servers = {}\n')
        for value in examples:
            path.write_text(value)
            before = self.tree()
            with self.subTest(value=value), self.assertRaises(client.ClientError):
                self.connect()
            self.assertEqual(before, self.tree())
        self.assertEqual(self.keychain.puts, [])

    def test_comment_mention_of_business_name_is_not_a_collision(self):
        (self.project / ".codex").mkdir()
        path = self.project / ".codex/config.toml"
        path.write_text('# optional business-memory connection\nmodel = "native-model"\n')
        self.connect()
        self.assertTrue(path.read_text().startswith('# optional business-memory connection\n'))

    def test_symlink_file_and_directory_refused(self):
        outside = self.base / "outside"
        outside.mkdir()
        (self.project / ".codex").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(client.ClientError):
            self.connect()
        self.assertEqual(list(outside.iterdir()), [])
        (self.project / ".codex").unlink()
        target = outside / "file"
        target.write_text("keep")
        (self.project / "AGENTS.md").symlink_to(target)
        with self.assertRaises(client.ClientError):
            self.connect()
        self.assertEqual(target.read_text(), "keep")

    def test_group_writable_and_readonly_project_refused(self):
        for mode in (0o770, 0o500):
            self.project.chmod(mode)
            with self.assertRaises(client.ClientError):
                self.connect()
        self.project.chmod(0o700)

    def test_hard_link_file_refused(self):
        target = self.base / "shared"
        target.write_text("do not edit")
        os.link(target, self.project / "AGENTS.md")
        with self.assertRaises(client.ClientError):
            self.connect()
        self.assertEqual(target.read_text(), "do not edit")

    def test_unowned_project_refused(self):
        with patch.object(client.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaises(client.ClientError):
                self.connect()

    def test_home_and_kit_project_refused(self):
        for path in (self.home, Path(client.__file__).resolve().parent.parent):
            with self.assertRaises(client.ClientError):
                self.connect(project=path)

    def test_global_configuration_directories_and_children_refused(self):
        for name in (".claude", ".codex", ".agents", ".config"):
            path = self.home / name
            path.mkdir()
            child = path / "nested"
            child.mkdir()
            for candidate in (path, child):
                with self.subTest(candidate=name), self.assertRaises(client.ClientError):
                    self.connect(project=candidate)

    def test_symlinked_global_configuration_target_is_not_a_project(self):
        target = self.base / "dotfiles"
        target.mkdir()
        (self.home / ".claude").symlink_to(target, target_is_directory=True)
        with self.assertRaises(client.ClientError):
            self.connect(project=target)
        self.assertEqual(list(target.iterdir()), [])

    def test_codex_approval_rules_do_not_block_mocked_claude_child(self):
        path = self.home / ".codex/rules"
        path.mkdir(parents=True)
        (path / "default.rules").write_text("prefix_rule fixture")
        self.connect()
        with patch.object(subprocess, "Popen", return_value=type("Child", (), {"wait": lambda self: 0, "poll": lambda self: 0})()):
            self.assertEqual(client.run(self.project / client.PROFILE_NAME, ["claude"], self.keychain), 0)

    def test_missing_native_argv_preserves_instruction_trees_without_body_reads(self):
        (self.base / ".git").mkdir()
        cases = [(self.home / native / filename, False)
                 for native in (".codex", ".claude")
                 for filename in ("AGENTS.md", "AGENTS.override.md", "CLAUDE.md", "CLAUDE.local.md")]
        cases += [(self.home / ".claude/rules", True),
                  (self.project / ".claude/rules", True),
                  (self.base / ".claude/rules", True)]
        for path, directory in cases:
            path.parent.mkdir(parents=True, exist_ok=True)
            if directory:
                path.mkdir()
                body = path / "private.md"
            else:
                body = path
            body.write_text("Private fixture body must remain unread and intact.\n")
            before = {str(item.relative_to(self.base)): item.read_bytes()
                      for item in self.base.rglob("*") if item.is_file()}
            real_snapshot = client._snapshot
            def guarded(candidate):
                self.assertNotEqual(candidate, body)
                return real_snapshot(candidate)
            with self.subTest(path=str(path.relative_to(self.base))), \
                 patch.object(client, "_snapshot", side_effect=guarded), \
                 self.assertRaisesRegex(client.ClientError, "native Claude"):
                self.connect(native_argv=None)
            after = {str(item.relative_to(self.base)): item.read_bytes()
                     for item in self.base.rglob("*") if item.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(self.keychain.puts, [])
            body.unlink()
            if directory:
                path.rmdir()

    def test_identity_distinguishes_missing_from_unresolvable_paths(self):
        self.assertIsNone(client._identity(self.base / "genuinely-missing"))
        path = self.home / ".claude"
        path.symlink_to(path)
        with self.assertRaisesRegex(client.ClientError, "cannot be resolved"):
            client._identity(path)
        path.unlink()
        with patch.object(Path, "stat", side_effect=PermissionError("private fixture diagnostic")):
            with self.assertRaisesRegex(client.ClientError, "cannot be resolved") as failure:
                client._identity(path)
        self.assertNotIn("private fixture diagnostic", str(failure.exception))

    def test_reviewed_binding_allows_unmanaged_routing_text(self):
        path = self.project / "AGENTS.md"
        path.write_text("## Audit log\n\nThis section explains records.\n")
        self.connect()
        with path.open("a") as handle:
            handle.write("\nAlways log this value.\n")
        with patch.object(subprocess, 'Popen', return_value=type('Child', (), {
                'wait': lambda self: 0, 'poll': lambda self: 0})()):
            self.assertEqual(client.run(self.project / client.PROFILE_NAME, ['claude'], self.keychain), 0)

    def test_case_alias_identity_is_rejected_even_when_path_spelling_differs(self):
        real_identity = client._identity
        def identity(path):
            return real_identity(self.home) if path == self.project else real_identity(path)
        with patch.object(client, "_identity", side_effect=identity), self.assertRaises(client.ClientError):
            self.connect()

    def test_secure_store_conflict_precedes_mutations(self):
        self.keychain.values[("fixture", "agent")] = b"different-fixture"
        with self.assertRaises(client.ClientError):
            self.connect()
        self.assertEqual(self.tree(), {})

    def test_keychain_failure_rolls_back_preserving_existing_files(self):
        (self.project / "AGENTS.md").write_text("Original instructions\n")
        before = self.tree()
        with patch.object(self.keychain, "put", side_effect=RuntimeError("SECURE_STORE_UNAVAILABLE")):
            with self.assertRaisesRegex(RuntimeError, "SECURE_STORE_UNAVAILABLE"):
                self.connect()
        self.assertEqual(self.tree(), before)
        self.assertFalse((self.project / ".codex").exists())

    def test_first_connect_stores_credential_before_profile_commit_point(self):
        original_put = self.keychain.put
        def check_order(*args):
            self.assertFalse((self.project / client.PROFILE_NAME).exists())
            original_put(*args)
        with patch.object(self.keychain, "put", side_effect=check_order):
            self.connect()
        self.assertTrue((self.project / client.PROFILE_NAME).exists())

    def test_rollback_preserves_concurrent_user_edit(self):
        def fail(*args):
            (self.project / ".mcp.json").write_text('{"user-edit": true}\n')
            raise RuntimeError("SECURE_STORE_UNAVAILABLE")
        with patch.object(self.keychain, "put", side_effect=fail):
            with self.assertRaises(RuntimeError):
                self.connect()
        self.assertEqual(self.tree(), {".mcp.json": b'{"user-edit": true}\n'})

    def test_rollback_preserves_concurrent_symlink_replacement(self):
        target = self.base / "user-file"
        target.write_text("keep")
        def fail(*args):
            path = self.project / ".mcp.json"
            path.unlink()
            path.symlink_to(target)
            raise RuntimeError("SECURE_STORE_UNAVAILABLE")
        with patch.object(self.keychain, "put", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "SECURE_STORE_UNAVAILABLE"):
                self.connect()
        self.assertTrue((self.project / ".mcp.json").is_symlink())
        self.assertEqual(target.read_text(), "keep")
        self.assertFalse((self.project / client.PROFILE_NAME).exists())

    def test_compare_and_swap_does_not_replace_changed_file(self):
        target = self.project / "AGENTS.md"
        target.write_text("before")
        previous = client._snapshot(target)
        target.write_text("user change")
        with self.assertRaises(client.ClientError):
            client._replace(target, previous, b"installer")
        self.assertEqual(target.read_text(), "user change")

    def test_missing_invalid_incomplete_and_wrong_profile_refused(self):
        path = self.project / client.PROFILE_NAME
        for data in (None, b"not-json", b"{}", b'{"version":false}'):
            if data is not None:
                path.write_bytes(data)
            with self.assertRaises(client.ClientError), patch.object(subprocess, "Popen") as launch:
                client.run(path, ["claude"], self.keychain)
            launch.assert_not_called()
        with self.assertRaises(client.ClientError):
            client.run(self.project / "other.json", ["claude"], self.keychain)

    def test_run_passes_native_argv_unchanged_and_secret_only_in_child(self):
        self.connect()
        argv = ["claude", "--model", "unchanged-model", "--dangerously-skip-permissions"]
        prior = os.environ.get(client.TOKEN_ENV)
        with patch.object(subprocess, "Popen", return_value=type("Child", (), {"wait": lambda self: 7, "poll": lambda self: 7})()) as launch:
            self.assertEqual(client.run(self.project / client.PROFILE_NAME, argv, self.keychain), 7)
        args, kwargs = launch.call_args
        self.assertEqual(args[0], argv)  # Checked launch constructs a fresh equal argv list.
        self.assertEqual(kwargs["env"][client.TOKEN_ENV], self.token.decode())
        self.assertEqual(kwargs["cwd"], str(self.project))
        self.assertEqual(os.environ.get(client.TOKEN_ENV), prior)
        self.assertNotIn(self.token, b"".join(self.tree().values()))

    def test_ordinary_unmanaged_edits_do_not_brick_run_or_connect(self):
        self.connect()
        for relative in ("AGENTS.md", "CLAUDE.md"):
            with (self.project / relative).open("a") as handle:
                handle.write("\nOrdinary project guidance.\n")
        mcp_path = self.project / ".mcp.json"
        mcp = json.loads(mcp_path.read_text())
        mcp["mcpServers"]["other"] = {"url": "http://127.0.0.1:77/mcp"}
        mcp_path.write_text(json.dumps(mcp))
        with (self.project / ".codex/config.toml").open("a") as handle:
            handle.write('\n[mcp_servers.other]\nurl = "http://127.0.0.1:77/mcp"\n')
        before = self.tree()
        with patch.object(subprocess, "Popen", return_value=type("Child", (), {"wait": lambda self: 0, "poll": lambda self: 0})()):
            self.assertEqual(client.run(self.project / client.PROFILE_NAME, ["claude"], self.keychain), 0)
        self.connect()
        self.assertEqual(self.tree(), before)

    def test_reconnect_uses_fresh_immutable_instance_without_editing_configs(self):
        self.connect()
        before = self.tree()
        replacement = b"offline-rotated-fixture"
        profile = client.reconnect(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                   replacement, self.keychain, "rotated-fixture", native_argv=["claude"])
        self.assertEqual(profile["keychain_instance"], "rotated-fixture")
        self.assertEqual(self.keychain.get("fixture", "agent"), self.token)
        self.assertEqual(self.keychain.get("rotated-fixture", "agent"), replacement)
        self.assertEqual({key: value for key, value in self.tree().items() if key != client.PROFILE_NAME},
                         {key: value for key, value in before.items() if key != client.PROFILE_NAME})
        with patch.object(subprocess, "Popen", return_value=type("Child", (), {"wait": lambda self: 0, "poll": lambda self: 0})()) as launch:
            client.run(self.project / client.PROFILE_NAME, ["claude"], self.keychain)
        self.assertEqual(launch.call_args.kwargs["env"][client.TOKEN_ENV], replacement.decode())
        self.assertNotIn(replacement, b"".join(self.tree().values()))

    def test_reconnect_rejects_scope_redirection_and_mutating_existing_instance(self):
        self.connect()
        before = self.tree()
        for workspace, url, instance in (("another-business", "http://127.0.0.1:4237/mcp", "new-fixture"),
                                         ("business-fixture", "http://127.0.0.1:4238/mcp", "new-fixture"),
                                         ("business-fixture", "http://127.0.0.1:4237/mcp", "fixture")):
            with self.subTest(workspace=workspace, url=url, instance=instance), self.assertRaises(client.ClientError):
                client.reconnect(self.project, workspace, url, b"replacement-fixture", self.keychain, instance, native_argv=["claude"])
        self.assertEqual(before, self.tree())
        self.assertEqual(self.keychain.puts, [("fixture", "agent")])

    def test_reconnect_rejects_conflicting_fresh_instance(self):
        self.connect()
        self.keychain.values[("rotated-fixture", "agent")] = b"unrelated-fixture"
        before = self.tree()
        with self.assertRaises(client.ClientError):
            client.reconnect(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                             b"replacement-fixture", self.keychain, "rotated-fixture", native_argv=["claude"])
        self.assertEqual(before, self.tree())
        self.assertEqual(self.keychain.puts, [("fixture", "agent")])

    def test_reconnect_requires_existing_intact_binding_before_store_write(self):
        with self.assertRaises(client.ClientError):
            client.reconnect(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                             b"replacement-fixture", self.keychain, "rotated-fixture", native_argv=["claude"])
        self.assertEqual(self.keychain.puts, [])
        self.connect()
        path = self.project / "AGENTS.md"
        path.write_text(path.read_text().replace("pending human review", "published immediately"))
        before = self.tree()
        with self.assertRaises(client.ClientError):
            client.reconnect(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                             b"replacement-fixture", self.keychain, "rotated-fixture", native_argv=["claude"])
        self.assertEqual(before, self.tree())
        self.assertEqual(self.keychain.puts, [("fixture", "agent")])

    def test_reconnect_keychain_failure_leaves_old_binding_usable(self):
        self.connect()
        before = self.tree()
        with patch.object(self.keychain, "put", side_effect=RuntimeError("SECURE_STORE_UNAVAILABLE")):
            with self.assertRaises(RuntimeError):
                client.reconnect(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                 b"replacement-fixture", self.keychain, "rotated-fixture", native_argv=["claude"])
        self.assertEqual(before, self.tree())
        with patch.object(subprocess, "Popen", return_value=type("Child", (), {"wait": lambda self: 0, "poll": lambda self: 0})()) as launch:
            client.run(self.project / client.PROFILE_NAME, ["claude"], self.keychain)
        self.assertEqual(launch.call_args.kwargs["env"][client.TOKEN_ENV], self.token.decode())

    def test_reconnect_profile_commit_failure_can_retry_same_unused_secure_item(self):
        self.connect()
        before = self.tree()
        with patch.object(client, "_replace", side_effect=RuntimeError("PROFILE_WRITE_FAILED")):
            with self.assertRaises(RuntimeError):
                client.reconnect(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                 b"replacement-fixture", self.keychain, "rotated-fixture", native_argv=["claude"])
        self.assertEqual(before, self.tree())
        self.assertEqual(self.keychain.get("rotated-fixture", "agent"), b"replacement-fixture")
        profile = client.reconnect(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                   b"replacement-fixture", self.keychain, "rotated-fixture", native_argv=["claude"])
        self.assertEqual(profile["keychain_instance"], "rotated-fixture")

    def test_reconnect_compare_and_swap_preserves_concurrent_profile_edit(self):
        self.connect()
        path = self.project / client.PROFILE_NAME
        def concurrent_edit(*args):
            path.write_text("concurrent user edit")
        with patch.object(self.keychain, "put", side_effect=concurrent_edit):
            with self.assertRaises(client.ClientError):
                client.reconnect(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                 b"replacement-fixture", self.keychain, "rotated-fixture", native_argv=["claude"])
        self.assertEqual(path.read_text(), "concurrent user edit")
        self.assertEqual(self.keychain.get("fixture", "agent"), self.token)

    def test_unshipped_legacy_profile_is_refused_without_rewriting_files(self):
        self.connect()
        path = self.project / client.PROFILE_NAME
        legacy = json.loads(path.read_text())
        legacy["version"] = 1
        path.write_text(json.dumps(legacy))
        before = self.tree()
        with self.assertRaises(client.ClientError):
            self.connect()
        self.assertEqual(before, self.tree())

    def test_managed_endpoint_or_token_reference_edit_cannot_be_rehashed_into_valid_scope(self):
        self.connect()
        mcp_path = self.project / ".mcp.json"
        profile_path = self.project / client.PROFILE_NAME
        before = mcp_path.read_text()
        for key, value in (("url", "http://127.0.0.1:9999/mcp"), ("headers", {"Authorization": "Bearer wrong-fixture"})):
            mcp = json.loads(before)
            mcp["mcpServers"][client.SERVER_NAME][key] = value
            mcp_path.write_text(json.dumps(mcp))
            profile = json.loads(profile_path.read_text())
            region = json.dumps(mcp["mcpServers"][client.SERVER_NAME], sort_keys=True, separators=(",", ":")).encode()
            profile["managed_hashes"][".mcp.json"] = client._digest(region)
            profile_path.write_text(json.dumps(profile))
            with self.subTest(key=key), self.assertRaises(client.ClientError):
                client.run(profile_path, ["claude"], self.keychain)

    def test_reviewed_guidance_uses_same_binding_validation_as_production(self):
        self.connect()
        with (self.project / 'AGENTS.md').open('a') as handle:
            handle.write('\nUse another logthis workflow.\n')
        with patch.object(subprocess, 'Popen', return_value=type('Child', (), {
                'wait': lambda self: 0, 'poll': lambda self: 0})()):
            self.assertEqual(client.run(self.project / client.PROFILE_NAME, ['claude'], self.keychain), 0)

    def test_binding_helpers_have_no_unreachable_review_mode(self):
        import inspect
        for name in ('_check_logthis', '_instruction_roots', '_ROUTING'):
            self.assertFalse(hasattr(client, name), name)
        for name in ('_verify', '_prepare_binding', '_managed_parts', '_instructions', '_profile'):
            self.assertNotIn('reviewed', inspect.signature(getattr(client, name)).parameters)


    def test_unmanaged_servers_cannot_reuse_credential_even_with_encoded_references(self):
        self.connect()
        mcp_path = self.project / ".mcp.json"
        before = mcp_path.read_text()
        for section in ({"headers": {"Authorization": "Bearer ${AGENT_MEMORY_TOKEN}"}},
                        {"env": {"copied": "AGENT_MEMORY_TOKEN"}}):
            mcp = json.loads(before)
            mcp["mcpServers"]["helper"] = section
            mcp_path.write_text(json.dumps(mcp).replace("AGENT_MEMORY_TOKEN", "AGENT\\u005fMEMORY_TOKEN"))
            with self.subTest(section=section), self.assertRaises(client.ClientError):
                client.run(self.project / client.PROFILE_NAME, ["claude"], self.keychain)
        mcp_path.write_text(before)
        path = self.project / ".codex/config.toml"
        original = path.read_text()
        for extra in ('\n[mcp_servers.helper]\nbearer_token_env_var = "AGENT_MEMORY_TOKEN"\n',
                      '\n[mcp_servers.helper.env]\ncopy = "AGENT\\u005fMEMORY_TOKEN"\n',
                      '\n# AGENT_MEMORY_TOKEN is referenced here\n'):
            path.write_text(original + extra)
            with self.subTest(extra=extra), self.assertRaises(client.ClientError):
                client.run(self.project / client.PROFILE_NAME, ["claude"], self.keychain)

    def test_preflight_refuses_existing_binding_without_rekey_before_readiness(self):
        self.connect()
        with self.assertRaises(client.ClientError):
            client.check_connection(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                    self.keychain, "fixture", os.getuid(), native_argv=["claude"])
        self.assertEqual(self.keychain.readiness_checks, 0)

    def test_stale_lock_preflight_refuses_before_new_token_or_mutation(self):
        (self.project / client._LOCK).write_text("stale lock fixture")
        before = self.tree()
        with self.assertRaises(client.ClientError):
            client.check_connection(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                    self.keychain, "fixture", os.getuid(), native_argv=["claude"])
        self.assertEqual(self.tree(), before)
        self.assertEqual(self.keychain.readiness_checks, 0)
        self.assertEqual(self.keychain.puts, [])

    def test_rollback_failure_continues_other_steps_and_preserves_original_error(self):
        (self.project / "AGENTS.md").write_text("Original guidance\n")
        real_replace = client._replace
        def replace(path, expected, data):
            if path.name == "AGENTS.md" and data == b"Original guidance\n":
                raise OSError("ROLLBACK_FAILED")
            return real_replace(path, expected, data)
        with patch.object(client, "_replace", side_effect=replace), \
             patch.object(self.keychain, "put", side_effect=RuntimeError("ORIGINAL_KEYCHAIN_FAILURE")):
            with self.assertRaisesRegex(RuntimeError, "ORIGINAL_KEYCHAIN_FAILURE"):
                self.connect()
        self.assertFalse((self.project / ".mcp.json").exists())
        self.assertFalse((self.project / "CLAUDE.md").exists())
        self.assertFalse((self.project / client.PROFILE_NAME).exists())

    def test_compare_and_swap_removal_preserves_a_newer_file(self):
        path = self.project / "file"
        path.write_text("installer")
        expected = client._snapshot(path)
        path.write_text("newer user edit")
        with self.assertRaises(client.ClientError):
            client._remove(path, expected)
        self.assertEqual(path.read_text(), "newer user edit")

    def test_changed_managed_file_and_missing_keychain_fail_closed(self):
        self.connect()
        path = self.project / "CLAUDE.md"
        before = path.read_bytes()
        path.write_bytes(before.replace(b"never approve or publish", b"approve and publish"))
        with patch.object(subprocess, "Popen") as launch:
            with self.assertRaises(client.ClientError):
                client.run(self.project / client.PROFILE_NAME, ["claude"], self.keychain)
            path.write_bytes(before)
            self.keychain.values.clear()
            with self.assertRaises(client.ClientError):
                client.run(self.project / client.PROFILE_NAME, ["claude"], self.keychain)
            launch.assert_not_called()

    def test_profile_workspace_cannot_disagree_with_instructions(self):
        self.connect()
        path = self.project / client.PROFILE_NAME
        profile = json.loads(path.read_text())
        profile["workspace"] = "another-business"
        path.write_text(json.dumps(profile))
        with patch.object(subprocess, "Popen") as launch:
            with self.assertRaises(client.ClientError):
                client.run(path, ["claude"], self.keychain)
            launch.assert_not_called()


    def test_group_writable_codex_directory_refuses_launch(self):
        self.connect()
        path = self.project / ".codex"
        path.chmod(0o770)
        with patch.object(subprocess, "Popen") as launch:
            with self.assertRaises(client.ClientError):
                client.run(self.project / client.PROFILE_NAME, ["claude"], self.keychain)
            launch.assert_not_called()
        path.chmod(0o700)

    def test_non_claude_child_is_refused_before_launch(self):
        self.connect()
        for argv in ([sys.executable, '-c', 'raise SystemExit(13)'], ['codex-yolo']):
            with self.subTest(argv=argv), patch.object(subprocess, 'Popen') as child:
                with self.assertRaises(client.ClientError):
                    client.run(self.project / client.PROFILE_NAME, argv, self.keychain)
                child.assert_not_called()


    def test_connection_sink_preflight_is_readonly_and_checks_expected_coding_uid(self):
        ready = client.check_connection(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                        self.keychain, "fixture", os.getuid(), native_argv=["claude"])
        self.assertTrue(ready["ready"])
        self.assertFalse(ready["item_access_verified"])
        self.assertFalse(ready["credential_received"])
        self.assertFalse(ready["changes_made"])
        self.assertEqual(self.tree(), {})
        self.assertEqual(self.keychain.puts, [])
        self.assertEqual(self.keychain.readiness_checks, 1)
        with self.assertRaises(client.ClientError):
            client.check_connection(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                    self.keychain, "fixture", os.getuid() + 1, native_argv=["claude"])
        self.assertEqual(self.keychain.readiness_checks, 1)

    def test_mocked_claude_binding_lifecycle_preserves_native_models_routing_and_unrelated_settings(self):
        self.enterContext(patch.object(subprocess, 'Popen', return_value=type('Child', (), {
            'wait': lambda self: 0, 'poll': lambda self: 0})()))
        codex = self.home / ".codex/config.toml"
        claude = self.home / ".claude/settings.json"
        routing = self.home / "native-routing.json"
        codex.parent.mkdir()
        claude.parent.mkdir()
        codex.write_text('model = "fixture-lead"\napproval_policy = "never"\n')
        claude.write_text(json.dumps({"model": "fixture-review", "permissions": {"defaultMode": "bypassPermissions"}}))
        routing.write_text(json.dumps({"lead": "fixture-lead", "worker": "fixture-worker", "review": "fixture-review"}))
        globals_before = {path: path.read_bytes() for path in (codex, claude, routing)}
        (self.project / ".codex").mkdir()
        local_codex = 'model = "fixture-worker"\n\n[mcp_servers.other]\nurl = "http://127.0.0.1:77/mcp"\n'
        (self.project / ".codex/config.toml").write_text(local_codex)
        other_server = {"type": "http", "url": "http://127.0.0.1:77/mcp"}
        (self.project / ".mcp.json").write_text(json.dumps({"mcpServers": {"other": other_server}, "unrelated": True}))
        (self.project / "AGENTS.md").write_text("Keep existing project guidance.\n")
        untouched = self.project / "unrelated-project.json"
        untouched.write_text('{"fixture_setting":"keep"}\n')
        untouched_before = untouched.read_bytes()
        before = self.tree()
        client.check_connection(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                self.keychain, "fixture", os.getuid(), native_argv=["claude"])
        self.assertEqual(self.tree(), before)
        self.connect()
        argv = ['claude', '--model', 'fixture-worker', '--dangerously-skip-permissions']
        prior_token = os.environ.get(client.TOKEN_ENV)
        self.assertEqual(client.run(self.project / client.PROFILE_NAME, argv, self.keychain), 0)
        bound = self.tree()
        client.check_connection(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                self.keychain, "rotated-fixture", os.getuid(), rekey=True, native_argv=["claude"])
        self.assertEqual(self.tree(), bound)
        rotated_token = b"offline-rotated-fixture"
        client.reconnect(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                         rotated_token, self.keychain, "rotated-fixture", native_argv=["claude"])
        self.assertEqual(client.run(self.project / client.PROFILE_NAME, argv, self.keychain), 0)
        self.assertEqual(os.environ.get(client.TOKEN_ENV), prior_token)
        self.assertEqual({path: path.read_bytes() for path in globals_before}, globals_before)
        self.assertEqual(untouched.read_bytes(), untouched_before)
        self.assertTrue((self.project / ".codex/config.toml").read_text().startswith(local_codex))
        mcp = json.loads((self.project / ".mcp.json").read_text())
        self.assertEqual(mcp["mcpServers"]["other"], other_server)
        self.assertTrue(mcp["unrelated"])
        self.assertEqual({name: value for name, value in self.tree().items() if name != client.PROFILE_NAME},
                         {name: value for name, value in bound.items() if name != client.PROFILE_NAME})


    def test_missing_native_argv_refuses_preflight_and_connect_without_body_reads(self):
        instruction = self.home / ".claude/CLAUDE.md"
        capture = self.home / ".agents/skills/logthis/SKILL.md"
        for bodies in ((instruction,), (capture,), (instruction, capture)):
            for path in bodies:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("Fictional private instructions and personal capture.\n")
            before = {str(path.relative_to(self.base)): path.read_bytes()
                      for path in self.base.rglob("*") if path.is_file()}
            modes = {path: stat.S_IMODE(path.stat().st_mode) for path in bodies}
            real_snapshot = client._snapshot
            def scoped_snapshot(path):
                self.assertNotIn(path, bodies)
                return real_snapshot(path)
            operations = {
                "connect-check": lambda: client.check_connection(
                    self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                    self.keychain, "fixture", os.getuid(), native_argv=None),
                "connect": lambda: self.connect(native_argv=None),
            }
            for operation, invoke in operations.items():
                try:
                    for path in bodies:
                        path.chmod(0)
                    with self.subTest(context=[str(path.relative_to(self.home)) for path in bodies], operation=operation), \
                         patch.object(client, "_snapshot", side_effect=scoped_snapshot), \
                         patch.object(self.keychain, "get") as get, \
                         patch.object(self.keychain, "put") as put, \
                         patch.object(self.keychain, "check_ready") as ready, \
                         patch.object(subprocess, "Popen") as launch:
                        with self.assertRaisesRegex(client.ClientError, "native Claude"):
                            invoke()
                        get.assert_not_called()
                        put.assert_not_called()
                        ready.assert_not_called()
                        launch.assert_not_called()
                finally:
                    for path, mode in modes.items():
                        path.chmod(mode)
                self.assertEqual({path: stat.S_IMODE(path.stat().st_mode) for path in bodies}, modes)
                self.assertEqual(before, {str(path.relative_to(self.base)): path.read_bytes()
                                          for path in self.base.rglob("*") if path.is_file()})
            for path in bodies:
                path.unlink()
            if capture in bodies:
                capture.parent.rmdir()

    def test_connection_sink_preflight_rejects_server_collision_before_keychain_readiness(self):
        (self.project / '.mcp.json').write_text('{"mcpServers":{"business-memory":{"type":"http","url":"http://127.0.0.1:77/mcp"}}}')
        before = self.tree()
        with self.assertRaises(client.ClientError):
            client.check_connection(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                    self.keychain, "fixture", os.getuid(), native_argv=["claude"])
        self.assertEqual(before, self.tree())
        self.assertEqual(self.keychain.readiness_checks, 0)

    def test_connection_sink_preflight_keychain_locked_fails_without_token_or_files(self):
        with patch.object(self.keychain, "check_ready", side_effect=RuntimeError("KEYCHAIN_LOCKED")):
            with self.assertRaisesRegex(RuntimeError, "KEYCHAIN_LOCKED"):
                client.check_connection(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                        self.keychain, "fixture", os.getuid(), native_argv=["claude"])
        self.assertEqual(self.tree(), {})
        self.assertEqual(self.keychain.puts, [])

    def test_connection_sink_preflight_rejects_privileged_coding_account(self):
        with patch.object(client, "standard_coding_identity", side_effect=client.SecurityError("STANDARD_CODING_ACCOUNT_REQUIRED")):
            with self.assertRaises(client.SecurityError):
                client.check_connection(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                        self.keychain, "fixture", os.getuid(), native_argv=["claude"])
        self.assertEqual(self.tree(), {})
        self.assertEqual(self.keychain.readiness_checks, 0)

    def test_connection_sink_preflight_existing_rotation_scope_and_instance(self):
        self.connect()
        before = self.tree()
        client.check_connection(self.project, "business-fixture", "http://127.0.0.1:4237/mcp",
                                self.keychain, "rotated-fixture", os.getuid(), rekey=True, native_argv=["claude"])
        self.assertEqual(before, self.tree())
        for workspace, instance, rekey in (("another-business", "rotated-fixture", True),
                                           ("business-fixture", "fixture", True),
                                           ("business-fixture", "rotated-fixture", False)):
            with self.subTest(workspace=workspace, instance=instance, rekey=rekey), self.assertRaises(client.ClientError):
                client.check_connection(self.project, workspace, "http://127.0.0.1:4237/mcp",
                                        self.keychain, instance, os.getuid(), rekey=rekey, native_argv=["claude"])
        self.assertEqual(before, self.tree())


if __name__ == "__main__":
    unittest.main()
