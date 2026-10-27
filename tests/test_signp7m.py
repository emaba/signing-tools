"""Exercise the Fish function without hardware, network access, or real secrets."""

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FISH = shutil.which("fish")

# One executable implements only the external interfaces exercised by the tests.
# The marker is synthetic test data, never a real PIN.
SUBSTITUTE = r'''
import json
import os
from pathlib import Path
import subprocess
import sys

name = Path(sys.argv[0]).name
args = sys.argv[1:]
stage = os.environ.get("TEST_FAIL", "")
with open(os.environ["TEST_CALLS"], "a") as log:
    log.write(json.dumps([name, args]) + "\n")

def value(flag):
    return args[args.index(flag) + 1]

def fail(label):
    if stage == label:
        sys.exit(1)

if name == "brew":
    fail("brew")
    print(os.environ["TEST_PROVIDER_PREFIX"])
elif name == "pkcs11-tool":
    assert value("--slot") == os.environ.get("SIGNP7M_SLOT", "0x2")
    assert value("--id") == os.environ.get("SIGNP7M_KEY_ID", "445334")
    fail("certificate")
    Path(value("--output-file")).write_bytes(b"PUBLIC TEST CERTIFICATE")
elif name == "op":
    assert args[:2] == ["run", "--"]
    assert os.environ.get("PKCS11_PIN") == os.environ["SIGNP7M_PIN_REF"]
    fail("authentication")
    child_env = dict(os.environ)
    child_env["PKCS11_PIN"] = "SYNTHETIC_TEST_MARKER"
    sys.exit(subprocess.run(args[2:], env=child_env).returncode)
elif name == "openssl":
    if args[0] == "x509":
        assert "PKCS11_PIN" not in os.environ
        fail("conversion")
        Path(value("-out")).write_bytes(b"PUBLIC TEST PEM")
    elif "-sign" in args:
        assert os.environ.get("PKCS11_PIN") == "SYNTHETIC_TEST_MARKER"
        assert os.environ.get("PKCS11_MODULE_PATH") == os.environ["SIGNP7M_MODULE"]
        assert value("-inkey") == os.environ.get(
            "SIGNP7M_KEY_URI", "pkcs11:token=CNS;id=%44%53%34;type=private"
        )
        assert all(flag in args for flag in ["-cades", "-binary", "-nodetach"])
        assert value("-md") == "sha256"
        assert value("-outform") == "DER"
        assert value("-provider-path") == os.environ["TEST_PROVIDER_PREFIX"] + "/lib/ossl-modules"
        fail("signing")
        Path(value("-out")).write_bytes(Path(value("-in")).read_bytes())
    elif "-verify" in args:
        assert "PKCS11_PIN" not in os.environ
        assert "-noverify" in args
        fail("verification")
        data = Path(value("-in")).read_bytes()
        Path(value("-out")).write_bytes(b"CHANGED CONTENT" if stage == "integrity" else data)
    elif "-cmsout" in args:
        assert "PKCS11_PIN" not in os.environ
        # Even an attribute printed by a failed command must not be accepted.
        if stage != "attribute":
            print("object: id-smime-aa-signingCertificateV2 (1.2.840.113549.1.9.16.2.47)")
        fail("inspection")
    else:
        sys.exit(90)
else:
    sys.exit(91)
'''


@unittest.skipUnless(FISH, "Fish must be installed")
class SignP7mTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix="signp7m-tests-")
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name).resolve()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.module = self.root / "middleware.dylib"
        self.module.touch()
        self.provider = self.root / "provider/lib/ossl-modules/pkcs11prov.dylib"
        self.provider.parent.mkdir(parents=True)
        self.provider.touch()
        self.input = self.root / "test document.pdf"
        self.input.write_bytes(b"%PDF-1.4\nSynthetic test document\r\n\x00\xff\n")
        self.output = self.root / "signed document.p7m"
        self.log = self.root / "calls.jsonl"
        for name in ("brew", "op", "openssl", "pkcs11-tool"):
            executable = self.bin / name
            executable.write_text(f"#!{sys.executable}\n" + SUBSTITUTE)
            executable.chmod(0o700)
        self.env = {
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "HOME": str(self.root),
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "LC_ALL": "C",
            "SIGNP7M_PIN_REF": "op://test-vault/test-item/test-field",
            "SIGNP7M_MODULE": str(self.module),
            "TEST_CALLS": str(self.log),
            "TEST_PROVIDER_PREFIX": str(self.root / "provider"),
        }

    def run_function(self, *args, answer="", extra_env=None):
        env = self.env | (extra_env or {})
        return subprocess.run(
            [FISH, "--no-config", "-c", 'source "$argv[1]"; signp7m $argv[2..-1]',
             str(ROOT / "signp7m.fish"), *map(str, args)],
            env=env, cwd=self.root, input=answer, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
        )

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def assert_clean(self):
        self.assertEqual(list(self.root.glob(".signp7m.*")), [])

    def test_help_does_not_require_configuration_or_dependencies(self):
        self.env.pop("SIGNP7M_PIN_REF")
        result = self.run_function("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--output", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_argument_errors(self):
        for args in ((), ("--unknown",), ("-o",), (self.input, self.input),
                     ("-o", "", self.input)):
            with self.subTest(args=args):
                self.assertEqual(self.run_function(*args).returncode, 2)
        self.assertEqual(self.calls(), [])

    def test_missing_or_literal_pin_configuration_is_rejected(self):
        for reference in ("", "literal-test-value", "op://incomplete"):
            with self.subTest(reference=reference):
                result = self.run_function(self.input, extra_env={"SIGNP7M_PIN_REF": reference})
                self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), [])

    def test_pin_parameters_in_uri_are_rejected(self):
        for parameter in ("pin-value", "pin-source", "PIN-VALUE"):
            result = self.run_function(self.input, extra_env={
                "SIGNP7M_KEY_URI": f"pkcs11:token=CNS;{parameter}=synthetic-test-data"
            })
            self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), [])

    def test_missing_input_or_output_directory(self):
        self.assertEqual(self.run_function("missing.pdf").returncode, 1)
        self.assertEqual(self.run_function("-o", "missing/output.p7m", self.input).returncode, 1)
        self.assertEqual(self.calls(), [])

    def test_default_output_and_permissions(self):
        result = self.run_function(self.input)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = Path(str(self.input) + ".p7m")
        self.assertEqual(output.read_bytes(), self.input.read_bytes())
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        self.assertIn("Signature completed successfully.", result.stdout)
        self.assert_clean()

    def test_both_output_flags_with_spaces_and_relative_paths(self):
        for flag in ("-o", "--output"):
            with self.subTest(flag=flag):
                result = self.run_function(flag, self.output.name, self.input.name)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.output.read_bytes(), self.input.read_bytes())
                self.output.unlink()
                self.assert_clean()

    def test_overwrite_acceptance(self):
        for answer in ("y\n", " YES \n"):
            self.output.write_bytes(b"OLD OUTPUT")
            result = self.run_function("-o", self.output, self.input, answer=answer)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Overwrite confirmed.", result.stdout)
            self.assertEqual(self.output.read_bytes(), self.input.read_bytes())
            self.assert_clean()

    def test_cancellation_and_eof_do_not_sign(self):
        for answer in ("n\n", "\n", "", "anything\n"):
            self.output.write_bytes(b"OLD OUTPUT")
            result = self.run_function("-o", self.output, self.input, answer=answer)
            self.assertEqual(result.returncode, 0)
            self.assertIn("Operation cancelled.", result.stdout)
            self.assertEqual(self.output.read_bytes(), b"OLD OUTPUT")
        self.assertEqual(self.calls(), [])
        self.assert_clean()

    def test_same_input_output_and_hard_link_are_rejected(self):
        os.link(self.input, self.output)
        for output in (self.input, self.output):
            result = self.run_function("-o", output, self.input, answer="y\n")
            self.assertEqual(result.returncode, 1)
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.input.read_bytes(), self.output.read_bytes())

    def test_symlinked_parent_cannot_overwrite_input(self):
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        result = self.run_function("-o", alias / self.input.name, self.input, answer="y\n")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.calls(), [])

    def test_symlink_directory_and_dangling_symlink_outputs_are_rejected(self):
        for target in (self.input, self.root / "missing"):
            self.output.symlink_to(target)
            self.assertEqual(self.run_function("-o", self.output, self.input).returncode, 1)
            self.output.unlink()
        self.assertEqual(self.run_function("-o", self.root, self.input).returncode, 1)
        self.assertEqual(self.calls(), [])

    def test_missing_middleware_and_provider(self):
        self.module.unlink()
        self.assertEqual(self.run_function(self.input).returncode, 1)
        self.module.touch()
        self.provider.unlink()
        self.assertEqual(self.run_function(self.input).returncode, 1)
        self.assertFalse(any(call[0] in ("op", "openssl") for call in self.calls()))
        self.assert_clean()

    def test_all_pipeline_failures_preserve_existing_output_and_cleanup(self):
        stages = ("brew", "certificate", "conversion", "authentication", "signing",
                  "verification", "integrity", "attribute", "inspection")
        for stage in stages:
            with self.subTest(stage=stage):
                self.output.write_bytes(b"OLD OUTPUT")
                result = self.run_function("-o", self.output, self.input, answer="y\n",
                                           extra_env={"TEST_FAIL": stage})
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(self.output.read_bytes(), b"OLD OUTPUT")
                self.assertNotIn("Signature completed successfully.", result.stdout)
                self.assert_clean()

    def test_authentication_failure_does_not_reach_signing(self):
        result = self.run_function(self.input, extra_env={"TEST_FAIL": "authentication"})
        self.assertEqual(result.returncode, 1)
        self.assertFalse(any(call[0] == "openssl" and "-sign" in call[1]
                             for call in self.calls()))
        self.assertFalse(Path(str(self.input) + ".p7m").exists())
        self.assert_clean()

    def test_optional_card_selectors(self):
        result = self.run_function(self.input, extra_env={
            "SIGNP7M_SLOT": "0x7", "SIGNP7M_KEY_ID": "1234",
            "SIGNP7M_KEY_URI": "pkcs11:token=OTHER;id=%12%34;type=private",
        })
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_clean()

    def test_pin_reference_does_not_escape_to_parent(self):
        result = subprocess.run(
            [FISH, "--no-config", "-c",
             'source "$argv[1]"; signp7m "$argv[2]"; '
             'set -l result $status; set -q PKCS11_PIN; and exit 99; exit $result',
             str(ROOT / "signp7m.fish"), str(self.input)],
            env=self.env, cwd=self.root, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
