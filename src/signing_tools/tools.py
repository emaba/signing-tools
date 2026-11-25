"""Resolve external tools independently of shell functions or startup files."""

from functools import lru_cache
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


@lru_cache
def installation_defaults():
    path = Path(sys.prefix) / "share/signing-tools/tools.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def configured(name):
    value = os.environ.get("SIGNING_TOOLS_" + name.upper()) or installation_defaults().get(name)
    return str(value) if value else None


def executable(name):
    key = {"op": "onepassword", "pkcs11-tool": "pkcs11_tool"}.get(name, name)
    explicit = configured(key)
    if explicit:
        return explicit
    found = shutil.which(name)
    if name == "openssl" and found in (None, "/usr/bin/openssl"):
        for prefix in ("/opt/homebrew", "/usr/local"):
            candidate = Path(prefix) / "opt/openssl@4/bin/openssl"
            if candidate.is_file():
                return str(candidate)
    return found or name


def available(name):
    return shutil.which(executable(name)) is not None


def provider_directory():
    explicit = configured("provider_path")
    if explicit:
        return Path(explicit)
    result = subprocess.run(["brew", "--prefix", "libp11"], capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError("libp11 provider directory could not be determined")
    return Path(result.stdout.decode().strip()) / "lib/ossl-modules"
