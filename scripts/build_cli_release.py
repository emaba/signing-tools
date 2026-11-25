#!/usr/bin/env python3
"""Build a source/wheel/local-tap distribution from a committed Git snapshot."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile

try:
    from .build_macos_bundle import git, extract_source, checksums
except ImportError:
    from build_macos_bundle import git, extract_source, checksums


ROOT = Path(__file__).resolve().parents[1]


def build(repo, ref, output):
    commit = git(repo, "rev-parse", "--verify", ref + "^{commit}").decode().strip()
    timestamp = git(repo, "show", "-s", "--format=%ct", commit).decode().strip()
    output = Path(output).resolve();output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".cli-release-", dir=output) as temporary:
        staging = Path(temporary);source = staging / "source"
        extract_source(git(repo, "archive", "--format=tar", commit), source)
        metadata = tomllib.loads((source / "pyproject.toml").read_text())
        version = metadata["project"]["version"]
        folder = staging / ("signing-tools-macos-" + version);folder.mkdir()
        result = subprocess.run(["uv", "build", "--python", sys.executable, "--cache-dir", str(output / ".build-cache"),
                                 "--out-dir", str(folder), str(source)],
                                env=os.environ | {"SOURCE_DATE_EPOCH": timestamp}, capture_output=True)
        if result.returncode:
            raise RuntimeError("source/wheel build failed; previous release files were kept")
        for original, name in (("homebrew/resources.json", "resources.json"),
                               ("scripts/generate_homebrew_formula.py", "formula_builder.py"),
                               ("scripts/prepare_local_tap.py", "prepare-local-tap.py"),
                               ("packaging/macos/START-HERE.md", "START-HERE.md"),
                               ("packaging/macos/FOR-CLAUDE.md", "FOR-CLAUDE.md")):
            shutil.copyfile(source / original, folder / name)
        (folder / "PACKAGE-INFO.json").write_text(json.dumps(dict(package="signing-tools", version=version,
            source_commit=commit, architecture="arm64", python="3.12", contains_credentials=False), indent=2) + "\n")
        (folder / "SHA256SUMS.txt").write_text(checksums(folder))
        path = output / (folder.name + ".zip")
        generated = staging / path.name
        stamp = (2026, 1, 1, 0, 0, 0)
        with zipfile.ZipFile(generated, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(folder.iterdir()):
                entry = zipfile.ZipInfo(folder.name + "/" + file.name, stamp)
                entry.compress_type = zipfile.ZIP_DEFLATED;entry.external_attr = 0o100644 << 16
                archive.writestr(entry, file.read_bytes())
        with zipfile.ZipFile(generated) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("release archive integrity check failed")
        os.replace(generated, path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(path.suffix + ".sha256").write_text(digest + "  " + path.name + "\n")
        for file in folder.iterdir():
            shutil.copyfile(file, output / file.name)
    return path, commit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    path, commit = build(args.repo, args.ref, args.output_dir)
    print("Source commit:", commit)
    print("Distribution:", path)


if __name__ == "__main__":
    main()
