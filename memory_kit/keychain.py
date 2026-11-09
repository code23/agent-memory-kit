"""Create-only generic passwords through Apple's native Keychain API.

Secret bytes never cross a subprocess boundary. A different stored value is a
conflict, not permission to rotate or overwrite an existing installation.
"""

import ctypes
import hmac
import re
import sys
from typing import Optional


class SecretStoreError(RuntimeError):
    """A safe, fixed diagnostic; never includes native output or secret bytes."""


def validate_instance(value: str) -> str:
    """Validate the shared Keychain namespace before any binding mutation."""
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,39}", value):
        raise SecretStoreError("KEYCHAIN_INVALID_INSTANCE")
    return value


class _NativeKeychain:
    NOT_FOUND = -25300
    DUPLICATE = -25299

    def __init__(self, security=None, core_foundation=None):
        if security is None:
            if sys.platform != "darwin":
                raise SecretStoreError("KEYCHAIN_MACOS_REQUIRED")
            try:
                security = ctypes.CDLL(
                    "/System/Library/Frameworks/Security.framework/Security"
                )
                core_foundation = ctypes.CDLL(
                    "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
                )
            except OSError:
                raise SecretStoreError("KEYCHAIN_UNAVAILABLE") from None
        self.security = security
        self.cf = core_foundation
        pointer = ctypes.c_void_p
        uint = ctypes.c_uint32
        security.SecKeychainFindGenericPassword.argtypes = [
            pointer, uint, pointer, uint, pointer,
            ctypes.POINTER(uint), ctypes.POINTER(pointer), ctypes.POINTER(pointer),
        ]
        security.SecKeychainFindGenericPassword.restype = ctypes.c_int32
        security.SecKeychainAddGenericPassword.argtypes = [
            pointer, uint, pointer, uint, pointer, uint, pointer,
            ctypes.POINTER(pointer),
        ]
        security.SecKeychainAddGenericPassword.restype = ctypes.c_int32
        security.SecKeychainItemFreeContent.argtypes = [pointer, pointer]
        security.SecKeychainItemFreeContent.restype = ctypes.c_int32
        self.cf.CFRelease.argtypes = [pointer]
        self.cf.CFRelease.restype = None

    def check_ready(self) -> None:
        self.security.SecKeychainCopyDefault.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        self.security.SecKeychainCopyDefault.restype = ctypes.c_int32
        self.security.SecKeychainGetStatus.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        self.security.SecKeychainGetStatus.restype = ctypes.c_int32
        keychain = ctypes.c_void_p()
        flags = ctypes.c_uint32()
        try:
            if self.security.SecKeychainCopyDefault(ctypes.byref(keychain)) != 0 or not keychain.value:
                raise SecretStoreError("KEYCHAIN_UNAVAILABLE")
            if self.security.SecKeychainGetStatus(keychain, ctypes.byref(flags)) != 0:
                raise SecretStoreError("KEYCHAIN_READINESS_FAILED")
            if not flags.value & 1:
                raise SecretStoreError("KEYCHAIN_LOCKED")
            if flags.value & 6 != 6:
                raise SecretStoreError("KEYCHAIN_PERMISSION_DENIED")
        finally:
            if keychain.value:
                self.cf.CFRelease(keychain)

    def find(self, service: bytes, account: bytes) -> Optional[bytes]:
        length = ctypes.c_uint32()
        data = ctypes.c_void_p()
        item = ctypes.c_void_p()
        try:
            status = self.security.SecKeychainFindGenericPassword(
                None, len(service), service, len(account), account,
                ctypes.byref(length), ctypes.byref(data), ctypes.byref(item),
            )
            if status == self.NOT_FOUND:
                return None
            if status != 0:
                raise SecretStoreError("KEYCHAIN_READ_FAILED")
            if length.value and not data.value:
                raise SecretStoreError("KEYCHAIN_READ_FAILED")
            return ctypes.string_at(data, length.value) if length.value else b""
        finally:
            if data.value:
                self.security.SecKeychainItemFreeContent(None, data)
            if item.value:
                self.cf.CFRelease(item)

    def add(self, service: bytes, account: bytes, value: bytes) -> None:
        item = ctypes.c_void_p()
        try:
            status = self.security.SecKeychainAddGenericPassword(
                None, len(service), service, len(account), account,
                len(value), value, ctypes.byref(item),
            )
            if status == self.DUPLICATE:
                raise SecretStoreError("KEYCHAIN_VALUE_CONFLICT")
            if status != 0:
                raise SecretStoreError("KEYCHAIN_WRITE_FAILED")
        finally:
            if item.value:
                self.cf.CFRelease(item)


class MacKeychain:
    """An injectable store; the default backend is native and macOS-only."""

    def __init__(self, backend=None):
        self._backend = backend if backend is not None else _NativeKeychain()

    def check_ready(self) -> None:
        """Check store status without item reads, writes or unlock attempts.

        This is a point-in-time check. It cannot prove an individual item's ACL
        permits access, or guarantee the store remains unlocked for a later put.
        """
        try:
            self._backend.check_ready()
        except SecretStoreError:
            raise
        except Exception:
            raise SecretStoreError("KEYCHAIN_READINESS_FAILED") from None

    @staticmethod
    def _names(instance: str, key: str):
        validate_instance(instance)
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9_-]{1,64}", key):
            raise SecretStoreError("KEYCHAIN_INVALID_KEY")
        return ("org.code23.agent-memory-kit." + instance).encode("ascii"), key.encode("ascii")

    def get(self, instance: str, key: str) -> Optional[bytes]:
        service, account = self._names(instance, key)
        try:
            value = self._backend.find(service, account)
            if value is not None and not isinstance(value, bytes):
                raise SecretStoreError("KEYCHAIN_READ_FAILED")
            return value
        except SecretStoreError:
            raise
        except Exception:
            raise SecretStoreError("KEYCHAIN_READ_FAILED") from None

    def put(self, instance: str, key: str, value: bytes) -> None:
        if not isinstance(value, bytes) or not value:
            raise SecretStoreError("KEYCHAIN_INVALID_VALUE")
        service, account = self._names(instance, key)
        existing = self.get(instance, key)
        if existing is not None:
            if hmac.compare_digest(existing, value):
                return
            raise SecretStoreError("KEYCHAIN_VALUE_CONFLICT")
        try:
            self._backend.add(service, account, value)
        except SecretStoreError:
            raise
        except Exception:
            raise SecretStoreError("KEYCHAIN_WRITE_FAILED") from None
