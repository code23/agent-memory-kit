"""Fail-closed filesystem and local-account checks for the Mac installer."""

import ctypes
import errno
import grp
import os
from pathlib import Path
import pwd
import re
import stat
import sys
from contextlib import contextmanager


class SecurityError(RuntimeError):
    """Fixed diagnostic codes, without local names or filesystem paths."""


@contextmanager
def public_directory(path, owner_uid, identity):
    """Anchor readable operator metadata; never relax private/project checks."""
    path = _absolute(Path(path))
    descriptors, snapshots = [], []
    try:
        fd = os.open("/", _open_flags())
        descriptors.append(fd)
        current = Path("/")
        for part in (None,) + path.parts[1:]:
            if part is not None:
                current /= part
                fd = os.open(part, _open_flags(), dir_fd=fd)
                descriptors.append(fd)
            info = os.fstat(fd)
            _check_volume(fd)
            _check_acl(fd)
            if (info.st_uid not in (0, owner_uid) or info.st_uid == identity["uid"]
                    or info.st_mode & 0o022):
                raise SecurityError("UNPROTECTED_CONTEXT_ANCESTOR")
            snapshots.append((current, info.st_dev, info.st_ino))
        if os.fstat(fd).st_uid != owner_uid:
            raise SecurityError("CONTEXT_OWNER_CHANGED")
        def unchanged():
            for name, device, inode in snapshots:
                info = os.lstat(name)
                if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != (device, inode):
                    raise SecurityError("CONTEXT_PARENT_REPLACED")
        unchanged()
    except OSError:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise SecurityError("CONTEXT_AUTHORITY_UNAVAILABLE") from None
    except BaseException:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise
    try:
        yield fd
        unchanged()
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def public_file_at(directory, name, owner_uid, limit=4 * 1024 * 1024):
    """Read a single no-follow regular inode owned by the delegated operator."""
    if Path(name).name != name or name in (".", ".."):
        raise SecurityError("CONTEXT_INVALID_NAME")
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        info = os.fstat(fd)
        _check_volume(fd)
        _check_acl(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner_uid
                or info.st_nlink != 1 or info.st_mode & 0o022 or info.st_size > limit):
            raise SecurityError("CONTEXT_METADATA_UNSAFE")
        data = b""
        while len(data) <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data += chunk
        after = os.fstat(fd)
        named = os.stat(name, dir_fd=directory, follow_symlinks=False)
        if (len(data) > limit or len(data) != info.st_size
                or (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_uid, info.st_mode)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_uid, after.st_mode)
                or (info.st_dev, info.st_ino) != (named.st_dev, named.st_ino)):
            raise SecurityError("CONTEXT_METADATA_REPLACED")
        return data, fd, info
    except BaseException:
        os.close(fd)
        raise


class _DarwinStatFS64(ctypes.Structure):
    # Darwin sys/mount.h __DARWIN_STRUCT_STATFS64; explicit fstatfs64 ABI.
    # Native SDK probe verifies size 2168, f_flags offset 64, MAXPATHLEN 1024.
    _fields_ = [
        ("f_bsize", ctypes.c_uint32), ("f_iosize", ctypes.c_int32),
        ("f_blocks", ctypes.c_uint64), ("f_bfree", ctypes.c_uint64),
        ("f_bavail", ctypes.c_uint64), ("f_files", ctypes.c_uint64),
        ("f_ffree", ctypes.c_uint64), ("f_fsid", ctypes.c_int32 * 2),
        ("f_owner", ctypes.c_uint32), ("f_type", ctypes.c_uint32),
        ("f_flags", ctypes.c_uint32), ("f_fssubtype", ctypes.c_uint32),
        ("f_fstypename", ctypes.c_char * 16),
        ("f_mntonname", ctypes.c_char * 1024),
        ("f_mntfromname", ctypes.c_char * 1024),
        ("f_flags_ext", ctypes.c_uint32), ("f_reserved", ctypes.c_uint32 * 7),
    ]


def _check_volume(fd: int) -> None:
    """Ownership comparisons are meaningful only on ownership-enforcing mounts."""
    if sys.platform != "darwin":
        raise SecurityError("MACOS_REQUIRED")
    try:
        libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        libc.fstatfs64.argtypes = [ctypes.c_int, ctypes.POINTER(_DarwinStatFS64)]
        libc.fstatfs64.restype = ctypes.c_int
        volume = _DarwinStatFS64()
        if libc.fstatfs64(fd, ctypes.byref(volume)) != 0:
            raise SecurityError("VOLUME_CHECK_FAILED")
        if volume.f_flags & 0x00200000:  # sys/mount.h MNT_IGNORE_OWNERSHIP
            raise SecurityError("OWNERSHIP_DISABLED_VOLUME")
    except SecurityError:
        raise
    except (OSError, AttributeError, TypeError):
        raise SecurityError("VOLUME_CHECK_FAILED") from None


def validate_workspace(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]{1,39}", value):
        raise SecurityError("INVALID_WORKSPACE")
    if re.fullmatch(r"[0-9a-f]{32}", value):
        raise SecurityError("INVALID_WORKSPACE")
    return value


def _absolute(path: Path) -> Path:
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or path == Path("/"):
        raise SecurityError("UNSAFE_PATH")
    return path


def _check_acl(fd: int, private: bool = False) -> None:
    """Reject unprovable ACL grants; harmless read grants on ancestors are OK.

    Darwin's ACL iterator returns -1/EINVAL at the end, unlike Linux's API.
    Descriptor-based inspection binds the ACL to the inode already checked.
    """
    if sys.platform != "darwin":
        raise SecurityError("MACOS_REQUIRED")
    try:
        libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        ptr = ctypes.c_void_p
        libc.acl_get_fd_np.argtypes = [ctypes.c_int, ctypes.c_int]
        libc.acl_get_fd_np.restype = ptr
        libc.acl_get_entry.argtypes = [ptr, ctypes.c_int, ctypes.POINTER(ptr)]
        libc.acl_get_entry.restype = ctypes.c_int
        libc.acl_get_tag_type.argtypes = [ptr, ctypes.POINTER(ctypes.c_int)]
        libc.acl_get_tag_type.restype = ctypes.c_int
        libc.acl_get_permset_mask_np.argtypes = [ptr, ctypes.POINTER(ctypes.c_uint64)]
        libc.acl_get_permset_mask_np.restype = ctypes.c_int
        libc.acl_free.argtypes = [ptr]
        libc.acl_free.restype = ctypes.c_int
        ctypes.set_errno(0)
        acl = libc.acl_get_fd_np(fd, 0x100)
        if not acl:
            # Darwin returns ENOENT when this open inode has no extended ACL.
            # It cannot refer to a missing pathname: we supplied a live fd.
            if ctypes.get_errno() == errno.ENOENT:
                return
            raise SecurityError("ACL_CHECK_FAILED")
        try:
            selector = 0  # ACL_FIRST_ENTRY
            while True:
                entry = ptr()
                ctypes.set_errno(0)
                result = libc.acl_get_entry(acl, selector, ctypes.byref(entry))
                if result == -1 and ctypes.get_errno() == errno.EINVAL:
                    break
                if result != 0:
                    raise SecurityError("ACL_CHECK_FAILED")
                selector = -1  # ACL_NEXT_ENTRY
                tag = ctypes.c_int()
                permissions = ctypes.c_uint64()
                if libc.acl_get_tag_type(entry, ctypes.byref(tag)) != 0:
                    raise SecurityError("ACL_CHECK_FAILED")
                if tag.value == 2:  # ACL_EXTENDED_DENY cannot grant access.
                    continue
                if tag.value != 1 or libc.acl_get_permset_mask_np(entry, ctypes.byref(permissions)) != 0:
                    raise SecurityError("ACL_CHECK_FAILED")
                readonly = sum(1 << bit for bit in (1, 3, 7, 9, 11, 20))
                if private or permissions.value & ~readonly:
                    raise SecurityError("UNSAFE_ACL")
        finally:
            libc.acl_free(acl)
    except SecurityError:
        raise
    except (OSError, AttributeError, TypeError):
        raise SecurityError("ACL_CHECK_FAILED") from None


def _open_flags() -> int:
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise SecurityError("SAFE_PATH_API_REQUIRED")
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY


def _safe_ancestor(info, owner_uid: int) -> None:
    if info.st_uid not in (0, owner_uid):
        raise SecurityError("UNSAFE_ANCESTOR_OWNER")
    writable = info.st_mode & 0o022
    sticky_root = info.st_uid == 0 and info.st_mode & stat.S_ISVTX
    if writable and not sticky_root:
        raise SecurityError("UNSAFE_ANCESTOR_MODE")


def _private_directory(path: Path, owner_uid: int, create: bool, checkout_identity=None) -> None:
    path = _absolute(path)
    if not isinstance(owner_uid, int) or owner_uid < 1:
        raise SecurityError("INVALID_OWNER")
    descriptors = []
    snapshots = []
    try:
        fd = os.open("/", _open_flags())
        descriptors.append(fd)
        _check_volume(fd)
        current = Path("/")
        for index, component in enumerate(path.parts[1:]):
            parent = os.fstat(fd)
            if (parent.st_dev, parent.st_ino) == checkout_identity:
                raise SecurityError("PRIVATE_ROOT_IN_CHECKOUT")
            _safe_ancestor(parent, owner_uid)
            _check_acl(fd)
            current = current / component
            last = index == len(path.parts) - 2
            try:
                child = os.open(component, _open_flags(), dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    # A read-only preflight may inspect a fresh install. The
                    # existing parent was validated above; creation performs
                    # the same walk again and checks every new component.
                    break
                # mkdir is relative to the verified parent; never follows a link.
                os.mkdir(component, 0o700, dir_fd=fd)
                child = os.open(component, _open_flags(), dir_fd=fd)
            fd = child
            descriptors.append(fd)
            _check_volume(fd)
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino) == checkout_identity:
                raise SecurityError("PRIVATE_ROOT_IN_CHECKOUT")
            snapshots.append((current, info.st_dev, info.st_ino))
            if last:
                if info.st_uid != owner_uid or stat.S_IMODE(info.st_mode) != 0o700:
                    raise SecurityError("PRIVATE_ROOT_PERMISSIONS")
                _check_acl(fd, private=True)
        # Detect replacement while walking. Operations must also use no-follow
        # opens; this assertion is deliberately not a write authorization token.
        for current, device, inode in snapshots:
            info = os.lstat(current)
            if stat.S_ISLNK(info.st_mode) or (info.st_dev, info.st_ino) != (device, inode):
                raise SecurityError("PATH_REPLACED")
    except SecurityError:
        raise
    except OSError:
        raise SecurityError("UNSAFE_PATH") from None
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def ensure_private_directory(path: Path, owner_uid: int) -> None:
    """Create private directories; reject existing unsafe directories unchanged."""
    _private_directory(path, owner_uid, create=True)


def assert_private_root(path: Path, kit_root: Path, owner_uid: int) -> None:
    """Read-only preflight for an existing root or its safe existing ancestors."""
    path = _absolute(path)
    try:
        kit_root = Path(kit_root).resolve(strict=True)
        descriptor = os.open(kit_root, _open_flags())
        try:
            _check_volume(descriptor)
            info = os.fstat(descriptor)
            checkout_identity = (info.st_dev, info.st_ino)
        finally:
            os.close(descriptor)
    except OSError:
        raise SecurityError("CHECKOUT_UNAVAILABLE") from None
    _private_directory(path, owner_uid, create=False, checkout_identity=checkout_identity)


def standard_coding_identity(name: str) -> dict:
    """Resolve a standard account, including current directory-service groups."""
    if not isinstance(name, str) or not name or "\x00" in name:
        raise SecurityError("CODING_ACCOUNT_REQUIRED")
    try:
        account = pwd.getpwnam(name)
        if account.pw_uid < 501:
            raise SecurityError("STANDARD_CODING_ACCOUNT_REQUIRED")
        groups = set(os.getgrouplist(account.pw_name, account.pw_gid))
        # Include the primary group explicitly even on unusual directory services.
        groups.add(account.pw_gid)
        if groups & {0, 80}:
            raise SecurityError("STANDARD_CODING_ACCOUNT_REQUIRED")
        for group_id in groups:
            grp.getgrgid(group_id)
        return {"name": account.pw_name, "uid": account.pw_uid,
                "gid": account.pw_gid, "groups": sorted(groups)}
    except SecurityError:
        raise
    except (KeyError, OSError, ValueError):
        raise SecurityError("CODING_ACCOUNT_UNAVAILABLE") from None


def coding_identity(name: str, current_uid: int) -> dict:
    """Resolve only the explicitly selected separate local coding account."""
    identity = standard_coding_identity(name)
    if identity["uid"] == current_uid:
        raise SecurityError("SEPARATE_CODING_ACCOUNT_REQUIRED")
    return identity


def assert_not_agent_writable(path: Path, identity: dict) -> None:
    """Check the object and every ancestor, including native ACL mutation grants."""
    path = _absolute(path)
    try:
        uid = identity["uid"]
        groups = set(identity["groups"])
        groups.add(identity["gid"])
        if not isinstance(uid, int) or uid < 501:
            raise SecurityError("INVALID_CODING_IDENTITY")
        if groups & {0, 80}:
            raise SecurityError("STANDARD_CODING_ACCOUNT_REQUIRED")
        descriptors = []
        snapshots = []
        try:
            fd = os.open("/", _open_flags())
            descriptors.append(fd)
            current = Path("/")
            for component in (None,) + path.parts[1:]:
                if component is not None:
                    current = current / component
                    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
                    if current != path:
                        flags |= os.O_DIRECTORY
                    fd = os.open(component, flags, dir_fd=fd)
                    descriptors.append(fd)
                info = os.fstat(fd)
                _check_volume(fd)
                if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                    raise SecurityError("UNSAFE_SOFTWARE_TYPE")
                snapshots.append((current, info.st_dev, info.st_ino))
                # An owner can chmod their inode even when write is currently
                # disabled, including on an ancestor used to replace software.
                if (info.st_uid == uid
                        or info.st_gid in groups and info.st_mode & 0o020
                        or info.st_mode & 0o002):
                    raise SecurityError("AGENT_WRITABLE_SOFTWARE")
                _check_acl(fd)
            for current, device, inode in snapshots:
                info = os.lstat(current)
                if stat.S_ISLNK(info.st_mode) or (info.st_dev, info.st_ino) != (device, inode):
                    raise SecurityError("PATH_REPLACED")
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
    except SecurityError:
        raise
    except (OSError, KeyError, TypeError, ValueError):
        raise SecurityError("SOFTWARE_CHECK_FAILED") from None
