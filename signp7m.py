#!/usr/bin/env python3
"""Shell-independent CAdES signing through OpenSSL, SafeDive and 1Password."""

import argparse
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from signpdf import MODULE, SignPDFError, file_identity, output_path, publish, valid_reference


class ConfigurationError(SignPDFError):
    """A controlled invalid-configuration message."""


def run(command, message, env=None):
    # Third-party diagnostics can contain token data. Return only controlled errors.
    result = subprocess.run(command, env=env, capture_output=True)
    if result.returncode:
        raise SignPDFError(message)
    return result.stdout


def execute(args):
    reference = os.environ.get("SIGNP7M_PIN_REF", "")
    key = os.environ.get("SIGNP7M_KEY_URI", "pkcs11:token=CNS;id=%44%53%34;type=private")
    if not valid_reference(reference):
        raise ConfigurationError("set SIGNP7M_PIN_REF to a 1Password secret reference")
    if re.search(r"pin-(?:value|source)=", key, re.I):
        raise ConfigurationError("the key URI must not contain PIN parameters")
    if args.output == "":
        raise ConfigurationError("output filename cannot be empty")
    source = args.input.expanduser().resolve(strict=True)
    if not source.is_file():
        raise SignPDFError("input must be a regular file")
    destination = output_path(source, Path(args.output) if args.output is not None else Path(str(source) + ".p7m"))
    identity = file_identity(destination)
    if identity is not None:
        print(f"The output file already exists:\n{destination}")
        try:
            answer = input("Overwrite existing file? [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("y", "yes"):
            print("Operation cancelled.")
            return 0
        print("Overwrite confirmed.")
    for command in ("openssl", "pkcs11-tool", "op", "brew"):
        if not shutil.which(command):
            raise SignPDFError("missing dependency: " + command)
    module = os.environ.get("SIGNP7M_MODULE", MODULE)
    if not Path(module).is_file():
        raise SignPDFError("SafeDive PKCS#11 module not found")
    prefix = run(["brew", "--prefix", "libp11"], "libp11 prefix could not be determined").decode().strip()
    provider = Path(prefix) / "lib/ossl-modules"
    if not (provider / "pkcs11prov.dylib").is_file():
        raise SignPDFError("libp11 OpenSSL provider not found")
    # Resolve only the intended PIN reference in op run's child environment.
    env = {k: v for k, v in os.environ.items()
           if not v.startswith("op://") and k not in ("PKCS11_PIN", "SIGNPDF_WORKER_PIN")}
    env["PKCS11_MODULE_PATH"] = module
    with tempfile.TemporaryDirectory(prefix=".signp7m.", dir=destination.parent) as directory:
        work = Path(directory)
        work.chmod(0o700)
        snapshot, certificate, pem = work / "input.pdf", work / "DS4.der", work / "DS4.pem"
        signed, extracted = work / "signed.p7m", work / "extracted.pdf"
        with source.open("rb") as incoming, snapshot.open("xb") as outgoing:
            snapshot.chmod(0o600)
            shutil.copyfileobj(incoming, outgoing)
        print("Reading InfoCert DS4 signing certificate...")
        run(["pkcs11-tool", "--module", module, "--slot", os.environ.get("SIGNP7M_SLOT", "0x2"),
             "--read-object", "--type", "cert", "--id", os.environ.get("SIGNP7M_KEY_ID", "445334"),
             "--output-file", str(certificate)], "failed to read signing certificate", env)
        run(["openssl", "x509", "-inform", "DER", "-in", str(certificate), "-out", str(pem)],
            "certificate conversion failed", env)
        print("Creating CAdES signature...\nAuthenticating through 1Password...")
        run(["op", "run", "--", "openssl", "cms", "-sign", "-provider-path", str(provider),
             "-provider", "default", "-provider", "pkcs11prov", "-binary", "-cades", "-nodetach",
             "-md", "sha256", "-in", str(snapshot), "-signer", str(pem), "-inkey", key,
             "-outform", "DER", "-out", str(signed)], "digital signing failed",
            env | {"PKCS11_PIN": reference})
        print("Verifying cryptographic signature...")
        run(["openssl", "cms", "-verify", "-inform", "DER", "-in", str(signed), "-noverify",
             "-out", str(extracted)], "cryptographic signature verification failed", env)
        print("Verifying document integrity...")
        with snapshot.open("rb") as original, extracted.open("rb") as recovered:
            while True:
                block = original.read(1024 * 1024)
                if block != recovered.read(1024 * 1024):
                    raise SignPDFError("signed content differs from the original")
                if not block:
                    break
        print("Checking CAdES attributes...")
        attributes = run(["openssl", "cms", "-cmsout", "-print", "-inform", "DER", "-in", str(signed)],
                         "CAdES attribute inspection failed", env)
        if b"id-smime-aa-signingCertificateV2" not in attributes:
            raise SignPDFError("required CAdES attribute not found")
        signed.chmod(0o600)
        publish(signed, destination, identity)
    print("\nSignature completed successfully.\nCryptographic verification: PASSED\n"
          "Document integrity: PASSED\nCAdES attribute: PRESENT")
    print(f"Output: {destination}")
    return 0


def main(argv=None):
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser(description="Sign a PDF using a smart card (CAdES).")
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output")
    args = parser.parse_args(argv)
    try:
        return execute(args)
    except ConfigurationError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except SignPDFError as error:
        print(f"Error: {error}", file=sys.stderr)
    except KeyboardInterrupt:
        print("Operation cancelled.", file=sys.stderr)
    except Exception:
        print("Error: signing operation failed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
