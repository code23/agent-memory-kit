"""Offline host lifecycle tests. No native Keychain, PostgreSQL or launchd calls."""
import copy
import contextlib
import io
import json
import os
from pathlib import Path
import plistlib
import tempfile
import subprocess
import shutil
import types
import unittest
from unittest.mock import Mock, patch

from memory_kit import host
from memory_kit import __main__ as cli
from memory_kit import client, context_authority

REAL_PRIVATE_ROOT = host.security.assert_private_root
REAL_NOT_WRITABLE = host.security.assert_not_agent_writable


class Store:
    def __init__(self):
        self.values = {}
        self.writes = []

    def check_ready(self):
        return None

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
        self.pg_dir = self.base / "pg-bin"
        self.pg_dir.mkdir()
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
                          "pg_bin": str(self.pg_dir), "node": "/opt/example/node",
                          "python": "/opt/example/python", "software_hash": host.software_hash(self.kit),
                          "existing": None, "pg_tools": {name: str(self.pg_dir / name) for name in ("initdb", "pg_ctl", "psql", "postgres")}}

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
        config = json.loads((self.root / "config.json").read_text())
        config["pg_tools"] = self.preflight["pg_tools"]
        return config

    def plan(self):
        def versions(argv, **kwargs):
            text = "v24.1.0" if str(argv[0]).endswith("/node") else "tool (PostgreSQL) 18.1"
            return types.SimpleNamespace(returncode=0, stdout=text.encode(), stderr=b"")
        self.runner.side_effect = versions
        with patch.object(host.platform, "system", return_value="Darwin"), \
                patch.object(host.security, "coding_identity", return_value=self.identity), \
                patch.object(host, "_tool", side_effect=lambda path, identity: str(path)):
            return host.plan("demo-team", "coding", self.root,
                             str(self.pg_dir), "/opt/example/node", self.kit, keychain=self.store)

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

    def test_homebrew_version_suffix_is_accepted(self):
        def versions(argv, **kwargs):
            text = "v24.1.0" if str(argv[0]).endswith("/node") else "tool (PostgreSQL) 18.6 (Homebrew)"
            return types.SimpleNamespace(returncode=0, stdout=text.encode(), stderr=b"")
        with patch.object(host.platform, "system", return_value="Darwin"), \
                patch.object(host.security, "coding_identity", return_value=self.identity), \
                patch.object(host, "_tool", side_effect=lambda path, identity: str(path)), \
                patch.object(host, "command", side_effect=versions):
            result = host.plan("demo-team", "coding", self.root, str(self.pg_dir), "/opt/example/node", self.kit, keychain=self.store)
        self.assertIsNone(result["existing"])
        self.assertFalse(self.root.exists())

    def test_tool_symlink_is_canonicalized_before_permission_check(self):
        executable = self.base / "executable"
        executable.write_text("#!/bin/sh\n")
        executable.chmod(0o700)
        link = self.base / "node-link"
        link.symlink_to(executable)
        result = host._tool(link, self.identity)
        self.assertEqual(result, str(executable))
        self.writable.assert_called_with(executable, self.identity)

    def test_failed_software_copy_leaves_no_final_directory_and_resumes(self):
        original = host._write_new
        failed = False
        def interrupted(path, payload):
            nonlocal failed
            if not failed and ".install-" in str(path) and path.name.endswith(".mjs"):
                failed = True
                raise OSError("simulated interrupted copy")
            original(path, payload)
        with patch.object(host, "_write_new", side_effect=interrupted):
            with self.assertRaises(OSError):
                host.install(self.preflight, self.store)
        config = json.loads((self.root / "config.json").read_text())
        self.assertFalse(host._software(config).exists())
        self.assertEqual(list((self.root / "software").iterdir()), [])
        self.preflight["existing"] = config
        host.install(self.preflight, self.store)
        self.assertTrue(host._software(config).exists())
        self.assertEqual(len(self.store.writes), 4)

    def test_node_children_use_only_private_unix_socket_transport(self):
        config = self.install()
        bootstrap = next(call for call in self.calls if any(arg.endswith("team-memory-bootstrap.mjs") for arg in call[0]))
        env = bootstrap[1]["env"]
        self.assertEqual(env["DATABASE_URL"], "postgresql:///agent_memory")
        self.assertEqual(env["PGHOST"], str(self.root / "s"))
        self.assertEqual(env["PGUSER"], "amk_bootstrap")
        self.assertTrue(env["PGPASSWORD"])
        starts = [call for call in self.calls if call[0][-1:] == ["start"]]
        options = starts[0][0][starts[0][0].index("-o") + 1]
        self.assertIn("-h ''", options)
        self.assertIn("unix_socket_permissions=0700", options)
        self.assertNotIn("127.0.0.1", options)
        self.assertEqual((self.root / "s").stat().st_mode & 0o777, 0o700)

    def test_explicit_locale_without_ambient_launchd_locale(self):
        with patch.dict(os.environ, {}, clear=True):
            env = host.clean_env()
        self.assertEqual(env["LC_ALL"], "C")
        self.assertEqual(env["LANG"], "C")

    def test_stop_removes_owned_autostart_and_start_boots_out_stale_job(self):
        config = self.install()
        path = self.base / "LaunchAgents" / "owned.plist"
        path.parent.mkdir()
        path.write_bytes(plistlib.dumps(host._launch_payload(config)))
        path.chmod(0o600)
        with patch.object(host, "_plist_path", return_value=path), \
                patch.object(host, "_coding_identity", return_value=self.identity):
            host.stop(config)
            self.assertFalse(path.exists())
            self.calls.clear()
            host.start(config)
            commands = [argv[1] for argv, kwargs in self.calls if argv[0] == "/bin/launchctl"]
            self.assertLess(commands.index("bootout"), commands.index("bootstrap"))
            self.assertTrue(path.exists())

    def test_start_creates_only_missing_launch_agents_directory(self):
        config = self.install()
        path = self.base / "NewLaunchAgents" / "owned.plist"
        with patch.object(host, "_plist_path", return_value=path), \
                patch.object(host, "_coding_identity", return_value=self.identity):
            result = host.start(config)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(result, {"service_loaded": True})
        self.assertTrue(path.exists())

    def test_cli_connect_check_is_nonsecret_json_and_never_reads_stdin(self):
        native_argv = ["claude", "--model", "fixture-model", "--dangerously-skip-permissions"]
        output = io.StringIO()
        expected = {"ready": True, "keychain_unlocked": True, "item_acl_verified": False}
        stdin = types.SimpleNamespace(buffer=types.SimpleNamespace(read=lambda *_: self.fail("read-only check consumed stdin")),
                                      isatty=lambda: self.fail("read-only check queried stdin"))
        with patch.object(client, "check_connection", return_value=expected, create=True) as check, \
                patch("memory_kit.keychain.MacKeychain", return_value=self.store), \
                patch.object(cli.sys, "stdin", stdin), contextlib.redirect_stdout(output):
            result = cli.main(["connect-check", "--project", str(self.base), "--workspace", "demo-team",
                               "--url", "http://127.0.0.1:47892", "--instance", "demo-instance",
                               "--expected-uid", str(self.uid), "--rekey",
                               "--native-argv", json.dumps(native_argv)])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), expected)
        check.assert_called_once_with(self.base, "demo-team", "http://127.0.0.1:47892", self.store,
                                      "demo-instance", self.uid, rekey=True,
                                      native_argv=native_argv, review_context=False)
        self.assertEqual(len(output.getvalue().splitlines()), 1)

    def test_cli_reconnect_consumes_token_only_from_stdin(self):
        native_argv = ["claude", "--model", "fixture-model", "--dangerously-skip-permissions"]
        output = io.StringIO()
        token = b"kmt_" + b"a" * 43
        stdin = types.SimpleNamespace(buffer=io.BytesIO(token + b"\n"), isatty=lambda: False)
        with patch.object(client, "reconnect", return_value={}) as reconnect, \
                patch.object(client, "_project", return_value=self.base), \
                patch.object(context_authority, "decision", return_value=contextlib.nullcontext()) as approval, \
                patch("memory_kit.keychain.MacKeychain", return_value=self.store), \
                patch.object(cli.sys, "stdin", stdin), contextlib.redirect_stdout(output):
            result = cli.main(["reconnect", "--project", str(self.base), "--workspace", "demo-team",
                               "--url", "http://127.0.0.1:47892", "--instance", "new-instance",
                               "--native-argv", json.dumps(native_argv)])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), {"connected": True})
        approval.assert_called_once_with(self.base, "demo-team", "http://127.0.0.1:47892",
                                         "new-instance", native_argv)
        reconnect.assert_called_once_with(self.base, "demo-team", "http://127.0.0.1:47892",
                                          token, self.store, "new-instance", native_argv=native_argv)
        self.assertEqual(stdin.buffer.read(), b"")
        self.assertNotIn(token.decode(), output.getvalue())

    def test_cli_context_denial_precedes_credential_input_and_all_effects(self):
        native_argv = ["claude", "--model", "fixture-model", "--dangerously-skip-permissions"]
        stdin = types.SimpleNamespace(buffer=Mock(), isatty=lambda: False)
        stdin.buffer.read.side_effect = AssertionError("denied context consumed credential stdin")
        before = {str(path): path.read_bytes() for path in self.base.rglob("*") if path.is_file()}
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(client, "_project", return_value=self.base), \
                patch.object(context_authority, "decision", side_effect=client.ClientError("context denied")) as approval, \
                patch("memory_kit.keychain.MacKeychain") as keychain, \
                patch.object(client, "reconnect") as reconnect, \
                patch.object(client, "_replace") as write, \
                patch.object(subprocess, "Popen") as spawn, \
                patch.object(cli.sys, "stdin", stdin), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = cli.main(["reconnect", "--project", str(self.base), "--workspace", "demo-team",
                               "--url", "http://127.0.0.1:47892", "--instance", "new-instance",
                               "--native-argv", json.dumps(native_argv)])
        self.assertEqual(result, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(errors.getvalue().strip(), "context denied")
        approval.assert_called_once_with(self.base, "demo-team", "http://127.0.0.1:47892",
                                         "new-instance", native_argv)
        stdin.buffer.read.assert_not_called()
        keychain.assert_not_called()
        reconnect.assert_not_called()
        write.assert_not_called()
        spawn.assert_not_called()
        self.assertEqual(self.store.writes, [])
        self.assertEqual(before, {str(path): path.read_bytes() for path in self.base.rglob("*") if path.is_file()})

    def test_invalid_runtime_workspace_refuses_before_any_io(self):
        for value in ("a", "my_team", "a" * 32):
            with self.subTest(value=value):
                with patch.object(host.platform, "system", return_value="Darwin"):
                    with self.assertRaises(host.security.SecurityError):
                        host.plan(value, "coding", self.root, kit=self.kit)
        self.assertEqual(self.calls, [])
        self.private.assert_not_called()
        self.assertFalse(self.root.exists())

    def test_locked_keychain_preflight_and_install_write_nothing(self):
        with patch.object(self.store, "check_ready", side_effect=host.HostError("locked")):
            with self.assertRaisesRegex(host.HostError, "locked"):
                self.plan()
            with self.assertRaisesRegex(host.HostError, "locked"):
                host.install(self.preflight, self.store)
        self.assertFalse(self.root.exists())
        self.private.assert_not_called()
        self.assertEqual(self.store.writes, [])

    def test_config_only_load_stop_status_uninstall_work_in_partial_phase_without_tools(self):
        config = self.install()
        config["phase"] = "cluster_ready"
        config["node"] = "/missing/node"
        config["python"] = "/missing/python"
        host._save_config(self.root / "config.json", config, self.uid)
        with patch.object(host, "_tool", side_effect=AssertionError("runtime tools must not be required")):
            loaded = host.load(self.root, kit=self.kit, runtime=False)
            with patch.object(host, "_plist_path", return_value=self.base / "absent.plist"):
                self.assertFalse(host.status(loaded)["postgres_running"])
                self.assertTrue(host.stop(loaded)["stopped"])
                self.assertTrue(host.uninstall(loaded)["data_preserved"])
        self.assertTrue((self.root / "postgres/facts").exists())

    def test_failed_launch_bootstrap_removes_autostart_plist(self):
        config = self.install()
        path = self.base / "LaunchAgents" / "owned.plist"
        def fail(argv, **kwargs):
            if str(argv[0]) == "/bin/launchctl" and argv[1] == "bootstrap":
                raise host.HostError("no GUI session")
            return self.command(argv, **kwargs)
        self.runner.side_effect = fail
        with patch.object(host, "_plist_path", return_value=path), \
                patch.object(host, "_coding_identity", return_value=self.identity):
            with self.assertRaisesRegex(host.HostError, "no GUI session"):
                host.start(config)
        self.assertFalse(path.exists())

    def test_interrupted_uninstall_leaves_final_path_absent_and_reinstall_recovers(self):
        config = self.install()
        with patch.object(host, "_plist_path", return_value=self.base / "absent.plist"), \
                patch.object(host.shutil, "rmtree", side_effect=OSError("interrupted delete")):
            with self.assertRaises(OSError):
                host.uninstall(config)
        self.assertFalse(host._software(config).exists())
        self.assertTrue(list((self.root / "software").glob(".removed-*")))
        self.preflight["existing"] = config
        host.install(self.preflight, self.store)
        self.assertTrue(host._software(config).exists())
        self.assertEqual((self.root / "postgres/facts").read_bytes(), b"preserve me")

    def test_initdb_early_pg_version_failure_never_adopts_partial_cluster(self):
        original = self.command
        def fail(argv, **kwargs):
            result = original(argv, **kwargs)
            if Path(str(argv[0])).name == "initdb":
                raise host.HostError("initdb interrupted after PG_VERSION")
            return result
        self.runner.side_effect = fail
        with self.assertRaisesRegex(host.HostError, "initdb interrupted"):
            host.install(self.preflight, self.store)
        self.assertFalse((self.root / "postgres").exists())
        self.assertEqual(list(self.root.glob(".initdb-*")), [])
        self.preflight["existing"] = json.loads((self.root / "config.json").read_text())
        self.runner.side_effect = original
        host.install(self.preflight, self.store)
        self.assertTrue((self.root / "postgres/.amk-initdb-complete").exists())

    def test_token_creation_refuses_regular_file_and_accepts_actual_fifo(self):
        config = self.install()
        stdin = types.SimpleNamespace(isatty=lambda: True)
        with tempfile.TemporaryFile(mode="w+") as output, \
                patch.object(host.sys, "stdin", stdin), patch.object(host.sys, "stdout", output):
            with self.assertRaises(host.HostError):
                host.operator(config, ["tokens", "create"], self.store)
        read_fd, write_fd = os.pipe()
        try:
            with os.fdopen(write_fd, "w") as output, \
                    patch.object(host.sys, "stdin", stdin), patch.object(host.sys, "stdout", output):
                self.assertEqual(host.operator(config, ["tokens", "create"], self.store), 0)
        finally:
            os.close(read_fd)

    def test_symlink_selector_in_coding_writable_directory_refuses_safe_target(self):
        executable = self.base / "safe-executable"
        executable.write_text("#!/bin/sh\n")
        executable.chmod(0o700)
        directory = self.base / "coding-selector"
        directory.mkdir()
        link = directory / "pg_ctl"
        link.symlink_to(executable)
        def refuse(path, identity):
            if path == directory:
                raise host.security.SecurityError("AGENT_WRITABLE_SOFTWARE")
        self.writable.side_effect = refuse
        with self.assertRaises(host.security.SecurityError):
            host._tool(link, self.identity)

    def test_official_bootstrap_imports_do_not_write_bytecode(self):
        source = Path(host.__file__).resolve().parent.parent
        isolated = self.base / "bootstrap-copy"
        isolated.mkdir()
        shutil.copy2(source / "memory-kit", isolated / "memory-kit")
        (isolated / "memory_kit").mkdir()
        for path in (source / "memory_kit").glob("*.py"):
            shutil.copy2(path, isolated / "memory_kit" / path.name)
        result = subprocess.run([str(isolated / "memory-kit"), "--help"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(list(isolated.rglob("__pycache__")), [])

    def test_config_only_stop_disables_autostart_when_pg_tool_is_missing(self):
        config = self.install()
        path = self.base / "owned.plist"
        path.write_bytes(plistlib.dumps(host._launch_payload(config)))
        path.chmod(0o600)
        with patch.object(host, "_plist_path", return_value=path), \
                patch.object(host, "_pg_status", return_value=types.SimpleNamespace(returncode=4)):
            self.assertIsNone(host.status(config)["postgres_running"])
            with self.assertRaisesRegex(host.HostError, "PostgreSQL tools are unavailable"):
                host.stop(config)
        self.assertFalse(path.exists())
        self.assertTrue(any(argv[1:2] == ["bootout"] for argv, kwargs in self.calls))

    @unittest.skipUnless(host.platform.system() == "Darwin", "native macOS symlink chain check")
    def test_native_protected_outer_link_refuses_group_writable_middle_hop(self):
        outer = self.base / "outer"
        middle = self.base / "middle"
        outer.mkdir(mode=0o700)
        middle.mkdir(mode=0o770)
        middle.chmod(0o770)
        target = Path(shutil.which("node")).resolve()
        (middle / "node").symlink_to(target)
        (outer / "node").symlink_to(middle / "node")
        self.writable.side_effect = REAL_NOT_WRITABLE
        identity = {"uid": 99999, "gid": middle.stat().st_gid, "groups": [middle.stat().st_gid]}
        with self.assertRaises(host.security.SecurityError):
            host._tool(outer / "node", identity)
        self.assertEqual(self.calls, [])

    def test_actual_private_pidfile_missing_pg_tool_reports_unknown_without_execution(self):
        config = self.install()
        path = self.root / "postgres/postmaster.pid"
        path.write_text("12345\n" + str(self.root / "postgres") + "\n")
        path.chmod(0o600)
        self.calls.clear()
        with patch.object(host, "_coding_identity", return_value=self.identity), \
                patch.object(host, "_plist_path", return_value=self.base / "absent.plist"):
            self.assertEqual(host._pg_status(config).returncode, 4)
            self.assertIsNone(host.status(config)["postgres_running"])
            with self.assertRaises(host.HostError):
                host.stop(config)
        self.assertFalse(any(Path(argv[0]).name == "pg_ctl" for argv, kwargs in self.calls))

    def test_explicit_reinstall_refreshes_stale_python_selector(self):
        config = self.install()
        config["python_selector"] = "/removed/python"
        host._save_config(self.root / "config.json", config, self.uid)
        self.preflight["existing"] = config
        self.preflight["python_selector"] = "/replacement/python"
        host.install(self.preflight, self.store)
        saved = json.loads((self.root / "config.json").read_text())
        self.assertEqual(saved["python_selector"], "/replacement/python")
        self.assertNotIn("pg_tools", saved)

    def test_missing_verified_pg_tools_refuses_before_any_install_write(self):
        self.preflight.pop("pg_tools")
        with self.assertRaisesRegex(host.HostError, "preflight tools are required"):
            host.install(self.preflight, self.store)
        self.private.assert_not_called()
        self.assertFalse(self.root.exists())
        self.assertEqual(self.store.writes, [])

    def test_fresh_preflight_refuses_config_created_by_other_install(self):
        self.install()
        before = (self.root / "config.json").read_bytes()
        self.assertIsNone(self.preflight["existing"])
        self.calls.clear()
        with self.assertRaisesRegex(host.HostError, "changed after preflight"):
            host.install(self.preflight, self.store)
        self.assertEqual(self.calls, [])
        self.assertEqual((self.root / "config.json").read_bytes(), before)

    def test_missing_selector_has_specific_safe_diagnostic(self):
        with self.assertRaisesRegex(host.HostError, "explicit executable path is unavailable"):
            host._tool(self.base / "missing-node", self.identity)
        self.assertEqual(self.calls, [])

    def test_actual_symlink_cycle_is_bounded_and_refused_before_execution(self):
        first = self.base / "first"
        second = self.base / "second"
        first.symlink_to(second)
        second.symlink_to(first)
        with self.assertRaisesRegex(host.HostError, "cyclic or excessive symlink chain"):
            host._tool(first, self.identity)
        self.assertEqual(self.calls, [])

    def test_status_reports_missing_autostart_python(self):
        config = self.install()
        path = self.base / "owned.plist"
        payload = host._launch_payload(config)
        path.write_bytes(plistlib.dumps(payload))
        path.chmod(0o600)
        with patch.object(host, "_plist_path", return_value=path):
            self.assertTrue(host.status(config)["autostart_python_missing"])
            payload["ProgramArguments"][0] = str(Path(host.sys.executable).resolve())
            path.write_bytes(plistlib.dumps(payload))
            self.assertFalse(host.status(config)["autostart_python_missing"])

    def test_retry_uninstall_cleans_owned_retired_copy_and_returns_consistent_keys(self):
        config = self.install()
        with patch.object(host, "_plist_path", return_value=self.base / "absent.plist"):
            with patch.object(host.shutil, "rmtree", side_effect=OSError("interrupted")):
                with self.assertRaises(OSError):
                    host.uninstall(config)
            self.assertTrue(list((self.root / "software").glob(".removed-*")))
            result = host.uninstall(config)
        self.assertEqual(list((self.root / "software").glob(".removed-*")), [])
        self.assertEqual(result, {"uninstalled_service": True, "software_removed": True,
                                  "data_preserved": True, "configuration_and_keychain_preserved": True})
        self.assertTrue((self.root / "postgres/facts").exists())

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
        self.assertIn("--pwfile=/dev/stdin", initdb[0])
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
        path.write_bytes(plistlib.dumps(host._launch_payload(config)))
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

    def test_start_timeout_still_stops_owned_cluster_during_install(self):
        with patch.object(host, '_start_pg', side_effect=host.HostError('start timeout')):
            with self.assertRaisesRegex(host.HostError, 'start timeout'):
                host.install(self.preflight, self.store)
        self.assertEqual(self.calls[-1][0][-1], 'stop')

    def test_daemon_start_failure_still_stops_owned_cluster(self):
        with patch.object(host, 'credential', return_value='fixture'), \
             patch.object(host, '_start_pg', side_effect=host.HostError('start timeout')), \
             patch.object(host, '_pg') as stop:
            with self.assertRaisesRegex(host.HostError, 'start timeout'):
                host.daemon({'node': 'fixture'})
        stop.assert_called_once_with({'node': 'fixture'}, '-w', '-t', '30', '-m', 'fast', 'stop')

    def test_daemon_signal_during_spawn_is_not_lost(self):
        config = self.install()
        child = Mock(); child.poll.return_value = 0; child.wait.return_value = 0
        handlers = {}
        def handler(sig, callback): handlers[sig] = callback
        def spawn(*args, **kwargs):
            handlers[host.signal.SIGTERM](host.signal.SIGTERM, None)
            return child
        with patch.object(host, 'credential', return_value='postgresql://u:p@localhost/db'), \
             patch.object(host, '_start_pg'), patch.object(host, '_pg'), \
             patch.object(host.signal, 'signal', side_effect=handler), \
             patch.object(host.subprocess, 'Popen', side_effect=spawn):
            self.assertEqual(host.daemon(config), 0)
        child.terminate.assert_called_once()

    def test_config_replace_fsyncs_parent_directory(self):
        config = self.install()
        events = []
        real_sync, real_replace = os.fsync, os.replace
        def sync(fd):
            events.append(('sync', host.stat.S_ISDIR(os.fstat(fd).st_mode)))
            return real_sync(fd)
        def replace(*args, **kwargs):
            events.append(('replace', False)); return real_replace(*args, **kwargs)
        with patch.object(os, 'fsync', side_effect=sync), patch.object(os, 'replace', side_effect=replace):
            host._save_config(self.root / 'config.json', config, self.uid)
        self.assertEqual(events, [('sync', False), ('replace', False), ('sync', True)])

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
