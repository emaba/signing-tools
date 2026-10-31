"""Installer transactions use temporary folders and fake dependency commands."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import install_signpdf as installer


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="signpdf install test ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.prefix = self.root / "Application Support/signp7m"
        self.functions = self.root / "fish/functions"
        self.functions.mkdir(parents=True)
        self.legacy = self.functions / "signp7m.fish"
        self.legacy.write_text("SYNTHETIC EXISTING CADES FUNCTION\n")
        for name in installer.FILES:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("SYNTHETIC SOURCE: " + name)

    def fake_run(self, command, message):
        if str(command[0]) == "uv" and command[1] == "venv":
            python = Path(command[-1]) / "bin/python"
            python.parent.mkdir(parents=True)
            python.write_text("SYNTHETIC PYTHON PLACEHOLDER")
        return ""

    def install(self, run=None):
        with patch.object(installer, "run", side_effect=run or self.fake_run), redirect_stdout(StringIO()):
            installer.install(self.source, self.prefix, self.functions, "python3.12", "uv")

    def test_isolated_release_and_link_preserve_existing_cades(self):
        self.install()
        state = installer.state_at(self.prefix)
        function = self.functions / "signpdf.fish"
        self.assertEqual(function.resolve(), (self.prefix / "releases" / state["active"] / "app/signpdf.fish").resolve())
        self.assertEqual(self.legacy.read_text(), "SYNTHETIC EXISTING CADES FUNCTION\n")
        self.assertEqual({p.name for p in self.functions.iterdir()}, {"signp7m.fish", "signpdf.fish"})
        self.assertEqual(list(self.prefix.glob(".cache-*")), [])
        self.assertIsNone(state["backup"])

    def test_existing_pades_function_is_restored_on_uninstall(self):
        function = self.functions / "signpdf.fish"
        function.write_text("SYNTHETIC OLD PDF FUNCTION\n")
        self.install()
        with redirect_stdout(StringIO()):
            installer.uninstall(self.prefix, self.root / "Trash")
        self.assertFalse(self.prefix.exists())
        self.assertEqual(function.read_text(), "SYNTHETIC OLD PDF FUNCTION\n")
        self.assertEqual(len(list((self.root / "Trash").iterdir())), 1)
        self.assertTrue(self.legacy.is_file())

    def test_failed_update_preserves_active_release_and_function(self):
        self.install()
        before = (self.prefix / "install.json").read_bytes()
        target = (self.prefix / "current").resolve()
        (self.source / "signpdf.py").write_text("SYNTHETIC UPDATED SOURCE")
        def fail(command, message):
            if command[1:3] == ["pip", "install"]:
                raise installer.InstallError("synthetic dependency failure")
            return self.fake_run(command, message)
        with self.assertRaises(installer.InstallError):
            self.install(fail)
        self.assertEqual((self.prefix / "install.json").read_bytes(), before)
        self.assertEqual((self.prefix / "current").resolve(), target)
        self.assertEqual(len(list((self.prefix / "releases").iterdir())), 1)

    def test_failed_activation_restores_original_function_and_removes_new_installation(self):
        function = self.functions / "signpdf.fish"
        function.write_text("SYNTHETIC ORIGINAL\n")
        with patch.object(installer, "write_json", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                self.install()
        self.assertEqual(function.read_text(), "SYNTHETIC ORIGINAL\n")
        self.assertFalse(self.prefix.exists())

    def test_uninstall_refuses_a_function_changed_by_the_owner(self):
        self.install()
        function = self.functions / "signpdf.fish"
        function.unlink()
        function.write_text("SYNTHETIC OWNER EDIT")
        with self.assertRaises(installer.InstallError):
            installer.uninstall(self.prefix, self.root / "Trash")
        self.assertTrue(self.prefix.is_dir())
        self.assertEqual(function.read_text(), "SYNTHETIC OWNER EDIT")

    def test_reinstall_of_same_source_does_not_create_another_environment(self):
        self.install()
        with patch.object(installer, "run", return_value="") as run, redirect_stdout(StringIO()):
            installer.install(self.source, self.prefix, self.functions, "python3.12", "uv")
        self.assertEqual(run.call_count, 1)  # Existing Python version check only.
        self.assertEqual(len(list((self.prefix / "releases").iterdir())), 1)

    def test_zsh_and_bash_install_update_failure_and_uninstall(self):
        for shell in ("zsh", "bash"):
            with self.subTest(shell=shell):
                prefix, commands = self.root / shell, self.root / (shell + "-integration")
                commands.mkdir(parents=True)
                entry = commands / "commands.sh"
                entry.write_text("SYNTHETIC ORIGINAL SHELL ENTRY\n")
                with patch.object(installer, "run", side_effect=self.fake_run), redirect_stdout(StringIO()):
                    installer.install(self.source, prefix, commands, "python3.12", "uv", shell=shell)
                self.assertEqual(entry.resolve(), (prefix / "current/app/signing-tools.sh").resolve())
                before = (prefix / "install.json").read_bytes()
                runtime = self.source / "signpdf.py"
                runtime.write_text(runtime.read_text() + "SYNTHETIC UPDATE\n")
                def fail(command, message):
                    if command[1:3] == ["pip", "install"]:
                        raise installer.InstallError("synthetic download failure")
                    return self.fake_run(command, message)
                with patch.object(installer, "run", side_effect=fail), self.assertRaises(installer.InstallError):
                    installer.install(self.source, prefix, commands, "python3.12", "uv", shell=shell)
                self.assertEqual((prefix / "install.json").read_bytes(), before)
                with redirect_stdout(StringIO()):
                    installer.uninstall(prefix, self.root / "Trash")
                self.assertEqual(entry.read_text(), "SYNTHETIC ORIGINAL SHELL ENTRY\n")
                self.assertEqual(self.legacy.read_text(), "SYNTHETIC EXISTING CADES FUNCTION\n")

    def test_shell_switch_does_not_overwrite_existing_fish_install(self):
        self.install()
        before = (self.prefix / "install.json").read_bytes()
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, self.prefix, self.root / "zsh", "python3.12", "uv", shell="zsh")
        self.assertEqual((self.prefix / "install.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
