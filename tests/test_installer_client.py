"""Offline business-client contract tests; no real Keychain or native client calls."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from memory_kit import client


class FakeKeychain:
    def __init__(self):
        self.values = {}
        self.puts = []

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
        self.keychain = FakeKeychain()
        self.token = b"offline-fixture-agent-token"

    def tearDown(self):
        self.home_patch.stop()
        self.temporary.cleanup()

    def connect(self, **kwargs):
        args = dict(project=self.project, workspace="business-fixture", url="http://127.0.0.1:4237/mcp",
                    token=self.token, keychain=self.keychain, instance="fixture")
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

    def test_invalid_credentials_are_never_written(self):
        for value in (b"", b"one\ntwo", b"two words", b"\xff", "not-bytes"):
            with self.subTest(value=type(value).__name__), self.assertRaises(client.ClientError):
                self.connect(token=value)
        self.assertEqual(self.tree(), {})
        self.assertEqual(self.keychain.puts, [])

    def test_global_logthis_is_detected_by_existence_without_reading(self):
        path = self.home / ".agents/skills/logthis"
        path.mkdir(parents=True)
        (path / "SKILL.md").write_text("This private content must not be read.")
        with self.assertRaisesRegex(client.ClientError, "handoff"):
            self.connect()
        self.assertEqual(self.tree(), {})

    def test_project_logthis_workflow_refused(self):
        (self.project / "AGENTS.md").write_text("Use the existing logthis workflow.\n")
        before = self.tree()
        with self.assertRaisesRegex(client.ClientError, "logthis"):
            self.connect()
        self.assertEqual(self.tree(), before)
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
            with self.assertRaises(client.ClientError), patch.object(subprocess, "run") as launch:
                client.run(path, ["codex-yolo"], self.keychain)
            launch.assert_not_called()
        with self.assertRaises(client.ClientError):
            client.run(self.project / "other.json", ["codex-yolo"], self.keychain)

    def test_run_passes_native_argv_unchanged_and_secret_only_in_child(self):
        self.connect()
        argv = ["claude-yolo", "--model", "unchanged-model", "a prompt"]
        prior = os.environ.get(client.TOKEN_ENV)
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess(argv, 7)) as launch:
            self.assertEqual(client.run(self.project / client.PROFILE_NAME, argv, self.keychain), 7)
        args, kwargs = launch.call_args
        self.assertIs(args[0], argv)
        self.assertEqual(kwargs["env"][client.TOKEN_ENV], self.token.decode())
        self.assertEqual(kwargs["cwd"], str(self.project))
        self.assertEqual(os.environ.get(client.TOKEN_ENV), prior)
        self.assertNotIn(self.token, b"".join(self.tree().values()))

    def test_changed_managed_file_and_missing_keychain_fail_closed(self):
        self.connect()
        path = self.project / "CLAUDE.md"
        before = path.read_bytes()
        path.write_bytes(before + b"changed")
        with patch.object(subprocess, "run") as launch:
            with self.assertRaises(client.ClientError):
                client.run(self.project / client.PROFILE_NAME, ["codex-yolo"], self.keychain)
            path.write_bytes(before)
            self.keychain.values.clear()
            with self.assertRaises(client.ClientError):
                client.run(self.project / client.PROFILE_NAME, ["codex-yolo"], self.keychain)
            launch.assert_not_called()

    def test_profile_workspace_cannot_disagree_with_instructions(self):
        self.connect()
        path = self.project / client.PROFILE_NAME
        profile = json.loads(path.read_text())
        profile["workspace"] = "another-business"
        path.write_text(json.dumps(profile))
        with patch.object(subprocess, "run") as launch:
            with self.assertRaises(client.ClientError):
                client.run(path, ["codex-yolo"], self.keychain)
            launch.assert_not_called()

    def test_new_global_logthis_conflict_refuses_launch(self):
        self.connect()
        path = self.home / ".codex/skills/logthis"
        path.mkdir(parents=True)
        with patch.object(subprocess, "run") as launch:
            with self.assertRaises(client.ClientError):
                client.run(self.project / client.PROFILE_NAME, ["codex-yolo"], self.keychain)
            launch.assert_not_called()

    def test_group_writable_codex_directory_refuses_launch(self):
        self.connect()
        path = self.project / ".codex"
        path.chmod(0o770)
        with patch.object(subprocess, "run") as launch:
            with self.assertRaises(client.ClientError):
                client.run(self.project / client.PROFILE_NAME, ["codex-yolo"], self.keychain)
            launch.assert_not_called()
        path.chmod(0o700)


if __name__ == "__main__":
    unittest.main()
