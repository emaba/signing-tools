"""Migration and rollback transactions use only synthetic private settings."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from signing_tools import config, migration


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="signing migration ")
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.config = self.home / ".config/signing-tools/config.toml"
        self.fish = self.home / ".config/fish/functions"
        self.fish.mkdir(parents=True)
        self.target = self.home / "Library/Application Support/signp7m/current/app/signpdf.fish"
        self.target.parent.mkdir(parents=True)
        self.target.write_text("SYNTHETIC MANAGED PDF FUNCTION\n")
        (self.fish / "signpdf.fish").symlink_to(self.target)
        self.legacy = self.fish / "signp7m.fish"
        self.original = ("function signp7m\n# SafeDive PKCS11 legacy signing\n"
                         "set -l onepassword_pin_ref 'op://SYNTHETIC_PRIVATE_METADATA/Item/PIN'\n"
                         "set -l pkcs11_slot '0x7'\n"
                         'set -lx PKCS11_PIN "$onepassword_pin_ref"\n'
                         "touch MUST_NOT_EXECUTE\nopenssl cms -sign\nend\n")
        self.legacy.write_text(self.original)
        self.environ = patch.dict(os.environ, {}, clear=True)
        self.environ.start();self.addCleanup(self.environ.stop)

    def migrate(self, **options):
        output = io.StringIO()
        with redirect_stdout(output):
            migration.migrate(home=self.home, destination=self.config, **options)
        self.assertNotIn("SYNTHETIC_PRIVATE_METADATA", output.getvalue())
        return output.getvalue()

    def rollback(self, **options):
        with redirect_stdout(io.StringIO()):
            migration.rollback(home=self.home, destination=self.config, **options)

    def assert_legacy(self):
        self.assertEqual(self.legacy.read_text(), self.original)
        self.assertEqual(os.readlink(self.fish / "signpdf.fish"), str(self.target))
        self.assertEqual(self.target.read_text(), "SYNTHETIC MANAGED PDF FUNCTION\n")

    def test_plan_is_read_only_and_never_executes_fish(self):
        self.migrate(plan=True)
        self.assert_legacy()
        self.assertFalse(self.config.exists())
        self.assertFalse((self.home / "MUST_NOT_EXECUTE").exists())

    def test_migration_backs_up_functions_and_is_idempotent(self):
        self.migrate()
        settings = config.load(self.config)
        self.assertEqual(settings["signing"]["slot"], "0x7")
        self.assertEqual(settings["signing"]["pin_reference"], "op://SYNTHETIC_PRIVATE_METADATA/Item/PIN")
        self.assertFalse(self.legacy.exists())
        self.assertFalse((self.fish / "signpdf.fish").is_symlink())
        state = self.config.parent / "migration.json"
        before = state.read_bytes()
        self.assertIn("already migrated", self.migrate())
        self.assertEqual(state.read_bytes(), before)

    def test_existing_configuration_is_preserved(self):
        config.create({"signing": {"pin_reference": "op://Existing/Item/Field"}}, self.config)
        before = self.config.read_bytes()
        self.migrate()
        self.assertEqual(self.config.read_bytes(), before)

    def test_failure_restores_functions_and_removes_only_new_configuration(self):
        with patch.object(migration, "write_state", side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                self.migrate()
        self.assert_legacy()
        self.assertFalse(self.config.exists())

    def test_rollback_restores_functions_and_preserves_user_configuration(self):
        self.migrate();before = self.config.read_bytes()
        self.rollback(plan=True)
        self.assertFalse(self.legacy.exists())
        self.rollback()
        self.assert_legacy()
        self.assertEqual(self.config.read_bytes(), before)

    def test_rollback_refuses_to_overwrite_a_new_function(self):
        self.migrate()
        self.legacy.write_text("SYNTHETIC OWNER EDIT\n")
        with self.assertRaises(migration.MigrationError):
            self.rollback()
        self.assertEqual(self.legacy.read_text(), "SYNTHETIC OWNER EDIT\n")

    def test_failed_rollback_keeps_migration_active_and_backups_available(self):
        self.migrate()
        with patch.object(migration, "write_state", side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                self.rollback()
        self.assertFalse(self.legacy.exists())
        state=json.loads((self.config.parent / "migration.json").read_text())
        self.assertEqual(state["status"], "active")
        self.assertTrue(all(Path(entry["backup"]).is_file() for entry in state["entries"]))

    def test_ambiguous_reference_fails_before_retiring_functions(self):
        self.legacy.write_text(self.original.replace('touch MUST_NOT_EXECUTE', "set -lx PKCS11_PIN 'op://Other/Item/Field'"))
        before = self.legacy.read_bytes()
        with self.assertRaises(migration.MigrationError):
            self.migrate()
        self.assertEqual(self.legacy.read_bytes(), before)
        self.assertFalse(self.config.exists())

    def test_conflicting_settings_across_files_are_not_silently_overwritten(self):
        other=self.home / ".config/fish/conf.d/signing-tools.fish"
        other.parent.mkdir(parents=True)
        other.write_text("set -gx SIGNP7M_SLOT '0x9'\n")
        with self.assertRaises(migration.MigrationError):
            self.migrate()
        self.assert_legacy()
        self.assertFalse(self.config.exists())

    def test_legacy_shell_source_gets_a_no_function_bridge(self):
        source=self.home / ".config/signing-tools/commands.sh"
        source.parent.mkdir(parents=True)
        target=self.target.with_name("signing-tools.sh")
        target.write_text("SYNTHETIC OLD SHELL ENTRY\n")
        source.symlink_to(target)
        self.migrate()
        self.assertEqual(source.read_bytes(), migration.BRIDGE)
        self.rollback()
        self.assertTrue(source.is_symlink())
        self.assertEqual(source.resolve(), target.resolve())


if __name__ == "__main__":
    unittest.main()
