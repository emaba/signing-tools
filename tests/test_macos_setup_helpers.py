"""Exercise shareable setup helpers without user settings, cards or credentials."""

import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "packaging/macos"


class SetupHelperTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="signing setup test ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @unittest.skipUnless(shutil.which("fish"), "Fish required")
    def test_fresh_setup_and_existing_files_are_preserved(self):
        bundle = self.root / "bundle"
        (bundle / "source").mkdir(parents=True)
        for name in ("install-fish-extras.fish", "settings.example.fish"):
            shutil.copyfile(TEMPLATES / name, bundle / name)
        shutil.copyfile(ROOT / "signp7m.fish", bundle / "source/signp7m.fish")
        config = self.root / "fish config"
        env = {k: v for k, v in os.environ.items() if k != "SIGNP7M_PIN_REF"}
        env["XDG_CONFIG_HOME"] = str(self.root / "isolated-config")
        command = [shutil.which("fish"), "--no-config", str(bundle / "install-fish-extras.fish"),
                   "--config-root", str(config)]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        function, settings = config / "functions/signp7m.fish", config / "conf.d/signing-tools.fish"
        self.assertEqual(function.read_bytes(), (ROOT / "signp7m.fish").read_bytes())
        self.assertEqual(stat.S_IMODE(settings.stat().st_mode), 0o600)
        function.write_text("SYNTHETIC EXISTING FUNCTION\n")
        settings.write_text("SYNTHETIC EXISTING SETTINGS\n")
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(function.read_text(), "SYNTHETIC EXISTING FUNCTION\n")
        self.assertEqual(settings.read_text(), "SYNTHETIC EXISTING SETTINGS\n")

    @unittest.skipUnless(shutil.which("fish"), "Fish required")
    def test_legacy_function_does_not_get_a_new_placeholder_configuration(self):
        bundle = self.root / "bundle"
        bundle.mkdir()
        shutil.copyfile(TEMPLATES / "install-fish-extras.fish", bundle / "install-fish-extras.fish")
        config = self.root / "fish config"
        (config / "functions").mkdir(parents=True)
        function = config / "functions/signp7m.fish"
        function.write_text("SYNTHETIC LEGACY\n")
        result = subprocess.run([shutil.which("fish"), "--no-config", str(bundle / "install-fish-extras.fish"),
                                 "--config-root", str(config)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((config / "conf.d/signing-tools.fish").exists())
        self.assertEqual(function.read_text(), "SYNTHETIC LEGACY\n")

    def test_preflight_status_does_not_disclose_or_resolve_a_reference(self):
        binary = self.root / "bin"
        binary.mkdir()
        provider = self.root / "provider/lib/ossl-modules"
        provider.mkdir(parents=True)
        (provider / "pkcs11prov.dylib").touch()
        module = self.root / "middleware.dylib"
        module.touch()
        for name in ("fish", "python3.12", "uv", "pkcs11-tool", "op"):
            path = binary / name
            path.write_text("#!/bin/sh\nexit 99\n")
            path.chmod(0o700)
        brew = binary / "brew"
        brew.write_text('#!/bin/sh\nprintf "%s\\n" ' + shlex.quote(str(self.root / "provider")) + "\n")
        brew.chmod(0o700)
        openssl = binary / "openssl"
        openssl.write_text('#!/bin/sh\nif [ "$1" = version ]; then echo "OpenSSL SYNTHETIC"; fi\nexit 0\n')
        openssl.chmod(0o700)
        env = dict(PATH=str(binary) + ":/usr/bin:/bin", SIGNP7M_MODULE=str(module),
                   SIGNP7M_PIN_REF="SYNTHETIC_DO_NOT_DISPLAY")
        command = [sys.executable, str(TEMPLATES / "check-setup.py")]
        failed = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1)
        self.assertNotIn(env["SIGNP7M_PIN_REF"], failed.stdout + failed.stderr)
        env["SIGNP7M_PIN_REF"] = "op://SYNTHETIC_VAULT/SYNTHETIC_ITEM/SYNTHETIC_FIELD"
        passed = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(passed.returncode, 0, passed.stdout)
        self.assertNotIn("op://", passed.stdout + passed.stderr)


if __name__ == "__main__":
    unittest.main()
