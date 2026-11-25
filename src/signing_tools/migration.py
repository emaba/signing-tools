"""Transactional migration of known legacy functions and reference settings."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex

from . import config


class MigrationError(Exception):
    """A controlled migration failure that never includes configuration values."""


BRIDGE = b"# Legacy shell functions retired. Homebrew now supplies the executables.\n# This source line may be removed from your shell startup file.\n"


def identity(path):
    if path.is_symlink():
        return "link:" + os.readlink(path)
    if path.is_file():
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return None


def locations(home=None):
    home = home or Path.home()
    return [home / ".config/fish/functions/signpdf.fish",
            home / ".config/fish/functions/signp7m.fish",
            home / ".config/fish/conf.d/signing-tools.fish",
            home / ".config/signing-tools/commands.sh",
            home / ".config/signing-tools/settings.sh"]


def literal_settings(path):
    """Extract only allowlisted literal settings; never source a shell file."""
    allowed = {value for values in config.SIGNING_KEYS.values() for value in values}
    local = {"pkcs11_module": "SIGNP7M_MODULE", "pkcs11_key": "SIGNP7M_KEY_URI",
             "pkcs11_key_id": "SIGNP7M_KEY_ID", "pkcs11_slot": "SIGNP7M_SLOT"}
    found = {}
    for line in path.read_text().splitlines():
        try:
            words = shlex.split(line, comments=True)
        except ValueError:
            continue
        name = value = None
        if words and words[0] == "set":
            index = 1
            while index < len(words) and words[index].startswith("-"):
                index += 1
            if len(words) == index + 2:
                name, value = words[index:]
        elif len(words) == 2 and words[0] == "export" and "=" in words[1]:
            name, value = words[1].split("=", 1)
        name = local.get(name, name)
        if name in allowed and value and not any(c in value for c in ("$", "`")):
            found.setdefault(name, set()).add(value)
    if any(len(values) != 1 for values in found.values()):
        raise MigrationError("ambiguous legacy settings; configure the new application before migration")
    return {name: next(iter(values)) for name, values in found.items()}


def collect(home=None):
    from .signpdf import legacy_pin_reference
    discovered = {}
    candidates = locations(home)
    for path in candidates:
        if not path.is_file() or path.name == "commands.sh":
            continue
        for name, value in literal_settings(path).items():
            discovered.setdefault(name, set()).add(value)
        for target in ("PKCS11_PIN", "SIGNP7M_PIN_REF", "SIGNPDF_PIN_REF"):
            reference = legacy_pin_reference(path, target=target)
            if reference:
                discovered.setdefault(target if target != "PKCS11_PIN" else "SIGNP7M_PIN_REF", set()).add(reference)
    if any(len(values) != 1 for values in discovered.values()):
        raise MigrationError("legacy files contain conflicting settings; configure them explicitly before migration")
    values = {name: next(iter(values)) for name, values in discovered.items()}
    values.update({name: os.environ[name] for names in config.SIGNING_KEYS.values()
                   for name in names if name in os.environ})
    signing = {}
    for name, targets in config.SIGNING_KEYS.items():
        available = [values[target] for target in targets if target in values]
        if available:
            if len(set(available)) > 1:
                raise MigrationError("legacy PDF and P7M settings disagree; configure them explicitly before migration")
            value = available[0]
            if name == "raw_mechanism":
                if value not in ("0", "1"):
                    raise MigrationError("invalid legacy mechanism setting")
                value = value == "1"
            signing[name] = value
    if not config.valid_reference(signing.get("pin_reference")):
        raise MigrationError("no unambiguous PIN reference found; run signing-tools configure locally first")
    return config.validate({"schema": 1, "signing": signing})


def managed_entries(home=None):
    home = home or Path.home()
    paths = locations(home)
    for path in paths:
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_dir():
            raise MigrationError("a legacy command path is a directory; refusing migration")
        if path.suffix == ".fish" and path.parent.name == "functions":
            if path.name == "signpdf.fish" and path.is_symlink():
                expected = home / "Library/Application Support/signp7m/current/app/signpdf.fish"
                if os.readlink(path) != str(expected):
                    raise MigrationError("the PDF Fish function is not the known managed link")
            else:
                text = path.read_text()
                if "PKCS11" not in text or "SafeDive" not in text or "cms -sign" not in text:
                    raise MigrationError("a Fish function is not recognised as the legacy signing tool")
        elif path.name == "commands.sh" and path.is_symlink():
            expected = home / "Library/Application Support/signp7m/current/app/signing-tools.sh"
            if os.readlink(path) != str(expected):
                raise MigrationError("the shell entry is not the known managed link")
        yield path


def write_state(path, state):
    temporary = path.with_name(path.name + ".tmp-" + secrets.token_hex(4))
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(state, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def checked_state(path, home):
    try:
        state = json.loads(path.read_text())
        if state["schema"] != 1 or state["status"] not in ("active", "rolled_back"):
            raise ValueError()
        allowed = {str(value) for value in locations(home)}
        backup_root = (path.parent / "backups").resolve()
        seen = set()
        for entry in state["entries"]:
            original, backup = Path(entry["path"]), Path(entry["backup"])
            if str(original) not in allowed or str(original) in seen:
                raise ValueError()
            seen.add(str(original))
            if not backup.parent.resolve().is_relative_to(backup_root):
                raise ValueError()
        return state
    except (OSError, ValueError, TypeError, KeyError):
        raise MigrationError("invalid migration record; inspect the private record locally") from None


def migrate(*, home=None, destination=None, plan=False):
    home = home or Path.home()
    destination = destination or config.config_path()
    state_path = destination.parent / "migration.json"
    if state_path.is_file():
        state = checked_state(state_path, home)
        if state.get("status") == "active":
            if not destination.is_file():
                raise MigrationError("the migrated configuration is missing; restore it before continuing")
            print("This installation was already migrated.")
            return
    entries = list(managed_entries(home))
    originals = {path: identity(path) for path in entries}
    if destination.exists():
        settings = config.load(destination)
        if not config.valid_reference(settings.get("signing", {}).get("pin_reference")):
            raise MigrationError("configure a PIN reference before retiring the legacy commands")
    else:
        settings = collect(home)
    print("Legacy commands/settings found:", len(entries))
    print("PIN reference: available (value not displayed)")
    print("Configuration:", destination)
    if plan:
        print("Plan only; no configuration or command files were changed.")
        return
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = destination.parent / "backups" / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3))
    backup.mkdir(parents=True, mode=0o700)
    moved = []
    created = False
    created_identity = None
    try:
        if not destination.exists():
            config.create(settings, destination)
            created = True
            created_identity = identity(destination)
        for index, path in enumerate(entries):
            before = identity(path)
            if before != originals[path]:
                raise MigrationError("a legacy file changed during migration; refusing to retire it")
            target = backup / (str(index) + "-" + path.name)
            os.replace(path, target)
            moved.append(dict(path=str(path), backup=str(target), identity=before, bridge=path.name == "commands.sh"))
            if path.name == "commands.sh":
                descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(BRIDGE)
        write_state(state_path, dict(schema=1, status="active", entries=moved,
                    configuration=str(destination), config_created=created, config_identity=identity(destination)))
    except BaseException:
        for entry in reversed(moved):
            path = Path(entry["path"])
            if entry["bridge"] and path.is_file() and path.read_bytes() == BRIDGE:
                path.unlink()
            if not path.exists() and not path.is_symlink():
                os.replace(entry["backup"], path)
        if created and identity(destination) == created_identity:
            destination.unlink(missing_ok=True)
        raise
    print("Migration completed. Legacy files were backed up; the previous application is retained.")
    print("Open a new terminal window to discard previously loaded shell functions.")


def rollback(*, home=None, destination=None, plan=False):
    home = home or Path.home()
    destination = destination or config.config_path()
    state_path = destination.parent / "migration.json"
    if not state_path.is_file():
        raise MigrationError("no migration record exists")
    state = checked_state(state_path, home)
    if state.get("status") != "active":
        raise MigrationError("this migration is not active")
    for entry in state["entries"]:
        path, backup = Path(entry["path"]), Path(entry["backup"])
        if identity(backup) != entry["identity"]:
            raise MigrationError("a legacy backup changed; refusing rollback")
        if path.exists() or path.is_symlink():
            if not entry["bridge"] or path.is_symlink() or path.read_bytes() != BRIDGE:
                raise MigrationError("a legacy path changed; refusing to overwrite it")
    if plan:
        print("Rollback available; legacy backups and destination paths passed checks.")
        return
    restored = []
    try:
        for entry in reversed(state["entries"]):
            path = Path(entry["path"])
            if entry["bridge"]:
                path.unlink()
            os.replace(entry["backup"], path)
            restored.append(entry)
        # Keep the unified configuration as user data, even after rollback.
        state["status"] = "rolled_back"
        write_state(state_path, state)
    except BaseException:
        for entry in reversed(restored):
            path = Path(entry["path"])
            os.replace(path, entry["backup"])
            if entry["bridge"]:
                path.write_bytes(BRIDGE)
                path.chmod(0o600)
        raise
    print("Legacy commands restored. The unified configuration was preserved. Open a new terminal.")
