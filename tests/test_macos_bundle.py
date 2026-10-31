"""Committed-snapshot isolation and reproducible package tests; no signing."""

from datetime import date
import hashlib
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time
import unittest
import zipfile

from scripts import build_macos_bundle as builder


ROOT = Path(__file__).resolve().parents[1]


class SourceGuardTests(unittest.TestCase):
    def test_rejects_private_documents_local_configuration_and_traversal(self):
        for name in ("../outside", "/absolute", ".env", "config.local.fish", "real.pdf", "key.pem",
                     ".git/config", ".venv/bin/python", "__pycache__/cached.pyc"):
            with self.subTest(name=name), self.assertRaises(builder.BundleError):
                builder.safe_source_name(name)
        self.assertEqual(str(builder.safe_source_name("assets/fonts/OFL-KaushanScript.txt")),
                         "assets/fonts/OFL-KaushanScript.txt")

    def test_rejects_links_and_private_key_headers(self):
        for link in (True, False):
            data = BytesIO()
            with tarfile.open(fileobj=data, mode="w") as archive:
                entry = tarfile.TarInfo("source.py")
                content = ("-----BEGIN " + "PRIVATE KEY-----\nSYNTHETIC\n").encode()
                if link:
                    entry.type, entry.linkname = tarfile.SYMTYPE, "../outside"
                    archive.addfile(entry)
                else:
                    entry.size = len(content)
                    archive.addfile(entry, BytesIO(content))
            with tempfile.TemporaryDirectory() as temporary, self.assertRaises(builder.BundleError):
                builder.extract_source(data.getvalue(), Path(temporary))


@unittest.skipUnless(importlib.util.find_spec("reportlab") and all(p.is_file() for p in builder.DEFAULT_FONTS),
                     "ReportLab and the default macOS fonts required for rendering integration")
class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="signing distribution test ")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.repo = cls.root / "source"
        cls.repo.mkdir()
        names = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z"]).decode().split("\0")
        names = {name for name in names if name}
        names.update(str(path.relative_to(ROOT)) for folder in (ROOT / "packaging", ROOT / "scripts")
                     for path in folder.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
        names.update(("requirements-packaging.txt", "docs/distribution.md"))
        for name in names:
            source = ROOT / name
            destination = cls.repo / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        subprocess.run(["git", "init", "-q", str(cls.repo)], check=True)
        subprocess.run(["git", "-C", str(cls.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(cls.repo), "-c", "user.name=Distribution Test",
                        "-c", "user.email=distribution@example.invalid", "-c", "commit.gpgsign=false",
                        "-c", "core.hooksPath=/dev/null", "commit", "-qm", "Synthetic snapshot"], check=True)
        cls.commit = subprocess.check_output(["git", "-C", str(cls.repo), "rev-parse", "HEAD"]).decode().strip()

    def test_two_builds_match_and_exclude_working_tree_configuration(self):
        (self.repo / ".env").write_text("SYNTHETIC UNTRACKED CONFIGURATION\n")
        (self.repo / "README.md").write_text("SYNTHETIC UNCOMMITTED EDIT\n")
        first, commit, digest = builder.build(self.repo, self.commit, self.root / "first", date(2026, 10, 31))
        time.sleep(1.05)  # Cross a PDF metadata timestamp boundary.
        second, _, other_digest = builder.build(self.repo, self.commit, self.root / "second", date(2026, 10, 31))
        self.assertEqual(digest, other_digest)
        self.assertEqual(commit, self.commit)
        with zipfile.ZipFile(first) as archive:
            self.assertIsNone(archive.testzip())
            prefix = "signing-tools-macos/"
            self.assertNotIn(prefix + "source/.env", archive.namelist())
            self.assertNotIn(b"SYNTHETIC UNCOMMITTED EDIT", archive.read(prefix + "source/README.md"))
            info = json.loads(archive.read(prefix + "PACKAGE-INFO.json"))
            self.assertEqual(info["source_commit"], self.commit)
            self.assertEqual(info["guide_pages"], 6)
            self.assertEqual(info["sample_pages"], 3)
            manifest = archive.read(prefix + "SHA256SUMS.txt").decode().splitlines()
            self.assertEqual(len(manifest), len(archive.namelist()) - 1)
            for line in manifest:
                expected, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256(archive.read(prefix + name)).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
