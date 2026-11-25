"""Installed entry points, common configuration and local management commands."""

import argparse
import getpass
import logging
import os
from pathlib import Path
import secrets
import shutil
import sys

from . import __version__, config


def _sign(which, argv=None):
    logging.disable(logging.CRITICAL)
    argv = sys.argv[1:] if argv is None else argv
    from . import signpdf as pdf, signp7m as p7m
    implementation = pdf if which == "signpdf" else p7m
    try:
        # Help and version remain usable even with an invalid private configuration.
        if "--help" in argv or "-h" in argv or "--version" in argv:
            return implementation.main(argv)
        with config.environment():
            return implementation.main(argv)
    except config.ConfigError as error:
        print("Error: " + str(error), file=sys.stderr)
        return 2


def signpdf():
    return _sign("signpdf")


def signp7m():
    return _sign("signp7m")


def configure(args):
    path = config.config_path()
    if path.is_symlink():
        raise config.ConfigError("the configuration path is a symbolic link; inspect it locally")
    settings = config.load(path)
    signing = settings.setdefault("signing", {})
    print("Enter the 1Password secret reference, never the actual card PIN.")
    print("The reference will not be echoed or printed.")
    reference = getpass.getpass("PIN secret reference (Enter keeps an existing reference): ")
    if reference:
        if not config.valid_reference(reference):
            raise config.ConfigError("expected a 1Password op:// reference; nothing was saved")
        signing["pin_reference"] = reference
    if not config.valid_reference(signing.get("pin_reference")):
        raise config.ConfigError("a PIN secret reference is required; nothing was saved")
    for name in ("module", "slot", "token_label", "key_id", "certificate_id"):
        value = getattr(args, name)
        if value is not None:
            signing[name] = value
    contents = config.encode(settings)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + ".tmp-" + secrets.token_hex(4))
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(contents)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    print("Saved reference-only configuration:", path)
    return 0


def exposed_commands():
    for name in ("signpdf", "signp7m", "signing-tools"):
        found = shutil.which(name)
        expected = Path(sys.prefix) / "bin" / name
        if not found or not expected.is_file() or Path(found).resolve() != expected.resolve():
            return False
    return True


def main(argv=None):
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser(description="Manage the local smart-card signing tools.")
    parser.add_argument("--version", action="version", version="signing-tools " + __version__)
    sub = parser.add_subparsers(dest="command", required=True)
    conf = sub.add_parser("configure", help="store a PIN reference and optional card settings")
    for name in ("module", "slot", "token-label", "key-id", "certificate-id"):
        conf.add_argument("--" + name)
    doctor = sub.add_parser("doctor", help="check local prerequisites without resolving a PIN")
    doctor.add_argument("--runtime-only", action="store_true", help="check package/runtime without personal setup")
    sub.add_parser("config-path", help="show the configuration path, never its contents")
    for name in ("migrate", "rollback"):
        command = sub.add_parser(name, help="migrate legacy shell functions" if name == "migrate" else "restore legacy shell functions")
        command.add_argument("--plan", action="store_true")
    sample = sub.add_parser("sample", help="create an unsigned synthetic three-page PDF")
    sample.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "configure":
            return configure(args)
        if args.command == "config-path":
            print(config.config_path())
            return 0
        if args.command == "doctor":
            from .doctor import check
            if args.runtime_only:
                return check(runtime_only=True)
            with config.environment():
                return check()
        if args.command in ("migrate", "rollback"):
            from .migration import migrate, rollback
            if args.command == "migrate":
                if not args.plan and not exposed_commands():
                    raise config.ConfigError("install the CLI executables on PATH before retiring legacy shell functions")
                migrate(plan=args.plan)
            else:
                rollback(plan=args.plan)
            return 0
        if args.command == "sample":
            from pypdf import PdfWriter
            writer = PdfWriter()
            for _ in range(3):
                writer.add_blank_page(width=595.276, height=841.89)
            with args.output.open("xb") as stream:
                args.output.chmod(0o600)
                writer.write(stream)
            print("Created unsigned synthetic sample:", args.output)
            return 0
    except config.ConfigError as error:
        print("Error: " + str(error), file=sys.stderr)
    except KeyboardInterrupt:
        print("Operation cancelled.", file=sys.stderr)
    except Exception as error:
        from .migration import MigrationError
        if isinstance(error, MigrationError):
            print("Error: " + str(error), file=sys.stderr)
        else:
            print("Error: local management operation failed.", file=sys.stderr)
    return 1
