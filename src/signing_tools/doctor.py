"""Status-only local checks; never resolve a PIN or open a card session."""

import importlib.metadata
import os
from pathlib import Path
import subprocess

from . import config
from .tools import executable, available, provider_directory


def check(*, runtime_only=False):
    results = []

    def report(label, good):
        results.append(bool(good))
        print(("PASS" if good else "FAIL") + ": " + label)

    for name, required in (("pyHanko", "0.38.0"), ("pypdf", "7.1.1"),
                           ("pypdfium2", "5.15.2"), ("Pillow", "13.0.0")):
        try:
            report(name + " " + required, importlib.metadata.version(name) == required)
        except importlib.metadata.PackageNotFoundError:
            report(name + " " + required, False)
    assets = Path(__file__).parent / "assets"
    report("bundled preview assets and cursive font", all((assets / name).is_file() for name in
           ("placement/index.html", "placement/app.js", "placement/style.css", "fonts/KaushanScript-Regular.ttf")))
    try:
        import pypdfium2 as pdfium
        import pkcs11  # noqa: F401
        from PIL import Image  # noqa: F401
        from pyhanko.pdf_utils.font.opentype import GlyphAccumulator  # noqa: F401
        report("native runtime libraries import", pdfium is not None)
    except Exception:
        report("native runtime libraries import", False)
    if not runtime_only:
        report("PIN reference configured (value not displayed)",
               config.valid_reference(os.environ.get("SIGNP7M_PIN_REF", "")))
        from .signpdf import MODULE
        report("PKCS#11 middleware exists", Path(os.environ.get("SIGNP7M_MODULE", MODULE)).is_file())
        for name in ("openssl", "pkcs11-tool", "op"):
            report(name + " is available", available(name))
        try:
            provider = provider_directory()
            report("OpenSSL PKCS#11 provider exists", (provider / "pkcs11prov.dylib").is_file())
            env = {k: v for k, v in os.environ.items() if not v.startswith("op://")
                   and k not in ("PKCS11_PIN", "SIGNPDF_WORKER_PIN")}
            result = subprocess.run([executable("openssl"), "list", "-providers", "-provider-path", str(provider),
                                     "-provider", "default", "-provider", "pkcs11prov"],
                                    env=env, capture_output=True, timeout=30)
            report("OpenSSL loads the PKCS#11 provider", result.returncode == 0)
        except Exception:
            report("OpenSSL loads the PKCS#11 provider", False)
    print("No PIN was resolved and no card login or signature was requested.")
    return 0 if all(results) else 1
