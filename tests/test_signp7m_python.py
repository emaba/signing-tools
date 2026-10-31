"""Run the CAdES contract without Fish, real credentials or smart-card hardware."""

import os
from pathlib import Path
import shlex
import subprocess
import sys
import unittest

import test_signp7m as legacy


class PythonCAdESTests(legacy.SignP7mTests):
    __unittest_skip__ = False

    def setUp(self):
        super().setUp()
        self.env.update(TEST_EXPECTED_PIN_REF=self.env["SIGNP7M_PIN_REF"].removeprefix("op://"), TEST_FILTERED="1")

    def run_function(self, *args, answer="", extra_env=None):
        return subprocess.run([sys.executable, str(legacy.ROOT / "signp7m.py"), *map(str, args)],
                              env=self.env | (extra_env or {}), cwd=self.root, input=answer,
                              text=True, capture_output=True, timeout=15)

    def test_pin_reference_does_not_escape_to_parent(self):
        result = self.run_function(self.input, extra_env={"UNRELATED_SECRET": "op://other/item/field"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("SYNTHETIC_TEST_MARKER", result.stdout + result.stderr)
        self.assertNotIn("op://", result.stdout + result.stderr)
        self.assertNotIn("PKCS11_PIN", self.env)

    def test_real_openssl_cades_with_synthetic_certificate(self):
        openssl = Path("/opt/homebrew/opt/openssl@4/bin/openssl")
        if not openssl.is_file():
            self.skipTest("Homebrew OpenSSL 4 needed for real CMS test")
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        from datetime import datetime, timedelta, timezone
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic CAdES test")])
        now = datetime.now(timezone.utc)
        certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                       .public_key(key.public_key()).serial_number(x509.random_serial_number())
                       .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
                       .sign(key, hashes.SHA256()))
        pem, der = self.root / "synthetic.key", self.root / "synthetic.der"
        pem.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
        pem.chmod(0o600)
        der.write_bytes(certificate.public_bytes(serialization.Encoding.DER))
        reader = self.bin / "pkcs11-tool"
        reader.write_text(reader.read_text().replace(
            'b"PUBLIC TEST CERTIFICATE"', 'Path(os.environ["TEST_CERT_DER"]).read_bytes()'))
        (self.bin / "openssl").unlink()
        (self.bin / "openssl").symlink_to(openssl)
        # Replace only the hardware-dependent signing step, retaining real CMS commands.
        code = '''import os, subprocess, sys
args = sys.argv[3:]
result = []
i = 0
while i < len(args):
    if args[i] in ("-provider", "-provider-path"):
        i += 2
        continue
    if args[i] == "-inkey":
        result.extend(["-inkey", os.environ["TEST_KEY"]]); i += 2
        continue
    result.append(args[i]); i += 1
raise SystemExit(subprocess.run(result).returncode)
'''
        op = self.bin / "op"
        op.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + " -c " + shlex.quote(code) + ' "$@"\n')
        result = self.run_function(self.input, extra_env={"TEST_CERT_DER": str(der), "TEST_KEY": str(pem)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        recovered = self.root / "independent.pdf"
        verify = subprocess.run([str(openssl), "cms", "-verify", "-inform", "DER", "-noverify",
                                 "-in", str(self.input) + ".p7m", "-out", str(recovered)], capture_output=True)
        self.assertEqual(verify.returncode, 0)
        self.assertEqual(recovered.read_bytes(), self.input.read_bytes())
        self.assert_clean()


if __name__ == "__main__":
    unittest.main()
