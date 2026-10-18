"""Regression: a symlinked directory several levels below MEMORY_ROOT must be refused."""
import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import safe_io


class AncestorSymlink(unittest.TestCase):
    def test_deep_ancestor_symlink_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve() / "root"
            outside = Path(td).resolve() / "outside"
            (root / "ledger").mkdir(parents=True)
            outside.mkdir()
            os.symlink(outside, root / "ledger" / "sub")
            target = root / "ledger" / "sub" / "deeper" / "x.log"
            (outside / "deeper").mkdir()
            with self.assertRaises(ValueError):
                safe_io.write_text(target, "nope\n", root=root, append=True)
            self.assertFalse((outside / "deeper" / "x.log").exists())

    def test_plain_path_under_root_ok(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            (root / "a" / "b").mkdir(parents=True)
            safe_io.write_text(root / "a" / "b" / "ok.txt", "ok\n", root=root)
            self.assertEqual((root / "a" / "b" / "ok.txt").read_text(), "ok\n")


if __name__ == "__main__":
    unittest.main()
