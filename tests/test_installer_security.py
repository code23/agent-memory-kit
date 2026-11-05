"""Offline security contracts; no real Keychain item is read or written."""

import ctypes
import errno
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from memory_kit.keychain import MacKeychain, SecretStoreError, _NativeKeychain, validate_instance
from memory_kit.security import (
    SecurityError, _DarwinStatFS64, _check_acl, _check_volume, assert_not_agent_writable, assert_private_root,
    coding_identity, ensure_private_directory, validate_workspace,
)


class MemoryKeychain:
    def __init__(self):
        self.items = {}
        self.writes = 0

    def find(self, service, account):
        return self.items.get((service, account))

    def add(self, service, account, value):
        self.writes += 1
        self.items[(service, account)] = value


class Callable:
    """A mock native function that supports ctypes signature attributes."""
    def __init__(self, implementation):
        self.implementation = implementation

    def __call__(self, *args):
        return self.implementation(*args)


class KeychainTests(unittest.TestCase):
    def setUp(self):
        self.backend = MemoryKeychain()
        self.store = MacKeychain(self.backend)

    def test_missing_create_and_identical_retry(self):
        self.assertIsNone(self.store.get("sample", "agent"))
        self.store.put("sample", "agent", b"synthetic-test-secret")
        self.store.put("sample", "agent", b"synthetic-test-secret")
        self.assertEqual(self.store.get("sample", "agent"), b"synthetic-test-secret")
        self.assertEqual(self.backend.writes, 1)
        self.assertIn((b"org.code23.agent-memory-kit.sample", b"agent"), self.backend.items)

    def test_conflicting_secret_is_preserved(self):
        self.store.put("sample", "agent", b"synthetic-one")
        with self.assertRaisesRegex(SecretStoreError, "^KEYCHAIN_VALUE_CONFLICT$"):
            self.store.put("sample", "agent", b"synthetic-two")
        self.assertEqual(self.store.get("sample", "agent"), b"synthetic-one")
        self.assertEqual(self.backend.writes, 1)

    def test_unexpected_backend_errors_are_redacted(self):
        with patch.object(self.backend, "find", side_effect=RuntimeError("synthetic-private-detail")):
            with self.assertRaisesRegex(SecretStoreError, "^KEYCHAIN_READ_FAILED$"):
                self.store.get("sample", "agent")
            with self.assertRaisesRegex(SecretStoreError, "^KEYCHAIN_READ_FAILED$"):
                self.store.put("sample", "agent", b"synthetic")
        with patch.object(self.backend, "add", side_effect=RuntimeError("synthetic-private-detail")):
            with self.assertRaisesRegex(SecretStoreError, "^KEYCHAIN_WRITE_FAILED$"):
                self.store.put("sample", "agent", b"synthetic")

    def native_store(self, status=0):
        releases = []
        data = ctypes.create_string_buffer(b"synthetic\x00bytes")

        def find(_keychain, _sl, _service, _al, _account, length, output, item):
            ctypes.cast(length, ctypes.POINTER(ctypes.c_uint32))[0] = len(data.raw) - 1
            ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(data)
            ctypes.cast(item, ctypes.POINTER(ctypes.c_void_p))[0] = 77
            return status

        security = SimpleNamespace(
            SecKeychainFindGenericPassword=Callable(find),
            SecKeychainAddGenericPassword=Callable(lambda *args: status),
            SecKeychainItemFreeContent=Callable(lambda *args: releases.append("content") or 0),
            SecKeychainCopyDefault=Callable(lambda *args: -25307),
            SecKeychainGetStatus=Callable(lambda *args: -50),
        )
        cf = SimpleNamespace(CFRelease=Callable(lambda *args: releases.append("reference")))
        return _NativeKeychain(security, cf), releases

    def test_native_binary_secret_and_resource_release(self):
        native, releases = self.native_store()
        self.assertEqual(native.find(b"service", b"account"), b"synthetic\x00bytes")
        self.assertEqual(releases, ["content", "reference"])

    def test_native_missing_is_only_nonerror_status(self):
        for status in (-25300, -25293, -128, -25308, -50):
            with self.subTest(status=status):
                native, releases = self.native_store(status)
                if status == -25300:
                    self.assertIsNone(native.find(b"service", b"account"))
                else:
                    with self.assertRaisesRegex(SecretStoreError, "^KEYCHAIN_READ_FAILED$"):
                        native.find(b"service", b"account")
                self.assertEqual(releases, ["content", "reference"])

    def test_native_add_refuses_duplicates(self):
        native, _ = self.native_store(-25299)
        with self.assertRaisesRegex(SecretStoreError, "^KEYCHAIN_VALUE_CONFLICT$"):
            native.add(b"service", b"account", b"synthetic")

    def test_readiness_uses_only_store_status_and_releases_reference(self):
        for copy_status, status_result, flags, expected in (
                (0, 0, 7, None), (0, 0, 6, "KEYCHAIN_LOCKED"),
                (0, 0, 3, "KEYCHAIN_PERMISSION_DENIED"),
                (0, -128, 0, "KEYCHAIN_READINESS_FAILED"),
                (-25307, 0, 0, "KEYCHAIN_UNAVAILABLE")):
            with self.subTest(copy_status=copy_status, status=status_result, flags=flags):
                native, releases = self.native_store()

                def copy_default(output):
                    ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = 88
                    return copy_status

                def get_status(keychain, output):
                    self.assertEqual(keychain.value, 88)
                    ctypes.cast(output, ctypes.POINTER(ctypes.c_uint32))[0] = flags
                    return status_result

                native.security.SecKeychainCopyDefault.implementation = copy_default
                native.security.SecKeychainGetStatus.implementation = get_status
                native.security.SecKeychainFindGenericPassword.implementation = lambda *args: self.fail("Item read")
                native.security.SecKeychainAddGenericPassword.implementation = lambda *args: self.fail("Item write")
                if expected:
                    with self.assertRaisesRegex(SecretStoreError, "^" + expected + "$"):
                        MacKeychain(native).check_ready()
                else:
                    MacKeychain(native).check_ready()
                self.assertEqual(releases, ["reference"])

    def test_readiness_requires_available_store_and_redacts_unexpected_errors(self):
        native, releases = self.native_store()
        native.security.SecKeychainCopyDefault.implementation = lambda *args: 0
        with self.assertRaisesRegex(SecretStoreError, "^KEYCHAIN_UNAVAILABLE$"):
            MacKeychain(native).check_ready()
        self.assertEqual(releases, [])
        backend = SimpleNamespace(check_ready=lambda: (_ for _ in ()).throw(RuntimeError("synthetic-private-detail")))
        with self.assertRaisesRegex(SecretStoreError, "^KEYCHAIN_READINESS_FAILED$"):
            MacKeychain(backend).check_ready()

    def test_names_and_values_are_validated(self):
        for instance in ("../sample", "UPPER", "", "x" * 41):
            with self.assertRaises(SecretStoreError):
                self.store.get(instance, "agent")
        for value in (b"", "not-bytes", None):
            with self.assertRaises(SecretStoreError):
                self.store.put("sample", "agent", value)

    def test_shared_instance_validation_matches_store_namespace(self):
        for value in ("sample", "sample_2", "0", "x" * 40,
                      "12345678-abcd-1234-abcd-123456789abc"):
            self.assertEqual(validate_instance(value), value)
            self.assertIsNone(self.store.get(value, "agent"))
        for value in ("", "UPPER", "sample.name", "x" * 41, None):
            with self.assertRaisesRegex(SecretStoreError, "^KEYCHAIN_INVALID_INSTANCE$"):
                validate_instance(value)

    def test_native_store_requires_macos(self):
        with patch("memory_kit.keychain.sys.platform", "linux"):
            with self.assertRaisesRegex(SecretStoreError, "^KEYCHAIN_MACOS_REQUIRED$"):
                MacKeychain()


class DirectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.uid = os.getuid()
        (self.root / "checkout").mkdir(mode=0o700)
        # Native ACL behavior is tested separately; these fixtures are portable.
        self.acl = patch("memory_kit.security._check_acl")
        self.acl.start()
        self.addCleanup(self.acl.stop)
        self.volume = patch("memory_kit.security._check_volume")
        self.volume.start()
        self.addCleanup(self.volume.stop)

    def test_workspace_slug_and_uuid_rejection(self):
        for value in ("sample", "sample-team-2", "ab", "x" * 40):
            self.assertEqual(validate_workspace(value), value)
        for value in ("", "Sample", "../sample", "_sample", "sample/name", "x" * 41,
                      "sample_team", "0", "a", "0sample", "a" * 32, "0" * 32,
                      "12345678-abcd-1234-abcd-123456789abc", None):
            with self.subTest(value=value), self.assertRaises(SecurityError):
                validate_workspace(value)

    def test_creates_owner_only_application_data(self):
        path = self.root / "Application Support" / "Memory Kit" / "sample"
        ensure_private_directory(path, self.uid)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
        self.assertEqual(path.stat().st_uid, self.uid)
        assert_private_root(path, self.root / "checkout", self.uid)
        ensure_private_directory(path, self.uid)

    def test_existing_unsafe_directory_is_not_chmodded(self):
        path = self.root / "existing"
        path.mkdir(mode=0o755)
        with self.assertRaisesRegex(SecurityError, "^PRIVATE_ROOT_PERMISSIONS$"):
            ensure_private_directory(path, self.uid)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o755)

    def test_rejects_symlink_in_any_component(self):
        real = self.root / "real"
        real.mkdir(mode=0o700)
        link = self.root / "linked"
        link.symlink_to(real, target_is_directory=True)
        for path in (link, link / "child"):
            with self.assertRaises(SecurityError):
                ensure_private_directory(path, self.uid)
        self.assertFalse((real / "child").exists())

    def test_rejects_wrong_owner_and_writable_ancestors(self):
        path = self.root / "private"
        path.mkdir(mode=0o700, exist_ok=True)
        with self.assertRaises(SecurityError):
            ensure_private_directory(path, self.uid + 10000)
        self.root.chmod(0o777)
        with self.assertRaisesRegex(SecurityError, "^UNSAFE_ANCESTOR_MODE$"):
            ensure_private_directory(path, self.uid)

    def test_rejects_replacement_after_open(self):
        path = self.root / "private"
        path.mkdir(mode=0o700)
        real_lstat = os.lstat

        def replaced(candidate, *args, **kwargs):
            info = real_lstat(candidate, *args, **kwargs)
            if Path(candidate) == path:
                values = list(info)
                values[1] += 1
                return os.stat_result(values)
            return info

        with patch("memory_kit.security.os.lstat", side_effect=replaced):
            with self.assertRaisesRegex(SecurityError, "^PATH_REPLACED$"):
                ensure_private_directory(path, self.uid)

    def test_root_is_outside_checkout_and_missing_root_is_read_only(self):
        path = self.root / "checkout"
        for candidate in (path, path / "private"):
            with self.assertRaisesRegex(SecurityError, "^PRIVATE_ROOT_IN_CHECKOUT$"):
                assert_private_root(candidate, path, self.uid)
        with self.assertRaises(SecurityError):
            assert_private_root(Path("/"), path, self.uid)
        missing = self.root / "missing" / "nested"
        assert_private_root(missing, path, self.uid)
        self.assertFalse((self.root / "missing").exists())

    def test_coding_identity_requires_explicit_distinct_account(self):
        account = SimpleNamespace(pw_name="test-coder", pw_uid=750, pw_gid=751)
        with patch("memory_kit.security.pwd.getpwnam", return_value=account), \
                patch("memory_kit.security.os.getgrouplist", return_value=[751, 752]), \
                patch("memory_kit.security.grp.getgrgid"):
            self.assertEqual(coding_identity("test-coder", 700), {
                "name": "test-coder", "uid": 750, "gid": 751, "groups": [751, 752],
            })
            with self.assertRaisesRegex(SecurityError, "^SEPARATE_CODING_ACCOUNT_REQUIRED$"):
                coding_identity("test-coder", 750)
            account.pw_uid = 500
            with self.assertRaises(SecurityError):
                coding_identity("test-coder", 700)
        with self.assertRaisesRegex(SecurityError, "^CODING_ACCOUNT_REQUIRED$"):
            coding_identity("", 700)
        with patch("memory_kit.security.pwd.getpwnam", side_effect=KeyError):
            with self.assertRaisesRegex(SecurityError, "^CODING_ACCOUNT_UNAVAILABLE$"):
                coding_identity("missing-test-account", 700)

    def test_coding_identity_rejects_privileged_groups(self):
        account = SimpleNamespace(pw_name="test-coder", pw_uid=750, pw_gid=751)
        for group in (0, 80):
            with self.subTest(group=group), \
                    patch("memory_kit.security.pwd.getpwnam", return_value=account), \
                    patch("memory_kit.security.os.getgrouplist", return_value=[751, group]), \
                    self.assertRaisesRegex(SecurityError, "^STANDARD_CODING_ACCOUNT_REQUIRED$"):
                coding_identity("test-coder", 700)
            with self.assertRaisesRegex(SecurityError, "^STANDARD_CODING_ACCOUNT_REQUIRED$"):
                assert_not_agent_writable(self.root / "checkout", {"uid": 750, "gid": 751, "groups": [group]})

    def test_both_walks_reject_untrusted_volume_before_mutation(self):
        self.volume.stop()
        with patch("memory_kit.security._check_volume", side_effect=SecurityError("OWNERSHIP_DISABLED_VOLUME")):
            with self.assertRaisesRegex(SecurityError, "^OWNERSHIP_DISABLED_VOLUME$"):
                ensure_private_directory(self.root / "missing", self.uid)
            with self.assertRaisesRegex(SecurityError, "^OWNERSHIP_DISABLED_VOLUME$"):
                assert_not_agent_writable(self.root / "checkout", {"uid": 750, "gid": 751, "groups": []})
        self.assertFalse((self.root / "missing").exists())

    def test_source_software_cannot_be_coder_writable(self):
        path = self.root / "source"
        path.write_text("synthetic software")
        identity = {"uid": self.uid, "gid": os.getgid(), "groups": [os.getgid()]}
        with self.assertRaisesRegex(SecurityError, "^AGENT_WRITABLE_SOFTWARE$"):
            assert_not_agent_writable(path, identity)
        other = {"uid": self.uid + 10000, "gid": 90001, "groups": [90001]}
        # A writable ancestor remains unsafe with a separately owned leaf.
        self.root.chmod(0o777)
        with self.assertRaisesRegex(SecurityError, "^AGENT_WRITABLE_SOFTWARE$"):
            assert_not_agent_writable(path, other)

    def test_software_checks_owner_group_and_other_permissions(self):
        identity = {"uid": 750, "gid": 751, "groups": [751, 752]}
        for owner, group, mode, writable in (
                (700, 701, 0o755, False), (750, 701, 0o755, True),
                (750, 701, 0o444, True),
                (700, 752, 0o775, True), (700, 701, 0o777, True)):
            with self.subTest(owner=owner, group=group, mode=mode):
                directory = os.stat_result((stat.S_IFDIR | 0o755, 1, 2, 1, 0, 0, 0, 0, 0, 0))
                software = os.stat_result((stat.S_IFREG | mode, 3, 2, 1, owner, group, 0, 0, 0, 0))
                with patch("memory_kit.security.os.open", side_effect=[100, 101]), \
                        patch("memory_kit.security.os.close"), \
                        patch("memory_kit.security.os.fstat", side_effect=[directory, software]), \
                        patch("memory_kit.security.os.lstat", side_effect=[directory, software]):
                    if writable:
                        with self.assertRaisesRegex(SecurityError, "^AGENT_WRITABLE_SOFTWARE$"):
                            assert_not_agent_writable(Path("/synthetic-tool"), identity)
                    else:
                        assert_not_agent_writable(Path("/synthetic-tool"), identity)


class ACLTests(unittest.TestCase):
    def native(self, entries, failure=None):
        state = {"index": 0, "freed": False}

        def get_acl(*args):
            if failure is not None:
                ctypes.set_errno(failure)
                return None
            return 1

        def get_entry(_acl, selector, output):
            index = 0 if selector == 0 else state["index"] + 1
            state["index"] = index
            if index >= len(entries):
                ctypes.set_errno(errno.EINVAL)
                return -1
            ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = index + 1
            return 0

        def get_tag(entry, output):
            ctypes.cast(output, ctypes.POINTER(ctypes.c_int))[0] = entries[entry.value - 1][0]
            return 0

        def get_perms(entry, output):
            ctypes.cast(output, ctypes.POINTER(ctypes.c_uint64))[0] = entries[entry.value - 1][1]
            return 0

        return SimpleNamespace(
            acl_get_fd_np=Callable(get_acl), acl_get_entry=Callable(get_entry),
            acl_get_tag_type=Callable(get_tag), acl_get_permset_mask_np=Callable(get_perms),
            acl_free=Callable(lambda *args: state.update(freed=True) or 0),
        ), state

    def test_native_acl_deny_readonly_and_mutation_grants(self):
        for entries, private, expected in (([(2, 0xffff)], True, None),
                                           ([(1, 2)], False, None),
                                           ([(1, 2)], True, "UNSAFE_ACL"),
                                           ([(1, 4)], False, "UNSAFE_ACL"),
                                           ([(1, 1 << 40)], False, "UNSAFE_ACL"),
                                           ([(99, 0)], False, "ACL_CHECK_FAILED")):
            with self.subTest(entries=entries, private=private):
                libc, state = self.native(entries)
                with patch("memory_kit.security.sys.platform", "darwin"), \
                        patch("memory_kit.security.ctypes.CDLL", return_value=libc):
                    if expected:
                        with self.assertRaisesRegex(SecurityError, "^" + expected + "$"):
                            _check_acl(8, private)
                    else:
                        _check_acl(8, private)
                self.assertTrue(state["freed"])

    def test_no_acl_is_safe_but_acl_read_failure_is_not(self):
        for failure in (errno.ENOENT, errno.EACCES, errno.EIO):
            libc, _ = self.native([], failure)
            with patch("memory_kit.security.sys.platform", "darwin"), \
                    patch("memory_kit.security.ctypes.CDLL", return_value=libc):
                if failure == errno.ENOENT:
                    _check_acl(8)
                else:
                    with self.assertRaisesRegex(SecurityError, "^ACL_CHECK_FAILED$"):
                        _check_acl(8)

    @unittest.skipUnless(sys.platform == "darwin", "native read-only macOS check")
    def test_actual_native_acl_read_only(self):
        descriptor = os.open("/", os.O_RDONLY)
        try:
            _check_acl(descriptor)
        finally:
            os.close(descriptor)

    @unittest.skipUnless(sys.platform == "darwin", "native read-only macOS preflight")
    def test_actual_private_root_preflight_does_not_create_missing_target(self):
        # No patched security guard: exercise real dirfd, ownership and ACLs.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "checkout").mkdir(mode=0o700)
            target = root / "Application Support" / "Memory Kit" / "sample"
            assert_private_root(target, root / "checkout", os.getuid())
            self.assertFalse((root / "Application Support").exists())
            ensure_private_directory(target, os.getuid())
            assert_private_root(target, root / "checkout", os.getuid())

    @unittest.skipUnless(sys.platform == "darwin", "native read-only macOS preflight")
    def test_actual_missing_root_still_rejects_unsafe_ancestor_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "checkout").mkdir(mode=0o700)
            unsafe = root / "unsafe"
            unsafe.mkdir(mode=0o777)
            unsafe.chmod(0o777)
            with self.assertRaisesRegex(SecurityError, "^UNSAFE_ANCESTOR_MODE$"):
                assert_private_root(unsafe / "missing", root / "checkout", os.getuid())
            safe = root / "safe"
            safe.mkdir(mode=0o700)
            link = root / "link"
            link.symlink_to(safe, target_is_directory=True)
            with self.assertRaises(SecurityError):
                assert_private_root(link / "missing", root / "checkout", os.getuid())
            self.assertFalse((unsafe / "missing").exists())
            self.assertFalse((safe / "missing").exists())

    @unittest.skipUnless(sys.platform == "darwin", "native macOS case-alias check")
    def test_actual_checkout_case_alias_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            checkout = root / "CheckOut"
            checkout.mkdir(mode=0o700)
            alias = root / "cHECKoUT"
            if not alias.exists():
                self.skipTest("fixture volume is case sensitive")
            self.assertNotEqual(str(checkout), str(alias))
            with self.assertRaisesRegex(SecurityError, "^PRIVATE_ROOT_IN_CHECKOUT$"):
                assert_private_root(alias / "private", checkout, os.getuid())
            self.assertFalse((checkout / "private").exists())


class VolumeTests(unittest.TestCase):
    def test_native_header_layout_and_ownership_flags(self):
        self.assertEqual(ctypes.sizeof(_DarwinStatFS64), 2168)
        self.assertEqual(_DarwinStatFS64.f_flags.offset, 64)
        for flags, status, expected in ((0, 0, None), (0x00200000, 0, "OWNERSHIP_DISABLED_VOLUME"),
                                         (0, -1, "VOLUME_CHECK_FAILED")):
            with self.subTest(flags=flags, status=status):
                def get_volume(fd, output):
                    ctypes.cast(output, ctypes.POINTER(_DarwinStatFS64))[0].f_flags = flags
                    return status
                libc = SimpleNamespace(fstatfs64=Callable(get_volume))
                with patch("memory_kit.security.sys.platform", "darwin"), \
                        patch("memory_kit.security.ctypes.CDLL", return_value=libc):
                    if expected:
                        with self.assertRaisesRegex(SecurityError, "^" + expected + "$"):
                            _check_volume(8)
                    else:
                        _check_volume(8)

    @unittest.skipUnless(sys.platform == "darwin", "native read-only macOS volume check")
    def test_actual_native_root_volume(self):
        descriptor = os.open("/", os.O_RDONLY)
        try:
            _check_volume(descriptor)
        finally:
            os.close(descriptor)


if __name__ == "__main__":
    unittest.main()
