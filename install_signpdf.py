#!/usr/bin/env python3
"""Install isolated signpdf releases and one Fish link; never read credentials."""

import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile


SOURCE = Path(__file__).resolve().parent
DEFAULT_PREFIX = Path.home() / "Library/Application Support/signp7m"
DEFAULT_FUNCTIONS = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "fish/functions"
FILES = ("signpdf.py", "signpdf.fish", "signpdf_appearance.py", "signpdf_picker.py",
         "requirements-signpdf.txt", "install_signpdf.py", "README.md", "SECURITY.md",
         "docs/signpdf.md", "docs/installation.md", "docs/macos-smartcard-driver.md",
         "assets/placement/index.html", "assets/placement/style.css", "assets/placement/app.js",
         "assets/fonts/KaushanScript-Regular.ttf", "assets/fonts/OFL-KaushanScript.txt", "assets/fonts/README.md")
FILES += ("signp7m.py", "signing-tools.sh", "packaging/macos/check-setup.py",
          "packaging/macos/settings.example.sh", "docs/shells.md")


class InstallError(Exception):
    """A controlled installation error, without subprocess diagnostic payloads."""


def run(command, message):
    result = subprocess.run([str(x) for x in command], capture_output=True, text=True)
    if result.returncode:
        raise InstallError(message)
    return result.stdout.strip()


def inventory(source):
    result = {}
    for name in FILES:
        path = source / name
        if path.is_symlink() or not path.is_file():
            raise InstallError("the source package is incomplete or contains a linked runtime file")
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    version = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()[:16]
    return version, result


def state_at(prefix):
    if prefix.is_symlink():
        raise InstallError("the installation directory must not be a symbolic link")
    if not prefix.exists():
        return None
    try:
        state = json.loads((prefix / "install.json").read_text())
        if state["application"] == "signpdf" and state["schema"] == 1:
            return state
    except (OSError, ValueError, KeyError, TypeError):
        pass
    raise InstallError("the installation directory already exists and is not managed by this installer")


def write_json(path, value):
    temporary = path.with_name(path.name + ".tmp-" + secrets.token_hex(4))
    try:
        temporary.write_text(json.dumps(value, indent=2) + "\n")
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def symlink_atomic(target, destination):
    temporary = destination.with_name("." + destination.name + ".tmp-" + secrets.token_hex(4))
    try:
        temporary.symlink_to(target)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def copy_entry(source, destination):
    if source.is_symlink():
        destination.symlink_to(os.readlink(source))
    else:
        shutil.copyfile(source, destination)
        destination.chmod(0o600)


def restore_entry(backup, destination):
    temporary = destination.with_name("." + destination.name + ".restore-" + secrets.token_hex(4))
    try:
        copy_entry(backup, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def install(source, prefix, functions, python, uv, cache=None, offline=False, shell="fish"):
    previous = state_at(prefix)
    entry = "signpdf.fish" if shell == "fish" else "signing-tools.sh"
    function = functions / ("signpdf.fish" if shell == "fish" else "commands.sh")
    target = prefix / "current/app" / entry
    if previous and previous["function"] != str(function):
        raise InstallError("this installation manages a different shell entry; review migration before switching")
    if function.exists() and function.is_dir():
        raise InstallError("the shell entry path is a directory")
    if previous and (not function.is_symlink() or os.readlink(function) != str(target)):
        raise InstallError("the installed shell link changed; refusing to overwrite it")
    run([python, "-c", "import sys; assert sys.version_info[:2] == (3, 12)"], "Python 3.12 is required")
    version, hashes = inventory(source)
    release = prefix / "releases" / version
    if previous and previous.get("active") == version:
        if inventory(release / "app")[1] != hashes:
            raise InstallError("the active release was modified; refusing to reuse it")
        print("This version is already installed.")
        return
    if release.exists():
        raise InstallError("this release directory already exists; keep it intact and use another release")
    current = prefix / "current"
    old_current = os.readlink(current) if current.is_symlink() else None
    if current.exists() and not current.is_symlink():
        raise InstallError("the current release path must be a managed symbolic link")
    created_root = not prefix.exists()
    prefix.mkdir(parents=True, exist_ok=True, mode=0o700)
    prefix.chmod(0o700)
    release.mkdir(parents=True, mode=0o700)
    backup = previous.get("backup") if previous else None
    replaced_function = activated = committed = False
    try:
        app = release / "app"
        for name in FILES:
            destination = app / name
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(source / name, destination)
            destination.chmod(0o600)
        environment = release / "venv"
        context = nullcontext(str(cache)) if cache else tempfile.TemporaryDirectory(prefix=".cache-", dir=prefix)
        with context as directory:
            run([uv, "venv", "--no-config", "--no-project", "--no-python-downloads", "--cache-dir", directory,
                 "--python", python, environment], "the isolated Python environment could not be created")
            command = [uv, "pip", "install", "--no-config", "--python", environment / "bin/python",
                       "--cache-dir", directory, "--link-mode", "copy", "-r", app / "requirements-signpdf.txt"]
            if offline:
                command.append("--offline")
            run(command, "dependency installation failed; the previous installation was kept")
        run([environment / "bin/python", app / "signpdf.py", "--help"], "the installed command failed its startup check")
        run([environment / "bin/python", "-c", "import pkcs11, pypdf, pypdfium2, PIL, pyhanko; "
             "from pyhanko.pdf_utils.font.opentype import GlyphAccumulator"], "an installed dependency failed to import")
        if not previous and (function.exists() or function.is_symlink()):
            backup = "backups/entry.original"
            (prefix / "backups").mkdir(mode=0o700)
            copy_entry(function, prefix / backup)
        functions.mkdir(parents=True, exist_ok=True)
        symlink_atomic("releases/" + version, current)
        activated = True
        symlink_atomic(str(target), function)
        replaced_function = True
        write_json(prefix / "install.json", dict(application="signpdf", schema=1,
                   active=version, previous=previous.get("active") if previous else None,
                   function=str(function), backup=backup, hashes=hashes))
        committed = True
    finally:
        if not committed:
            if replaced_function and not previous:
                if backup:
                    restore_entry(prefix / backup, function)
                else:
                    function.unlink(missing_ok=True)
            if activated:
                if old_current is not None:
                    symlink_atomic(old_current, current)
                else:
                    current.unlink(missing_ok=True)
            shutil.rmtree(release)
            if created_root:
                shutil.rmtree(prefix)
    print(f"Installed signpdf release: {version}")
    print(f"Application directory: {prefix}")
    print(f"Shell entry link: {function}")
    print("Open a new terminal window. Existing shell functions and private settings were not changed.")


def uninstall(prefix, trash):
    state = state_at(prefix)
    if state is None:
        raise InstallError("signpdf is not installed at this location")
    function = Path(state["function"])
    entry = "signpdf.fish" if function.name == "signpdf.fish" else "signing-tools.sh"
    if not function.is_symlink() or os.readlink(function) != str(prefix / "current/app" / entry):
        raise InstallError("the shell link changed; refusing to remove or overwrite it")
    if state["backup"]:
        restore_entry(prefix / state["backup"], function)
    else:
        function.unlink()
    trash.mkdir(parents=True, exist_ok=True)
    destination = trash / ("signpdf-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3))
    try:
        shutil.move(str(prefix), str(destination))
    except Exception:
        symlink_atomic(str(prefix / "current/app" / entry), function)
        raise InstallError("the application could not be moved to Trash; its shell link was restored") from None
    print("The managed shell link was removed and the application folder was moved to Trash.")
    print("Existing shell functions, startup files and private settings were not changed.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=DEFAULT_PREFIX)
    parser.add_argument("--shell", choices=("fish", "zsh", "bash"), default="fish",
                        help="shell integration (default: fish, for existing installations)")
    parser.add_argument("--function-dir", type=Path, help="override the shell entry-link directory")
    parser.add_argument("--python", type=Path, default=shutil.which("python3.12"))
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--offline", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="show the intended paths without changing files")
    mode.add_argument("--uninstall", action="store_true", help="remove the managed link and move the app to Trash")
    args = parser.parse_args(argv)
    prefix = args.prefix.expanduser().absolute()
    default_functions = DEFAULT_FUNCTIONS if args.shell == "fish" else Path.home() / ".config/signing-tools"
    functions = (args.function_dir or default_functions).expanduser().absolute()
    try:
        if args.plan:
            state_at(prefix)
            print(f"Application directory: {prefix}")
            print(f"Shell entry link: {functions / ('signpdf.fish' if args.shell == 'fish' else 'commands.sh')}")
            print("Existing signp7m, shell configuration, PATH and macOS reader preferences are preserved.")
            return 0
        if args.uninstall:
            uninstall(prefix, Path.home() / ".Trash")
        else:
            uv = shutil.which("uv")
            if not uv or not args.python:
                raise InstallError("existing uv and Python 3.12 are required; no global software is installed automatically")
            install(SOURCE, prefix, functions, args.python, uv, args.cache_dir, args.offline, args.shell)
        return 0
    except InstallError as error:
        print(f"Error: {error}", file=sys.stderr)
    except KeyboardInterrupt:
        print("Installation cancelled.", file=sys.stderr)
    except Exception as error:
        print(f"Error: installation failed ({type(error).__name__}).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
