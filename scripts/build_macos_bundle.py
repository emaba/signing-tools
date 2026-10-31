#!/usr/bin/env python3
"""Build a versioned macOS setup ZIP from a committed local Git snapshot."""

import argparse
from datetime import date
import hashlib
from io import BytesIO
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ("START-HERE.md", "FOR-CLAUDE.md", "settings.example.fish",
             "install-fish-extras.fish", "check-setup.py", "settings.example.sh", "install-shell-extras.py")
DEFAULT_FONTS = (
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/System/Library/Fonts/Menlo.ttc"),
)
PRIVATE_SUFFIXES = {".pdf", ".p7m", ".pem", ".der", ".key", ".p12", ".pfx", ".crt", ".cer"}


class BundleError(Exception):
    """A controlled packaging error without source or credential payloads."""


def git(repo, *arguments):
    result = subprocess.run(["git", "-C", str(repo), *arguments], capture_output=True)
    if result.returncode:
        raise BundleError("Git could not read the selected committed snapshot")
    return result.stdout


def safe_source_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise BundleError("the source archive contains an unsafe path")
    if any(part in (".git", ".venv", ".venv-signpdf", ".venv-packaging", "__pycache__") for part in path.parts):
        raise BundleError("the source archive contains a development or Git directory")
    if (path.suffix.lower() in PRIVATE_SUFFIXES or path.name == ".env"
            or path.name.startswith(".env.") or path.name.endswith((".local.fish", ".local.sh"))
            or path.name == "settings.sh"):
        raise BundleError("the source archive contains a document or local credential/configuration file")
    return path


def extract_source(archive, destination):
    with tarfile.open(fileobj=BytesIO(archive), mode="r:") as source:
        for member in source.getmembers():
            path = safe_source_name(member.name)
            target = destination.joinpath(*path.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                data = source.extractfile(member).read()
                if re.search(rb"(?m)^-----BEGIN(?: RSA| EC| OPENSSH)? PRIVATE KEY-----\s*$", data):
                    raise BundleError("the source archive contains private-key material")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            else:
                raise BundleError("linked and special files are not allowed in the source archive")


def checksums(directory):
    lines = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            lines.append(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.relative_to(directory).as_posix())
    return "\n".join(lines) + "\n"


def write_zip(directory, destination, build_date):
    stamp = (max(1980, build_date.year), build_date.month, build_date.day, 0, 0, 0)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            entry = zipfile.ZipInfo("signing-tools-macos/" + path.relative_to(directory).as_posix(), stamp)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes(), compresslevel=9)


def build(repo, ref, output_dir, build_date=None, fonts=DEFAULT_FONTS):
    commit = git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise BundleError("the source commit could not be identified")
    if build_date is None:
        build_date = date.fromisoformat(git(repo, "show", "-s", "--format=%cs", commit).decode().strip())
    if build_date.year < 1980 or build_date.year > 2107:
        raise BundleError("the build date must fit the ZIP timestamp range")
    try:
        fonts = tuple(Path(path).resolve(strict=True) for path in fonts)
        reportlab_version = importlib.metadata.version("reportlab")
        from pypdf import PdfReader
    except (OSError, ImportError, importlib.metadata.PackageNotFoundError):
        raise BundleError("install requirements-packaging.txt and provide the three document fonts") from None
    if reportlab_version != "4.4.9":
        raise BundleError("this renderer requires reportlab 4.4.9; use requirements-packaging.txt")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    name = "signing-tools-macos-" + build_date.isoformat() + ".zip"
    destination = output_dir / name
    with tempfile.TemporaryDirectory(prefix=".signing-bundle-", dir=output_dir) as temporary:
        staging = Path(temporary)
        bundle = staging / "signing-tools-macos"
        source = bundle / "source"
        extract_source(git(repo, "archive", "--format=tar", commit), source)
        for name in TEMPLATES:
            template = source / "packaging/macos" / name
            if not template.is_file():
                raise BundleError("the selected commit does not contain the macOS distribution templates")
            (bundle / name).write_bytes(template.read_bytes())
        renderer = source / "scripts/render_setup_guide.py"
        command = [sys.executable, str(renderer), "--bundle", str(bundle), "--date", build_date.isoformat()]
        for option, font in zip(("--sans-font", "--bold-font", "--mono-font"), fonts):
            command.extend((option, str(font)))
        result = subprocess.run(command, capture_output=True)
        if result.returncode:
            raise BundleError("the guide/sample renderer failed; existing distribution files were kept")
        guide = PdfReader(bundle / "START-HERE.pdf")
        sample = PdfReader(bundle / "sample.pdf")
        if not guide.pages or len(sample.pages) != 3 or sample.is_encrypted or sample.get_fields():
            raise BundleError("the generated guide/sample failed its structural checks")
        info = dict(package="signing-tools-macos", date=build_date.isoformat(), source_commit=commit,
                    language="English", offline_installer=False, contains_credentials=False,
                    guide_pages=len(guide.pages), sample_pages=len(sample.pages), reportlab=reportlab_version,
                    font_sha256={key: hashlib.sha256(font.read_bytes()).hexdigest()
                                 for key, font in zip(("sans", "bold", "mono"), fonts)})
        (bundle / "PACKAGE-INFO.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
        (bundle / "SHA256SUMS.txt").write_text(checksums(bundle))
        archive_path = staging / destination.name
        write_zip(bundle, archive_path, build_date)
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise BundleError("the generated archive failed its integrity check")
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        sha_path = staging / (destination.name + ".sha256")
        sha_path.write_text(digest + "  " + destination.name + "\n")
        os.replace(archive_path, destination)
        os.replace(sha_path, destination.with_name(destination.name + ".sha256"))
    return destination, commit, digest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--ref", default="HEAD", help="committed Git revision; worktree edits are never packaged")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--date", type=date.fromisoformat, help="ISO date; defaults to the source commit date")
    for name, default in zip(("sans", "bold", "mono"), DEFAULT_FONTS):
        parser.add_argument("--" + name + "-font", type=Path, default=default)
    args = parser.parse_args(argv)
    try:
        destination, commit, digest = build(args.repo, args.ref, args.output_dir, args.date,
                                            (args.sans_font, args.bold_font, args.mono_font))
        print(f"Source commit: {commit}\nZIP: {destination}\nSHA-256: {digest}")
        return 0
    except (BundleError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
    except Exception as error:
        print(f"Error: package build failed ({type(error).__name__}).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
