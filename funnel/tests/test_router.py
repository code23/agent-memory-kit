#!/usr/bin/env python3
"""Behaviour tests for model-free route.py (synthetic fixtures only)."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "router"))

import route  # noqa: E402


def _write_index(idxdir: Path, entries: list[tuple[str, str]]) -> None:
    lines = ["# Vault router index (auto-generated)\n", "\n"]
    for title, summary in entries:
        lines.append(f"- {title} :: {summary}\n")
    (idxdir / "router-index.md").write_text("".join(lines), encoding="utf-8")


def _write_map(idxdir: Path, mapping: dict[str, str]) -> None:
    (idxdir / "router-map.json").write_text(
        json.dumps(mapping, indent=2), encoding="utf-8"
    )


def _fixture(notes: dict[str, tuple[str, str]], *, relative: bool = False):
    """notes: title -> (summary, body). Returns (idxdir, notes_dir, cleanup)."""
    tmp = tempfile.TemporaryDirectory()
    idxdir = Path(tmp.name) / "index"
    notes_dir = Path(tmp.name) / "notes"
    idxdir.mkdir()
    notes_dir.mkdir()
    entries = []
    mapping = {}
    for title, (summary, body) in notes.items():
        path = notes_dir / f"{title}.md"
        path.write_text(body, encoding="utf-8")
        entries.append((title, summary))
        mapping[title] = (
            os.path.relpath(path, idxdir) if relative else str(path.resolve())
        )
    _write_index(idxdir, entries)
    _write_map(idxdir, mapping)
    return idxdir, notes_dir, tmp


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
        code = route.main(argv)
    return code, out.getvalue(), err.getvalue()


class TestExactAndDescriptive(unittest.TestCase):
    def test_exact_title_legacy_output(self):
        idxdir, notes_dir, tmp = _fixture(
            {
                "Model Routing": (
                    "how agents pick which model to use for a task",
                    "# Model Routing\n\nUse the cheapest capable model.\n",
                ),
                "Email Drafts": (
                    "how to draft replies in the email client",
                    "# Email\n\nDraft only.\n",
                ),
            }
        )
        self.addCleanup(tmp.cleanup)
        code, out, err = _run(
            ["--indexdir", str(idxdir), "Model Routing"]
        )
        self.assertEqual(code, 0, err)
        line = out.strip().splitlines()[0]
        title, path = line.split("\t", 1)
        self.assertEqual(title, "Model Routing")
        self.assertEqual(path, str((notes_dir / "Model Routing.md").resolve()))
        self.assertTrue(Path(path).is_absolute())

    def test_descriptive_multiword_retrieval(self):
        idxdir, notes_dir, tmp = _fixture(
            {
                "Model Routing": (
                    "policy for choosing which local or remote model an agent should use",
                    "body A",
                ),
                "Calendar Prep": (
                    "meeting preparation one hour before client calls",
                    "body B",
                ),
                "Vault Lint": (
                    "notes with weak summaries needing curation",
                    "body C",
                ),
            }
        )
        self.addCleanup(tmp.cleanup)
        code, out, err = _run(
            [
                "--indexdir",
                str(idxdir),
                "which model should an agent use for routing policy",
            ]
        )
        self.assertEqual(code, 0, err)
        self.assertTrue(out.startswith("Model Routing\t"), out)


class TestTiesAndNoMatch(unittest.TestCase):
    def test_exact_top_score_tie_is_ambiguous(self):
        # Identical summaries + shared query tokens → identical BM25 scores.
        idxdir, _, tmp = _fixture(
            {
                "Alpha Note": ("shared widget protocol details", "a"),
                "Beta Note": ("shared widget protocol details", "b"),
                "Unrelated": ("gardening tips for spring", "c"),
            }
        )
        self.addCleanup(tmp.cleanup)
        code, out, err = _run(
            ["--indexdir", str(idxdir), "shared widget protocol"]
        )
        self.assertEqual(code, 2)
        self.assertIn("AMBIGUOUS", err)
        self.assertEqual(out, "")

    def test_no_relevance_nonzero(self):
        idxdir, _, tmp = _fixture(
            {
                "Alpha": ("quantum flute maintenance", "a"),
                "Beta": ("underwater basket weaving", "b"),
            }
        )
        self.addCleanup(tmp.cleanup)
        code, out, err = _run(
            ["--indexdir", str(idxdir), "zzzzzy unrelated tango xylophone"]
        )
        self.assertEqual(code, 2)
        self.assertIn("NONE", err)
        self.assertEqual(out, "")


class TestMissingMalformed(unittest.TestCase):
    def test_missing_index(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        _write_map(idxdir, {"A": "/tmp/a.md"})
        code, _, err = _run(["--indexdir", str(idxdir), "A"])
        self.assertEqual(code, 2)
        self.assertIn("missing index", err.lower())

    def test_missing_map(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        _write_index(idxdir, [("A", "summary about apples")])
        code, _, err = _run(["--indexdir", str(idxdir), "A"])
        self.assertEqual(code, 2)
        self.assertIn("missing map", err.lower())

    def test_malformed_index_line(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        (idxdir / "router-index.md").write_text(
            "# idx\n\n- NoDelimiter here\n", encoding="utf-8"
        )
        _write_map(idxdir, {"NoDelimiter here": "/tmp/x.md"})
        code, _, err = _run(["--indexdir", str(idxdir), "anything useful"])
        self.assertEqual(code, 2)
        self.assertIn("malformed", err.lower())

    def test_duplicate_titles_in_index(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        (idxdir / "router-index.md").write_text(
            "- Dup :: first\n- Dup :: second\n", encoding="utf-8"
        )
        _write_map(idxdir, {"Dup": "/tmp/x.md"})
        code, _, err = _run(["--indexdir", str(idxdir), "Dup"])
        self.assertEqual(code, 2)
        self.assertIn("duplicate", err.lower())

    def test_invalid_map_shape(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        _write_index(idxdir, [("A", "alpha summary text")])
        (idxdir / "router-map.json").write_text("[1, 2, 3]", encoding="utf-8")
        code, _, err = _run(["--indexdir", str(idxdir), "A"])
        self.assertEqual(code, 2)
        self.assertIn("json object", err.lower())

    def test_oversized_index_rejected(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        big = "# idx\n\n- T :: " + ("word " * 100) + "\n"
        # Force size check via patched limit for speed.
        (idxdir / "router-index.md").write_text(big, encoding="utf-8")
        _write_map(idxdir, {"T": "/tmp/t.md"})
        with mock.patch.object(route, "MAX_INDEX_BYTES", 20):
            code, _, err = _run(["--indexdir", str(idxdir), "T"])
        self.assertEqual(code, 2)
        self.assertIn("too large", err.lower())

    def test_index_read_is_byte_capped(self):
        """Regression: open+read(limit+1), not Path.read_bytes of the whole file."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        idx = idxdir / "router-index.md"
        idx.write_bytes(b"x" * 5000)
        _write_map(idxdir, {"T": "/tmp/t.md"})
        cap = 100
        read_sizes: list[int] = []
        real_open = open

        def tracking_open(path, *a, **kw):
            f = real_open(path, *a, **kw)
            if Path(path).resolve() == idx.resolve() and "b" in (a[0] if a else kw.get("mode", "r")):
                real_read = f.read

                def capped_read(n=-1):
                    read_sizes.append(n)
                    return real_read(n)

                f.read = capped_read  # type: ignore[method-assign]
            return f

        with mock.patch.object(route, "MAX_INDEX_BYTES", cap):
            with mock.patch("builtins.open", tracking_open):
                code, _, err = _run(["--indexdir", str(idxdir), "T"])
        self.assertEqual(code, 2)
        self.assertIn("too large", err.lower())
        self.assertIn(cap + 1, read_sizes)

    def test_malformed_json_map(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        _write_index(idxdir, [("A", "alpha summary text")])
        (idxdir / "router-map.json").write_text("{not json", encoding="utf-8")
        code, out, err = _run(["--indexdir", str(idxdir), "A"])
        self.assertEqual(code, 2)
        self.assertIn("invalid json", err.lower())
        self.assertEqual(out, "")

    def test_non_utf8_index_rejected(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        (idxdir / "router-index.md").write_bytes(b"- A :: bad\xff summary\n")
        _write_map(idxdir, {"A": "/tmp/a.md"})
        code, out, err = _run(["--indexdir", str(idxdir), "A"])
        self.assertEqual(code, 2)
        self.assertIn("utf-8", err.lower())
        self.assertEqual(out, "")

    def test_non_utf8_map_rejected(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        _write_index(idxdir, [("A", "alpha summary text")])
        (idxdir / "router-map.json").write_bytes(b'{"A": "/tmp/a.md"\xff}')
        code, out, err = _run(["--indexdir", str(idxdir), "A"])
        self.assertEqual(code, 2)
        self.assertIn("utf-8", err.lower())
        self.assertEqual(out, "")

    def test_exact_duplicate_json_keys_rejected(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        _write_index(idxdir, [("A", "alpha summary text")])
        (idxdir / "router-map.json").write_text(
            '{"A": "/tmp/a.md", "A": "/tmp/b.md"}', encoding="utf-8"
        )
        code, out, err = _run(["--indexdir", str(idxdir), "A"])
        self.assertEqual(code, 2)
        self.assertIn("duplicate exact", err.lower())
        self.assertEqual(out, "")

    def test_casefold_duplicate_map_titles_rejected(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        _write_index(idxdir, [("Alpha", "alpha summary text")])
        (idxdir / "router-map.json").write_text(
            json.dumps({"Alpha": "/tmp/a.md", "alpha": "/tmp/b.md"}),
            encoding="utf-8",
        )
        code, out, err = _run(["--indexdir", str(idxdir), "Alpha"])
        self.assertEqual(code, 2)
        self.assertIn("duplicate", err.lower())
        self.assertEqual(out, "")

    def test_nonregular_index_rejected(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        # Directory named like the index file → not a regular file.
        (idxdir / "router-index.md").mkdir()
        _write_map(idxdir, {"A": "/tmp/a.md"})
        code, out, err = _run(["--indexdir", str(idxdir), "A"])
        self.assertEqual(code, 2)
        self.assertIn("regular", err.lower())
        self.assertEqual(out, "")

    def test_control_char_title_rejected(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        (idxdir / "router-index.md").write_text(
            "- Bad\tTitle :: summary about widgets\n", encoding="utf-8"
        )
        _write_map(idxdir, {"Bad\tTitle": "/tmp/x.md"})
        code, out, err = _run(["--indexdir", str(idxdir), "widgets"])
        self.assertEqual(code, 2)
        self.assertIn("control", err.lower())
        self.assertEqual(out, "")


class TestRootsAndRelative(unittest.TestCase):
    def test_relative_map_paths_resolve_against_indexdir(self):
        idxdir, notes_dir, tmp = _fixture(
            {
                "Rel Note": (
                    "relative path resolution example note",
                    "relative body\n",
                )
            },
            relative=True,
        )
        self.addCleanup(tmp.cleanup)
        # Ensure cwd is NOT the indexdir / notes parent.
        old = os.getcwd()
        os.chdir("/tmp")
        self.addCleanup(os.chdir, old)
        code, out, err = _run(
            ["--indexdir", str(idxdir), "Rel Note"]
        )
        self.assertEqual(code, 0, err)
        title, path = out.strip().split("\t", 1)
        self.assertEqual(title, "Rel Note")
        self.assertEqual(path, str((notes_dir / "Rel Note.md").resolve()))

    def test_allow_root_filters_before_ranking(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        idxdir = base / "index"
        allowed = base / "allowed"
        denied = base / "denied"
        idxdir.mkdir()
        allowed.mkdir()
        denied.mkdir()
        a = allowed / "Winner.md"
        d = denied / "Distractor.md"
        a.write_text("allowed body", encoding="utf-8")
        d.write_text("SECRET_SHOULD_NOT_BE_READ", encoding="utf-8")
        # Distractor is a better lexical match; root filter must remove it first.
        _write_index(
            idxdir,
            [
                ("Winner", "widget protocol notes for agents"),
                ("Distractor", "precise unique xylophone widget protocol handbook"),
            ],
        )
        _write_map(
            idxdir,
            {
                "Winner": str(a.resolve()),
                "Distractor": str(d.resolve()),
            },
        )
        code, out, err = _run(
            [
                "--indexdir",
                str(idxdir),
                "--allow-root",
                str(allowed),
                "precise unique xylophone widget protocol",
            ]
        )
        self.assertEqual(code, 0, err)
        self.assertTrue(out.startswith("Winner\t"), out)
        self.assertNotIn("Distractor", out)
        self.assertNotIn("SECRET", out)


class TestShowScopeAndSymlinks(unittest.TestCase):
    def test_show_requires_allow_root(self):
        idxdir, _, tmp = _fixture(
            {"N": ("note about something useful", "body")}
        )
        self.addCleanup(tmp.cleanup)
        code, out, err = _run(
            ["--indexdir", str(idxdir), "--show", "N"]
        )
        self.assertEqual(code, 2)
        self.assertIn("--allow-root", err)
        self.assertEqual(out, "")

    def test_show_reads_body_inside_scope(self):
        idxdir, notes_dir, tmp = _fixture(
            {"Scoped": ("scoped content note summary", "VISIBLE_BODY_OK\n")}
        )
        self.addCleanup(tmp.cleanup)
        code, out, err = _run(
            [
                "--indexdir",
                str(idxdir),
                "--show",
                "--allow-root",
                str(notes_dir),
                "Scoped",
            ]
        )
        self.assertEqual(code, 0, err)
        self.assertIn("Scoped\t", out)
        self.assertIn("VISIBLE_BODY_OK", out)

    def _guard_note_reads(self, note: Path):
        """Patch open / Path.read_* so denied note bodies cannot be touched."""
        note_r = note.resolve()
        real_open = open
        real_read_bytes = Path.read_bytes
        real_read_text = Path.read_text

        def guarded_open(path, *a, **kw):
            if Path(path).resolve() == note_r:
                raise AssertionError(f"body read attempted on denied path: {path}")
            return real_open(path, *a, **kw)

        def guarded_read_bytes(self):
            if self.resolve() == note_r:
                raise AssertionError("Path.read_bytes on denied note")
            return real_read_bytes(self)

        def guarded_read_text(self, *a, **kw):
            if self.resolve() == note_r:
                raise AssertionError("Path.read_text on denied note")
            return real_read_text(self, *a, **kw)

        return mock.patch("builtins.open", guarded_open), mock.patch.object(
            Path, "read_bytes", guarded_read_bytes
        ), mock.patch.object(Path, "read_text", guarded_read_text)

    def test_denied_show_does_not_read_body(self):
        """Winner outside allow-root after filter → no match; body never read."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        idxdir = base / "index"
        allowed = base / "allowed"
        other = base / "other"
        idxdir.mkdir()
        allowed.mkdir()
        other.mkdir()
        note = other / "Outside.md"
        note.write_text("SHOULD_NOT_READ", encoding="utf-8")
        _write_index(idxdir, [("Outside", "outside scoped note summary text")])
        _write_map(idxdir, {"Outside": str(note.resolve())})

        g_open, g_bytes, g_text = self._guard_note_reads(note)
        with g_open, g_bytes, g_text:
            code, out, err = _run(
                [
                    "--indexdir",
                    str(idxdir),
                    "--show",
                    "--allow-root",
                    str(allowed),
                    "Outside",
                ]
            )
        self.assertEqual(code, 2)
        self.assertNotIn("SHOULD_NOT_READ", out)
        self.assertTrue(
            "NONE" in err or "refused" in err.lower() or "no relevant" in err.lower()
        )

    def test_allow_root_filter_guards_denied_body_apis(self):
        """Root filter before ranking must not touch the denied note via any read API."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        idxdir = base / "index"
        allowed = base / "allowed"
        denied = base / "denied"
        idxdir.mkdir()
        allowed.mkdir()
        denied.mkdir()
        a = allowed / "Winner.md"
        d = denied / "Distractor.md"
        a.write_text("allowed body", encoding="utf-8")
        d.write_text("SECRET_SHOULD_NOT_BE_READ", encoding="utf-8")
        _write_index(
            idxdir,
            [
                ("Winner", "widget protocol notes for agents"),
                ("Distractor", "precise unique xylophone widget protocol handbook"),
            ],
        )
        _write_map(
            idxdir,
            {
                "Winner": str(a.resolve()),
                "Distractor": str(d.resolve()),
            },
        )
        g_open, g_bytes, g_text = self._guard_note_reads(d)
        with g_open, g_bytes, g_text:
            code, out, err = _run(
                [
                    "--indexdir",
                    str(idxdir),
                    "--allow-root",
                    str(allowed),
                    "precise unique xylophone widget protocol",
                ]
            )
        self.assertEqual(code, 0, err)
        self.assertTrue(out.startswith("Winner\t"), out)
        self.assertNotIn("SECRET", out)

    def test_symlink_escape_rejected_on_show(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        idxdir = base / "index"
        allowed = base / "allowed"
        secret_dir = base / "secret"
        idxdir.mkdir()
        allowed.mkdir()
        secret_dir.mkdir()
        secret = secret_dir / "Secret.md"
        secret.write_text("TOP_SECRET\n", encoding="utf-8")
        link = allowed / "Escape.md"
        link.symlink_to(secret)
        _write_index(idxdir, [("Escape", "symlink escape candidate note")])
        _write_map(idxdir, {"Escape": str(link)})

        code, out, err = _run(
            [
                "--indexdir",
                str(idxdir),
                "--show",
                "--allow-root",
                str(allowed),
                "Escape",
            ]
        )
        # Filtered before ranking (resolved target outside root) → no match,
        # or explicit refuse, either way body must not appear.
        self.assertEqual(code, 2)
        self.assertNotIn("TOP_SECRET", out)

    def test_oversized_note_rejected(self):
        idxdir, notes_dir, tmp = _fixture(
            {"Big": ("large note summary text here", "x")}
        )
        self.addCleanup(tmp.cleanup)
        big_path = notes_dir / "Big.md"
        big_path.write_bytes(b"y" * (route.MAX_NOTE_BYTES + 10))
        read_sizes: list[int] = []
        real_open = open

        def tracking_open(path, *a, **kw):
            f = real_open(path, *a, **kw)
            mode = a[0] if a else kw.get("mode", "r")
            if Path(path).resolve() == big_path.resolve() and "b" in mode:
                real_read = f.read

                def capped_read(n=-1):
                    read_sizes.append(n)
                    return real_read(n)

                f.read = capped_read  # type: ignore[method-assign]
            return f

        with mock.patch("builtins.open", tracking_open):
            code, out, err = _run(
                [
                    "--indexdir",
                    str(idxdir),
                    "--show",
                    "--allow-root",
                    str(notes_dir),
                    "Big",
                ]
            )
        self.assertEqual(code, 2)
        self.assertIn("exceeds", err.lower())
        self.assertNotIn("yyy", out)
        self.assertEqual(out, "")
        self.assertIn(route.NOTE_READ_CAP, read_sizes)

    def test_non_utf8_note_rejected(self):
        idxdir, notes_dir, tmp = _fixture(
            {"Bin": ("binary-ish note summary text", "placeholder")}
        )
        self.addCleanup(tmp.cleanup)
        (notes_dir / "Bin.md").write_bytes(b"ok\xff\xfe not utf8")
        code, out, err = _run(
            [
                "--indexdir",
                str(idxdir),
                "--show",
                "--allow-root",
                str(notes_dir),
                "Bin",
            ]
        )
        self.assertEqual(code, 2)
        self.assertIn("utf-8", err.lower())
        self.assertEqual(out, "")

    def test_missing_body_no_success_stdout(self):
        idxdir, notes_dir, tmp = _fixture(
            {"Gone": ("missing body note summary", "placeholder")}
        )
        self.addCleanup(tmp.cleanup)
        (notes_dir / "Gone.md").unlink()
        code, out, err = _run(
            [
                "--indexdir",
                str(idxdir),
                "--show",
                "--allow-root",
                str(notes_dir),
                "Gone",
            ]
        )
        self.assertEqual(code, 2)
        self.assertIn("does not exist", err.lower())
        self.assertEqual(out, "")

    def test_nonregular_body_rejected(self):
        idxdir, notes_dir, tmp = _fixture(
            {"DirNote": ("directory posing as note", "placeholder")}
        )
        self.addCleanup(tmp.cleanup)
        target = notes_dir / "DirNote.md"
        target.unlink()
        target.mkdir()
        code, out, err = _run(
            [
                "--indexdir",
                str(idxdir),
                "--show",
                "--allow-root",
                str(notes_dir),
                "DirNote",
            ]
        )
        self.assertEqual(code, 2)
        self.assertIn("regular", err.lower())
        self.assertEqual(out, "")

    def test_md_symlink_to_txt_rejected(self):
        idxdir, notes_dir, tmp = _fixture(
            {"Alias": ("markdown alias to plaintext", "placeholder")}
        )
        self.addCleanup(tmp.cleanup)
        txt = notes_dir / "real.txt"
        txt.write_text("NOT_MARKDOWN_BODY\n", encoding="utf-8")
        alias = notes_dir / "Alias.md"
        alias.unlink()
        alias.symlink_to(txt)
        code, out, err = _run(
            [
                "--indexdir",
                str(idxdir),
                "--show",
                "--allow-root",
                str(notes_dir),
                "Alias",
            ]
        )
        self.assertEqual(code, 2)
        self.assertIn("markdown", err.lower())
        self.assertNotIn("NOT_MARKDOWN_BODY", out)
        self.assertEqual(out, "")

    def test_show_body_failure_emits_no_metadata(self):
        """Failing body read must not print Title<TAB>path first."""
        idxdir, notes_dir, tmp = _fixture(
            {"FailBody": ("body read failure note", "placeholder")}
        )
        self.addCleanup(tmp.cleanup)
        (notes_dir / "FailBody.md").write_bytes(b"\xff\xfe")
        code, out, err = _run(
            [
                "--indexdir",
                str(idxdir),
                "--show",
                "--allow-root",
                str(notes_dir),
                "FailBody",
            ]
        )
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("utf-8", err.lower())

    def test_allow_root_must_be_existing_directory(self):
        idxdir, _, tmp = _fixture(
            {"N": ("note about something useful", "body")}
        )
        self.addCleanup(tmp.cleanup)
        code, out, err = _run(
            [
                "--indexdir",
                str(idxdir),
                "--allow-root",
                str(Path(tmp.name) / "no-such-root"),
                "N",
            ]
        )
        self.assertEqual(code, 2)
        self.assertIn("allow-root", err.lower())
        self.assertIn("directory", err.lower())
        self.assertEqual(out, "")


class TestModelJsonAndNoNetwork(unittest.TestCase):
    def test_model_flag_rejected(self):
        idxdir, _, tmp = _fixture(
            {"M": ("model flag rejection note", "body")}
        )
        self.addCleanup(tmp.cleanup)
        code, out, err = _run(
            ["--indexdir", str(idxdir), "--model", "gemma4:latest", "M"]
        )
        self.assertEqual(code, 2)
        self.assertIn("Ollama", err)
        self.assertIn("model-free", err.lower())
        self.assertEqual(out, "")

    def test_json_and_limit(self):
        idxdir, _, tmp = _fixture(
            {
                "One": ("alpha bravo charlie routing", "1"),
                "Two": ("alpha bravo something else", "2"),
                "Three": ("alpha only filler text", "3"),
                "Four": ("unrelated gardening tips", "4"),
            }
        )
        self.addCleanup(tmp.cleanup)
        code, out, err = _run(
            [
                "--indexdir",
                str(idxdir),
                "--json",
                "--limit",
                "2",
                "alpha bravo charlie",
            ]
        )
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["status"], "ok")
        self.assertLessEqual(len(payload["matches"]), 2)
        self.assertEqual(payload["matches"][0]["title"], "One")
        for m in payload["matches"]:
            self.assertIn("score", m)
            self.assertIn("why", m)
            self.assertNotIn("confidence", m)

    def test_limit_upper_bound_rejected(self):
        idxdir, _, tmp = _fixture(
            {"M": ("model free routing check note", "body")}
        )
        self.addCleanup(tmp.cleanup)
        code, out, err = _run(
            ["--indexdir", str(idxdir), "--json", "--limit", "999", "M"]
        )
        self.assertEqual(code, 2)
        self.assertIn("1", err)
        self.assertIn(str(route.MAX_LIMIT), err)
        self.assertEqual(out, "")

    def test_json_show_rejected_before_index_read(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name) / "missing-index-dir"
        # Combination must fail before any index/body IO.
        code, out, err = _run(
            [
                "--indexdir",
                str(idxdir),
                "--json",
                "--show",
                "--allow-root",
                str(tmp.name),
                "anything",
            ]
        )
        self.assertEqual(code, 2)
        self.assertIn("--json", err)
        self.assertIn("--show", err)
        self.assertNotIn("indexdir", err.lower())
        self.assertEqual(out, "")

    def test_ambiguous_message_is_bounded(self):
        notes = {
            f"Note{i:02d}": ("shared widget protocol details", f"b{i}")
            for i in range(15)
        }
        idxdir, _, tmp = _fixture(notes)
        self.addCleanup(tmp.cleanup)
        code, out, err = _run(
            ["--indexdir", str(idxdir), "shared widget protocol"]
        )
        self.assertEqual(code, 2)
        self.assertIn("AMBIGUOUS", err)
        self.assertIn("+", err)  # “… (+N more)”
        # Every title must not appear; message is capped.
        listed = err.count("Note")
        self.assertLessEqual(listed, route.MAX_AMBIGUOUS_TITLES)
        self.assertEqual(out, "")

    def test_zero_network_or_model_imports(self):
        # route.py must not import urllib / subprocess / requests.
        src = (ROOT / "router" / "route.py").read_text(encoding="utf-8")
        import_lines = [
            ln.strip()
            for ln in src.splitlines()
            if ln.lstrip().startswith(("import ", "from "))
        ]
        joined = "\n".join(import_lines).lower()
        self.assertNotIn("urllib", joined)
        self.assertNotIn("subprocess", joined)
        self.assertNotIn("requests", joined)
        self.assertNotRegex(src, r"(?m)^\s*(import|from)\s+urllib")
        self.assertNotRegex(src, r"(?m)^\s*(import|from)\s+subprocess")
        self.assertNotIn("localhost:11434", src)
        self.assertNotIn("api/generate", src)

        idxdir, _, tmp = _fixture(
            {"Net": ("network free routing check note", "body")}
        )
        self.addCleanup(tmp.cleanup)

        with mock.patch.dict(sys.modules, {"urllib": None, "urllib.request": None}):
            # Calling urlopen would fail; ensure main never touches it.
            with mock.patch("socket.socket") as sock:
                code, out, err = _run(
                    ["--indexdir", str(idxdir), "Net"]
                )
                sock.assert_not_called()
        self.assertEqual(code, 0, err)
        self.assertTrue(out.startswith("Net\t"), out)

    def test_metadata_only_does_not_open_note_bodies(self):
        idxdir, notes_dir, tmp = _fixture(
            {"Meta": ("metadata only search note", "BODY_SECRET")}
        )
        self.addCleanup(tmp.cleanup)
        note = (notes_dir / "Meta.md").resolve()
        real_open = open

        def guarded_open(path, *a, **kw):
            p = Path(path).resolve()
            if p == note:
                raise AssertionError("metadata search opened note body")
            return real_open(path, *a, **kw)

        with mock.patch("builtins.open", guarded_open):
            # Path.read_bytes / read_text also used, patch Path.read_bytes for notes.
            real_read_bytes = Path.read_bytes

            def guarded_read_bytes(self):
                if self.resolve() == note:
                    raise AssertionError("metadata search read note bytes")
                return real_read_bytes(self)

            with mock.patch.object(Path, "read_bytes", guarded_read_bytes):
                code, out, err = _run(
                    ["--indexdir", str(idxdir), "Meta"]
                )
        self.assertEqual(code, 0, err)
        self.assertNotIn("BODY_SECRET", out)


class TestNeverInventPath(unittest.TestCase):
    def test_index_title_missing_from_map(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        idxdir = Path(tmp.name)
        _write_index(idxdir, [("Present", "present note summary text")])
        _write_map(idxdir, {})  # empty map, must not invent
        code, _, err = _run(["--indexdir", str(idxdir), "Present"])
        self.assertEqual(code, 2)
        self.assertIn("never inventing", err.lower())


class TestFilesystemFailures(unittest.TestCase):
    def test_oserror_on_body_read_is_clean(self):
        idxdir, notes_dir, tmp = _fixture(
            {"Perm": ("permission failure note summary", "body")}
        )
        self.addCleanup(tmp.cleanup)
        note = (notes_dir / "Perm.md").resolve()
        real_open = open

        def boom_open(path, *a, **kw):
            mode = a[0] if a else kw.get("mode", "r")
            if Path(path).resolve() == note and "b" in mode:
                raise OSError(13, "Permission denied (synthetic)")
            return real_open(path, *a, **kw)

        with mock.patch("builtins.open", boom_open):
            code, out, err = _run(
                [
                    "--indexdir",
                    str(idxdir),
                    "--show",
                    "--allow-root",
                    str(notes_dir),
                    "Perm",
                ]
            )
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err.lower())
        self.assertEqual(out, "")
        self.assertNotIn("Traceback", err)

    def test_runtime_error_on_resolve_is_clean(self):
        idxdir, notes_dir, tmp = _fixture(
            {"Loop": ("symlink loop candidate note", "body")}
        )
        self.addCleanup(tmp.cleanup)
        real_resolve = Path.resolve

        def boom_resolve(self, *a, **kw):
            # Survive allow-root / index setup; fail when resolving the note.
            name = self.name if isinstance(self, Path) else ""
            if name == "Loop.md":
                raise RuntimeError("Symlink loop detected from testing")
            return real_resolve(self, *a, **kw)

        with mock.patch.object(Path, "resolve", boom_resolve):
            code, out, err = _run(
                [
                    "--indexdir",
                    str(idxdir),
                    "--show",
                    "--allow-root",
                    str(notes_dir),
                    "Loop",
                ]
            )
        self.assertEqual(code, 2)
        # Filtered out or explicit resolve error, either way clean nonzero.
        self.assertTrue(len(err) > 0, err)
        self.assertEqual(out, "")
        self.assertNotIn("Traceback", err)


class BuildIndexSymlinkSafety(unittest.TestCase):
    """build_index.py writes through the shared safe writer: symlinks are refused."""

    def _run(self, src, out):
        import subprocess
        return subprocess.run([sys.executable, str(ROOT / "router" / "build_index.py"),
                               "--src", str(src), "--out", str(out)],
                              capture_output=True, text=True)

    def _notes(self, td):
        src = Path(td) / "notes"
        src.mkdir()
        (src / "a.md").write_text("---\nsummary: A note about backups\n---\n# a\n")
        return src

    def test_symlinked_output_file_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td).resolve()
            src, out = self._notes(td), td / "out"
            out.mkdir()
            victim = td / "victim.txt"
            victim.write_text("keep\n")
            os.symlink(victim, out / "router-index.md")
            r = self._run(src, out)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(victim.read_text(), "keep\n")

    def test_symlinked_output_dir_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td).resolve()
            src = self._notes(td)
            real = td / "real"
            real.mkdir()
            os.symlink(real, td / "out")
            r = self._run(src, td / "out")
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(list(real.iterdir()), [])

    def test_plain_output_still_works(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td).resolve()
            src, out = self._notes(td), td / "out"
            out.mkdir()
            r = self._run(src, out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((out / "router-map.json").exists())


if __name__ == "__main__":
    unittest.main()
