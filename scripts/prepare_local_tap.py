#!/usr/bin/env python3
"""Prepare a local Homebrew tap from a supplied, checksummed source archive."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from formula_builder import generate


def main():
    root = Path(__file__).resolve().parent
    archives = list(root.glob("signing_tools-*.tar.gz"))
    if len(archives) != 1:
        raise SystemExit("Keep exactly one versioned signing_tools source archive beside this helper.")
    archive = archives[0]
    version = archive.name.removeprefix("signing_tools-").removesuffix(".tar.gz")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = (root / "SHA256SUMS.txt").read_text().splitlines()
    if digest + "  " + archive.name not in manifest:
        raise SystemExit("Source archive checksum does not match the distribution manifest.")
    tap = root / "homebrew-tap"
    formula = tap / "Formula/signing-tools.rb"
    content = generate(None, "v" + version, json.loads((root / "resources.json").read_text()),
                       archive=archive.as_uri(), sha256=digest)
    if formula.exists() and formula.read_text() != content:
        raise SystemExit("An existing local formula differs; keep it and prepare a fresh distribution folder.")
    if formula.exists():
        print("The local tap is already prepared:", tap)
        return 0
    formula.parent.mkdir(parents=True)
    formula.write_text(content)
    for arguments in (["init", "-q"], ["add", "Formula/signing-tools.rb"],
                      ["-c", "user.name=Local package", "-c", "user.email=local-package@example.invalid",
                       "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
                       "commit", "-qm", "Prepare versioned local signing-tools formula"]):
        subprocess.run(["git", "-C", str(tap), *arguments], check=True, capture_output=True)
    print("Prepared local Homebrew tap:", tap)
    print('Next: brew tap emaba/signing-tools-local "' + str(tap) + '"')
    print("Then: brew install emaba/signing-tools-local/signing-tools")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
