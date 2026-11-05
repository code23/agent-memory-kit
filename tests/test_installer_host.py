"""Offline host lifecycle tests. No native Keychain, PostgreSQL or launchd calls."""
import copy
import json
import os
from pathlib import Path
import plistlib
import tempfile
import types
import unittest
from unittest.mock import patch

from memory_kit import host

REAL_PRIVATE_ROOT = host.security.assert_private_root
REAL_NOT_WRITABLE = host.security.assert_not_agent_writable


class Store:
    def __init__(self):
        self.values = {}
        self.writes = []

    def get(self, instance, key):
        return self.values.get((instance, key))

    def put(self, instance, key, value):
        if (instance, key) in self.values:
            raise AssertionError("credential replacement")
        self.values[instance, key] = value
        self.writes.append((instance, key))


class HostTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "private"
        self.kit = self.base / "source"
        (self.kit / "runtime").mkdir(parents=True)
        (self.kit / "memory_kit").mkdir()
        for name in host.RUNTIME_FILES:
            (self.kit / "runtime" / name).write_bytes(b"test runtime")
        for name in ("__init__.py", "__main__.py", "host.py", "keychain.py", "security.py", "client.py"):
            (self.kit / "memory_kit" / name).write_bytes(b"test source")
        (self.kit / "memory-kit").write_bytes(b"test entrypoint")
        self.calls = []
        self.uid = os.getuid()
        self.identity = {"uid": self.uid + 1, "gid": 20, "groups": [20]}
        def private(path, uid):
            Path(path).mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(str(path), 0o700)
        self.private = patch.object(host.security, "ensure_private_directory", side_effect=private).start()
        self.guard = patch.object(host.security, "assert_private_root").start()
        self.writable = patch.object(host.security, "assert_not_agent_writable").start()
        self.addCleanup(patch.stopall)
        self.store = Store()
        self.runner = patch.object(host, "command", side_effect=self.command).start()
        patch.object(host, "_free_port").start()
        self.preflight = {"workspace": "demo-team", "coding_uid": self.identity["uid"],
                          "owner_uid": self.uid, "root": str(self.root), "kit": str(self.kit),
                          "pg_bin": "/opt/example/postgres/bin", "node": "/opt/example/node",
                          "python": "/opt/example/python", "software_hash": host.software_hash(self.kit),
                          "existing": None}

    def command(self, argv, **kwargs):
        argv = [str(item) for item in argv]
        self.calls.append((argv, kwargs))
        if Path(argv[0]).name == "initdb":
            data = Path(argv[argv.index("-D") + 1])
            data.mkdir(mode=0o700)
            (data / "PG_VERSION").write_text("18\n")
            os.chmod(str(data / "PG_VERSION"), 0o600)
            for name in ("postgresql.conf", "postgresql.auto.conf", "pg_hba.conf", "pg_ident.conf"):
                (data / name).write_text("# owned config\n")
                os.chmod(str(data / name), 0o600)
            (data / "facts").write_bytes(b"preserve me")
        return types.SimpleNamespace(returncode=3 if argv[-1:] == ["status"] else 0,
                                     stdout=b"", stderr=b"")

    def install(self):
        result = host.install(self.preflight, self.store)
        self.assertTrue(result["installed"])
        return json.loads((self.root / "config.json").read_text())

    def plan(self):
        def versions(argv, **kwargs):
            text = "v24.1.0" if str(argv[0]).endswith("/node") else "tool (PostgreSQL) 18.1"
            return types.SimpleNamespace(returncode=0, stdout=text.encode(), stderr=b"")
        self.runner.side_effect = versions
        with patch.object(host.platform, "system", return_value="Darwin"), \
                patch.object(host.security, "coding_identity", return_value=self.identity), \
                patch.object(host, "_tool", side_effect=lambda path, identity: str(path)):
            return host.plan("demo-team", "coding", self.root,
                             "/opt/example/postgres/bin", "/opt/example/node", self.kit)

    def test_readonly_plan_leaves_fresh_root_absent(self):
        result = self.plan()
        self.assertIsNone(result["existing"])
        self.assertFalse(self.root.exists())
        self.private.assert_not_called()
        self.assertEqual(self.store.writes, [])

    def test_preflight_security_refusal_writes_nothing(self):
        self.guard.side_effect = host.HostError("unsafe root")
        with self.assertRaisesRegex(host.HostError, "unsafe root"):
            self.plan()
        self.assertFalse(self.root.exists())
        self.private.assert_not_called()
        self.assertEqual(self.calls, [])

    def test_occupied_port_refuses_before_install_writes(self):
        with patch.object(host, "_free_port", side_effect=host.HostError("occupied")):
            with self.assertRaisesRegex(host.HostError, "occupied"):
                self.plan()
        self.assertFalse(self.root.exists())
        self.private.assert_not_called()

    def test_changed_version_refuses_without_modifying_existing_instance(self):
        self.install()
        before = (self.root / "config.json").read_bytes()
        (self.kit / "memory_kit/host.py").write_bytes(b"different version")
        with self.assertRaisesRegex(host.HostError, "identity or version differs"):
            self.plan()
        self.assertEqual((self.root / "config.json").read_bytes(), before)
        self.assertEqual(len(self.store.writes), 4)

    def test_cluster_configuration_change_refuses_before_start(self):
        config = self.install()
        (self.root / "postgres/postgresql.conf").write_text("data_directory = '/external'\n")
        self.calls.clear()
        with self.assertRaisesRegex(host.HostError, "configuration differs"):
            host._start_pg(config)
        self.assertEqual(self.calls, [])

    @unittest.skipUnless(host.platform.system() == "Darwin", "native macOS ACL integration")
    def test_native_security_preflight_accepts_absent_root_without_io(self):
        self.guard.side_effect = REAL_PRIVATE_ROOT
        self.writable.side_effect = REAL_NOT_WRITABLE
        self.plan()
        self.assertFalse(self.root.exists())
        self.private.assert_not_called()

    def test_install_credentials_never_in_argv_or_files(self):
        config = self.install()
        self.assertEqual(config["phase"], "installed")
        self.assertEqual(len(self.store.writes), 4)
        for credential in self.store.values.values():
            password = host.urlsplit(credential.decode()).password.encode()
            for argv, kwargs in self.calls:
                self.assertNotIn(password.decode(), " ".join(argv))
            for file in self.root.rglob("*"):
                if file.is_file():
                    self.assertNotIn(password, file.read_bytes())
        initdb = next(call for call in self.calls if Path(call[0][0]).name == "initdb")
        self.assertIn("--pwfile=-", initdb[0])
        self.assertIn("--auth-host=scram-sha-256", initdb[0])
        sql = next(call for call in self.calls if Path(call[0][0]).name == "psql")
        self.assertIn("PGPASSWORD", sql[1]["env"])
        self.assertIn(b"CREATE ROLE memory_operator", sql[1]["input"])
        self.assertEqual((self.root / "config.json").stat().st_mode & 0o777, 0o600)

    def test_matching_reinstall_preserves_credentials_cluster_and_facts(self):
        config = self.install()
        secrets_before = copy.deepcopy(self.store.values)
        self.calls.clear()
        self.preflight["existing"] = config
        host.install(self.preflight, self.store)
        self.assertEqual(self.store.values, secrets_before)
        self.assertEqual(len(self.store.writes), 4)
        self.assertFalse(any(Path(argv[0]).name == "initdb" for argv, kwargs in self.calls))
        self.assertEqual((self.root / "postgres/facts").read_bytes(), b"preserve me")

    def test_missing_existing_keychain_item_fails_without_rotation(self):
        config = self.install()
        self.preflight["existing"] = config
        del self.store.values[(config["instance"], "reader")]
        self.calls.clear()
        with self.assertRaisesRegex(host.HostError, "credentials are missing"):
            host.install(self.preflight, self.store)
        self.assertEqual(self.calls, [])
        self.assertEqual(len(self.store.writes), 4)

    def test_preflight_change_detected_before_subprocess(self):
        config = self.install()
        self.preflight["existing"] = copy.deepcopy(config)
        config["workspace"] = "different-team"
        host._save_config(self.root / "config.json", config, self.uid)
        self.calls.clear()
        with self.assertRaisesRegex(host.HostError, "changed after preflight"):
            host.install(self.preflight, self.store)
        self.assertEqual(self.calls, [])

    def test_bad_source_symlink_fails(self):
        target = self.kit / "runtime/team-memory-server.mjs"
        target.unlink()
        target.symlink_to(self.kit / "runtime/team-memory-bootstrap.mjs")
        with self.assertRaises(host.HostError):
            host.software_hash(self.kit)

    def test_source_directory_symlink_fails(self):
        (self.kit / "runtime").rename(self.kit / "other-runtime")
        (self.kit / "runtime").symlink_to(self.kit / "other-runtime", target_is_directory=True)
        with self.assertRaises(host.HostError):
            host.software_hash(self.kit)

    def test_clean_environment_discards_database_and_injection_settings(self):
        with patch.dict(os.environ, {"PGHOST": "remote.invalid", "PGPASSWORD": "sensitive",
                                     "PGSERVICE": "production", "DATABASE_URL": "sensitive",
                                     "NODE_OPTIONS": "--import evil", "PYTHONPATH": "/unsafe"}):
            env = host.clean_env({"PGPASSWORD": "isolated"})
        self.assertEqual(env["PGPASSWORD"], "isolated")
        for key in ("PGHOST", "PGSERVICE", "DATABASE_URL", "NODE_OPTIONS", "PYTHONPATH"):
            self.assertNotIn(key, env)

    def test_uninstall_preserves_database_config_keychain_and_reinstall_works(self):
        config = self.install()
        agent_dir = self.base / "LaunchAgents"
        agent_dir.mkdir()
        path = agent_dir / (host.label(config) + ".plist")
        args = [config["python"], "-I", str(host._software(config) / "memory-kit"), "daemon", "--root", config["root"]]
        path.write_bytes(plistlib.dumps({"Label": host.label(config), "ProgramArguments": args}))
        os.chmod(str(path), 0o600)
        with patch.object(host, "_plist_path", return_value=path):
            result = host.uninstall(config)
        self.assertTrue(result["data_preserved"])
        self.assertFalse(path.exists())
        self.assertTrue((self.root / "postgres/facts").exists())
        self.assertTrue((self.root / "config.json").exists())
        self.assertFalse(host._software(config).exists())
        self.assertEqual(len(self.store.values), 4)
        self.preflight["existing"] = config
        self.calls.clear()
        host.install(self.preflight, self.store)
        self.assertTrue(host._software(config).exists())
        self.assertFalse(any(Path(argv[0]).name == "initdb" for argv, kwargs in self.calls))
        self.assertEqual((self.root / "postgres/facts").read_bytes(), b"preserve me")

    def test_foreign_launch_agent_not_removed(self):
        config = self.install()
        path = self.base / "foreign.plist"
        path.write_bytes(plistlib.dumps({"Label": "foreign"}))
        os.chmod(str(path), 0o600)
        with patch.object(host, "_plist_path", return_value=path):
            with self.assertRaisesRegex(host.HostError, "does not match"):
                host.uninstall(config)
        self.assertTrue(path.exists())

    def test_runtime_failure_stops_only_owned_cluster(self):
        original = self.command
        def fail_bootstrap(argv, **kwargs):
            if any(str(arg).endswith("team-memory-bootstrap.mjs") for arg in argv):
                raise host.HostError("runtime refused")
            return original(argv, **kwargs)
        self.runner.side_effect = fail_bootstrap
        with self.assertRaisesRegex(host.HostError, "runtime refused"):
            host.install(self.preflight, self.store)
        self.assertEqual(self.calls[-1][0][-1], "stop")
        self.assertEqual(self.calls[-1][0][self.calls[-1][0].index("-D") + 1], str(self.root / "postgres"))
        self.assertEqual(json.loads((self.root / "config.json").read_text())["phase"], "cluster_ready")


if __name__ == "__main__":
    unittest.main()
