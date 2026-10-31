"""Zsh/Bash integration with no Fish, hardware, user settings or resolved secrets."""

import json
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ShellTests(unittest.TestCase):
    def test_functions_forward_arguments_and_keep_settings_in_child(self):
        with tempfile.TemporaryDirectory(prefix="signing shell test ") as temporary:
            root = Path(temporary)
            app = root / "application/current/app"
            app.mkdir(parents=True)
            binary = app.parent / "venv/bin"
            binary.mkdir(parents=True)
            (binary / "python").symlink_to(sys.executable)
            probe = ('import json, os, sys\nprint(json.dumps(dict(argv=sys.argv[1:], '
                     'configured=os.environ.get("SIGNP7M_PIN_REF", "").startswith("op://"))))\n')
            for name in ("signpdf.py", "signp7m.py", "packaging/macos/check-setup.py"):
                path = app / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(probe)
            settings = root / "settings.sh"
            settings.write_text("export SIGNP7M_PIN_REF='op://synthetic/item/field'\n"
                                "PATH=/synthetic/provider:$PATH\nexport PATH\n")
            env = dict(HOME=str(root), PATH="/usr/bin:/bin", SIGNING_TOOLS_ROOT=str(app.parents[1]),
                       SIGNING_TOOLS_CONFIG=str(settings))
            script = ('. ' + shlex.quote(str(ROOT / "signing-tools.sh")) + '\n'
                      'original_path=$PATH\nsignpdf "document with spaces.pdf" --page 3\n'
                      'signp7m --help\nsigning_tools_check\n'
                      '[ "$PATH" = "$original_path" ] || exit 91\n'
                      '[ -z "${SIGNP7M_PIN_REF+x}" ] || exit 92\n')
            for shell in (("/bin/zsh", "-f"), ("/bin/bash", "--noprofile", "--norc"), ("/bin/sh",)):
                with self.subTest(shell=shell):
                    result = subprocess.run([*shell, "-c", script], env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    values = [json.loads(line) for line in result.stdout.splitlines()]
                    self.assertEqual(values[0]["argv"], ["document with spaces.pdf", "--page", "3"])
                    self.assertEqual(values[1]["argv"], ["--help"])
                    self.assertEqual(values[2]["argv"], [])
                    self.assertTrue(all(value["configured"] for value in values))
                    self.assertNotIn("op://", result.stdout + result.stderr)

    def test_settings_helper_preserves_existing_files_and_rejects_symlink_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="signing settings test ") as temporary:
            config = Path(temporary) / "settings"
            command = [sys.executable, str(ROOT / "packaging/macos/install-shell-extras.py"),
                       "--config-root", str(config)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            settings = config / "settings.sh"
            self.assertEqual(stat.S_IMODE(settings.stat().st_mode), 0o600)
            self.assertEqual(settings.read_bytes(), (ROOT / "packaging/macos/settings.example.sh").read_bytes())
            settings.write_text("SYNTHETIC EXISTING SETTINGS\n")
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(settings.read_text(), "SYNTHETIC EXISTING SETTINGS\n")
            settings.unlink()
            target = config / "absent-target"
            settings.symlink_to(target)
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertTrue(settings.is_symlink())
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
