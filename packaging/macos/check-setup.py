#!/usr/bin/env python3
"""Report prerequisites without reading a PIN, contacting 1Password or logging in."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def main():
    good = True

    def report(label, passed):
        nonlocal good
        good = good and passed
        print(f"{'PASS' if passed else 'FAIL'}: {label}")

    for command in ("brew", "fish", "python3.12", "uv", "openssl", "pkcs11-tool", "op"):
        report(command + " is available", shutil.which(command) is not None)

    reference = os.environ.get("SIGNP7M_PIN_REF", "")
    component = r"[^/\x00-\x1f\x7f]+"
    valid = re.fullmatch(rf"op://{component}/{component}/{component}(?:/{component})?", reference) is not None
    valid = valid and not any(marker in reference for marker in ("VAULT_ID", "ITEM_ID", "FIELD_ID"))
    report("shared PIN reference has a configured URI shape (value not displayed)", valid)

    module = os.environ.get("SIGNPDF_MODULE", os.environ.get("SIGNP7M_MODULE", (
        "/Applications/SafeDive/STCryptoTokenKit.app/Contents/PlugIns/"
        "STToken.appex/Contents/Frameworks/libstPKCS11.dylib")))
    report("configured middleware file exists", Path(module).is_file())

    if shutil.which("brew") and shutil.which("openssl"):
        try:
            prefix = subprocess.run(["brew", "--prefix", "libp11"], capture_output=True, text=True, timeout=30)
            provider = Path(prefix.stdout.strip()) / "lib/ossl-modules/pkcs11prov.dylib"
            report("libp11 provider file exists", prefix.returncode == 0 and provider.is_file())
            version = subprocess.run(["openssl", "version"], capture_output=True, text=True, timeout=15)
            report("selected command is OpenSSL rather than LibreSSL", version.returncode == 0 and version.stdout.startswith("OpenSSL "))
            if prefix.returncode == 0 and provider.is_file():
                result = subprocess.run(["openssl", "list", "-providers", "-provider-path", str(provider.parent),
                                         "-provider", "default", "-provider", "pkcs11prov"],
                                        capture_output=True, text=True, timeout=30)
                report("libp11 provider loads into the selected OpenSSL", result.returncode == 0)
        except Exception:
            report("OpenSSL/provider prerequisite check completed", False)
    print("No PIN was resolved and no card login or signing operation was requested.")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
