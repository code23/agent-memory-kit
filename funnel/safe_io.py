"""One shared symlink-safe file writer, used by memory.py, capture.py and router/build_index.py.

A write is refused (ValueError) when the target file is a symlink, or when a parent
directory is a symlink. With `root`, every directory between root and the file is checked;
without it, the immediate parent is checked. The final open uses O_NOFOLLOW so a swap
after the check cannot be followed.
"""
import os
from pathlib import Path


class UnsafePathError(OSError, ValueError):
    """Refused write. Both an OSError and a ValueError so existing handlers keep working."""


def assert_not_symlinked(path, root=None):
    path = Path(path)
    if os.path.islink(path):
        raise UnsafePathError(f"refusing symlink: {path}")
    parents = [path.parent]
    if root is not None:
        try:
            rel = path.parent.relative_to(root)
            cur = Path(root)
            parents = []
            for part in rel.parts:
                cur = cur / part
                parents.append(cur)
        except ValueError:
            parents = [path.parent]
    for d in parents:
        if os.path.islink(d):
            raise UnsafePathError(f"refusing symlinked directory: {d}")


def write_text(path, text, root=None, append=False, fsync=False, mode=0o644):
    """Write (or append) text without following symlinks. Raises ValueError if unsafe."""
    path = Path(path)
    assert_not_symlinked(path, root)
    flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    flags |= os.O_APPEND if append else os.O_TRUNC
    try:
        fd = os.open(str(path), flags, mode)
    except OSError as e:
        raise UnsafePathError(f"refusing unsafe write: {path} ({e})") from e
    try:
        data = text.encode("utf-8")
        view = memoryview(data)
        total = 0
        while total < len(data):
            n = os.write(fd, view[total:])
            if n <= 0:
                raise OSError(f"short write: {path}")
            total += n
        if fsync:
            os.fsync(fd)
    finally:
        os.close(fd)
