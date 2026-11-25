"""Unified settings and management commands never resolve or print secrets."""

from contextlib import redirect_stdout, redirect_stderr
import io
import getpass
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from signing_tools import cli, config, tools


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="signing config ")
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "private/config.toml"
        self.settings = {"schema": 1, "signing": {"pin_reference": "op://SYNTHETIC_PRIVATE_METADATA/Item/PIN", "slot": "0x7"}}

    def test_private_toml_roundtrip_and_no_overwrite(self):
        config.create(self.settings, self.path)
        self.assertEqual(config.load(self.path), self.settings)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        with self.assertRaises(FileExistsError):
            config.create(self.settings, self.path)

    def test_literal_pin_unknown_keys_and_pin_uris_are_rejected_before_writing(self):
        for settings in ({"signing": {"pin_reference": "SYNTHETIC_LITERAL_PIN"}},
                         {"signing": {"password": "SYNTHETIC_LITERAL_PIN"}},
                         {"signing": {"key_uri": "pkcs11:pin-value=SYNTHETIC_LITERAL_PIN"}},
                         {"schema": True}, {"signing": {"raw_mechanism": "1"}}):
            with self.subTest(settings=settings), self.assertRaises(config.ConfigError):
                config.create(settings, self.path)
            self.assertFalse(self.path.exists())

    def test_environment_applies_to_both_commands_and_restores_parent(self):
        with patch.dict(os.environ, {}, clear=True), patch("subprocess.run") as run:
            with config.environment(self.settings):
                self.assertEqual(os.environ["SIGNP7M_PIN_REF"], self.settings["signing"]["pin_reference"])
                self.assertEqual(os.environ["SIGNPDF_PIN_REF"], os.environ["SIGNP7M_PIN_REF"])
                self.assertEqual(os.environ["SIGNP7M_SLOT"], "0x7")
            self.assertNotIn("SIGNP7M_PIN_REF", os.environ)
            run.assert_not_called()

    def test_explicit_environment_overrides_file_configuration(self):
        with patch.dict(os.environ, {"SIGNPDF_PIN_REF": "op://Explicit/Item/Field"}, clear=True):
            with config.environment(self.settings):
                self.assertEqual(os.environ["SIGNPDF_PIN_REF"], "op://Explicit/Item/Field")

    def test_invalid_toml_does_not_disclose_contents(self):
        self.path.parent.mkdir()
        self.path.write_text('schema = [SYNTHETIC_PRIVATE_METADATA\n')
        with self.assertRaises(config.ConfigError) as error:
            config.load(self.path)
        self.assertNotIn("SYNTHETIC_PRIVATE_METADATA", str(error.exception))

    def test_configure_rejects_literal_pin_without_echo_or_file(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"SIGNING_TOOLS_CONFIG": str(self.path)}), \
             patch("getpass.getpass", return_value="SYNTHETIC_LITERAL_PIN"), \
             redirect_stdout(output), redirect_stderr(output):
            self.assertEqual(cli.main(["configure"]), 1)
        self.assertFalse(self.path.exists())
        self.assertNotIn("SYNTHETIC_LITERAL_PIN", output.getvalue())

    def test_configure_refuses_a_prompt_that_cannot_hide_input(self):
        output=io.StringIO()
        with patch.dict(os.environ, {"SIGNING_TOOLS_CONFIG": str(self.path)}), \
             patch("getpass.getpass", side_effect=getpass.GetPassWarning), \
             redirect_stdout(output), redirect_stderr(output):
            self.assertEqual(cli.main(["configure"]), 1)
        self.assertFalse(self.path.exists())
        self.assertIn("interactive terminal with hidden input", output.getvalue())

    def test_configure_keeps_reference_and_updates_optional_slot(self):
        config.create(self.settings, self.path)
        output = io.StringIO()
        with patch.dict(os.environ, {"SIGNING_TOOLS_CONFIG": str(self.path)}), \
             patch("getpass.getpass", return_value=""), redirect_stdout(output):
            self.assertEqual(cli.main(["configure", "--slot", "0x8"]), 0)
        self.assertEqual(config.load(self.path)["signing"]["slot"], "0x8")
        self.assertNotIn("SYNTHETIC_PRIVATE_METADATA", output.getvalue())
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_entrypoint_loads_configuration_without_shell(self):
        from signing_tools import signpdf
        config.create(self.settings, self.path)
        def sign(args):
            self.assertEqual(os.environ["SIGNPDF_PIN_REF"], self.settings["signing"]["pin_reference"])
            return 0
        with patch.dict(os.environ, {"SIGNING_TOOLS_CONFIG": str(self.path)}, clear=True), \
             patch.object(signpdf, "main", side_effect=sign):
            self.assertEqual(cli._sign("signpdf", ["synthetic.pdf"]), 0)
            self.assertNotIn("SIGNPDF_PIN_REF", os.environ)

    def test_tool_paths_are_selected_without_changing_path(self):
        with patch.dict(os.environ, {"PATH": "/synthetic/path"}, clear=True):
            with config.environment({"tools": {"openssl": "/synthetic/provider/openssl"}}):
                self.assertEqual(tools.executable("openssl"), "/synthetic/provider/openssl")
                self.assertEqual(os.environ["PATH"], "/synthetic/path")

    def test_runtime_doctor_uses_neither_configuration_nor_external_tools(self):
        output = io.StringIO()
        with patch.object(config, "load", side_effect=AssertionError("must not read settings")), \
             patch("subprocess.run", side_effect=AssertionError("must not invoke tools")), \
             redirect_stdout(output):
            self.assertEqual(cli.main(["doctor", "--runtime-only"]), 0)
        self.assertNotIn("op://", output.getvalue())


if __name__ == "__main__":
    unittest.main()
