"""Committed-snapshot isolation and reproducible package tests; no signing."""

from io import BytesIO
from pathlib import Path
import tarfile
import tempfile
import unittest

from scripts import build_macos_bundle as builder


ROOT = Path(__file__).resolve().parents[1]


class SourceGuardTests(unittest.TestCase):
    def test_rejects_private_documents_local_configuration_and_traversal(self):
        for name in ("../outside", "/absolute", ".env", "config.local.fish", "config.local.sh", "settings.sh", "config.toml", "migration.json", "real.pdf", "key.pem",
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


if __name__ == "__main__":
    unittest.main()
