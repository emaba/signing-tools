"""Reference-only TOML configuration shared by every installed command."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import tomllib


class ConfigError(Exception):
    """A configuration error safe to display without including its contents."""


SIGNING_KEYS = {
    "pin_reference": ("SIGNP7M_PIN_REF", "SIGNPDF_PIN_REF"),
    "module": ("SIGNP7M_MODULE", "SIGNPDF_MODULE"),
    "key_id": ("SIGNP7M_KEY_ID", "SIGNPDF_KEY_ID"),
    "certificate_id": ("SIGNP7M_CERT_ID", "SIGNPDF_CERT_ID"),
    "token_label": ("SIGNPDF_TOKEN_LABEL",),
    "slot": ("SIGNP7M_SLOT",),
    "key_uri": ("SIGNP7M_KEY_URI",),
    "raw_mechanism": ("SIGNPDF_RAW_MECHANISM",),
}
TOOL_KEYS = {name: "SIGNING_TOOLS_" + name.upper() for name in
             ("openssl", "pkcs11_tool", "onepassword", "provider_path")}


def config_path():
    override = os.environ.get("SIGNING_TOOLS_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "signing-tools/config.toml"


def valid_reference(value):
    component = r"[^/\x00-\x1f\x7f]+"
    return (isinstance(value, str) and re.fullmatch(
        rf"op://{component}/{component}/{component}(?:/{component})?", value) is not None
        and not any(marker in value for marker in ("VAULT_ID", "ITEM_ID", "FIELD_ID")))


def validate(settings):
    if (not isinstance(settings, dict) or set(settings) - {"schema", "signing", "tools"}
            or type(settings.get("schema", 1)) is not int or settings.get("schema", 1) != 1):
        raise ConfigError("unsupported configuration schema or section")
    for section, allowed in (("signing", SIGNING_KEYS), ("tools", TOOL_KEYS)):
        values = settings.get(section, {})
        if not isinstance(values, dict) or set(values) - set(allowed):
            raise ConfigError("unsupported configuration key")
        for name, value in values.items():
            if name == "raw_mechanism":
                if type(value) is not bool:
                    raise ConfigError("raw_mechanism must be a boolean")
            elif not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ConfigError("configuration values must be text without control characters")
            elif name == "pin_reference" and value and not valid_reference(value):
                raise ConfigError("pin_reference must be a 1Password op:// reference, never a PIN")
            elif name == "key_uri" and re.search(r"pin-(?:value|source)=", value, re.I):
                raise ConfigError("key_uri must not contain PIN parameters")
    return settings


def load(path=None):
    path = path or config_path()
    if not path.exists():
        return {"schema": 1}
    try:
        with path.open("rb") as stream:
            return validate(tomllib.load(stream))
    except (OSError, ValueError, TypeError):
        raise ConfigError("the configuration could not be read; inspect it locally without revealing its contents") from None


def encode(settings):
    validate(settings)
    lines = ["# Store only a 1Password reference, never the actual PIN.", "schema = 1", ""]
    for section in ("signing", "tools"):
        if settings.get(section):
            lines.append("[" + section + "]")
            for name, value in sorted(settings[section].items()):
                literal = str(value).lower() if type(value) is bool else json.dumps(value, ensure_ascii=False)
                lines.append(name + " = " + literal)
            lines.append("")
    return "\n".join(lines)


def create(settings, path=None):
    path = path or config_path()
    contents = encode(settings)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(contents)


@contextmanager
def environment(settings=None):
    """Set subprocess settings in this process only; never resolve a secret."""
    settings = load() if settings is None else validate(settings)
    changes = {}
    for name, targets in SIGNING_KEYS.items():
        if name in settings.get("signing", {}):
            value = settings["signing"][name]
            value = ("1" if value else "0") if type(value) is bool else value
            for target in targets:
                if target not in os.environ and value:
                    changes[target] = value
    for name, target in TOOL_KEYS.items():
        if name in settings.get("tools", {}) and target not in os.environ:
            changes[target] = settings["tools"][name]
    os.environ.update(changes)
    try:
        yield
    finally:
        for name in changes:
            os.environ.pop(name, None)
