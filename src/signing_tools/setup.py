"""Interactive card setup and isolated, unauthenticated certificate discovery."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote

from .config import ConfigError


def hexadecimal(value, name):
    if not re.fullmatch(r"(?:[0-9a-fA-F]{2})+", value):
        raise ConfigError(name + " must contain complete hexadecimal bytes")
    return value.lower()


def complete_profile(signing, *, preserve_uri=False):
    """Keep both pipelines on the same token/key; never preserve a stale URI."""
    from .signpdf import MODULE
    result = dict(signing)
    result.setdefault("module", MODULE)
    result.setdefault("token_label", "CNS")
    result.setdefault("key_id", "445334")
    result.setdefault("certificate_id", result["key_id"])
    result.setdefault("slot", "0x2")
    result.setdefault("raw_mechanism", False)
    if not result["token_label"].strip():
        raise ConfigError("token label must not be empty")
    for name in ("key_id", "certificate_id"):
        result[name] = hexadecimal(result[name], name)
    if not re.fullmatch(r"(?:0[xX][0-9a-fA-F]+|[0-9]+)", result["slot"]):
        raise ConfigError("slot must be a nonnegative decimal or hexadecimal slot ID")
    slot = int(result["slot"], 16 if result["slot"].lower().startswith("0x") else 10)
    result["slot"] = hex(slot)
    encoded = "".join("%" + result["key_id"][i:i + 2].upper()
                      for i in range(0, len(result["key_id"]), 2))
    if not preserve_uri or not result.get('key_uri'):
        result["key_uri"] = "pkcs11:token=" + quote(result["token_label"], safe="") + ";id=" + encoded + ";type=private"
    return result


def display(value):
    """Do not let card-provided labels inject terminal controls or new lines."""
    return "".join(c if c.isprintable() else "?" for c in str(value))[:240]


def prompt(label, default=""):
    suffix = " [" + display(default) + "]" if default else ""
    try:
        value = input(label + suffix + ": ").strip()
    except EOFError:
        raise ConfigError("setup needs an interactive terminal; nothing was saved") from None
    return value or default


def choose(label, items, describe, default=None):
    if not items:
        raise ConfigError("no selectable " + label.lower() + "; nothing was saved")
    print(label + ":")
    for index, item in enumerate(items, 1):
        print(f"  {index}. {describe(item)}")
    answer = prompt("Select a number", str(default) if default else "")
    if not answer.isdecimal() or not 1 <= int(answer) <= len(items):
        raise ConfigError("invalid selection; nothing was saved")
    return items[int(answer) - 1]


def inspect_module(module):
    """This code runs only in the timeout-limited discovery child process."""
    import pkcs11
    from asn1crypto import x509

    cards = []
    for slot in pkcs11.lib(module).get_slots(token_present=True)[:32]:
        token = slot.get_token()
        card = dict(slot=hex(slot.slot_id), reader=display(slot.slot_description),
                    token_label=token.label, certificates=[], unavailable=False)
        try:
            # No user_pin, so_pin or PROTECTED_AUTH: no login and no PIN attempts.
            with token.open(rw=False) as session:
                for index, obj in enumerate(session.get_objects({pkcs11.Attribute.CLASS: pkcs11.ObjectClass.CERTIFICATE})):
                    if index >= 64:
                        raise ConfigError("too many public certificates")
                    try:
                        cert_id = bytes(obj[pkcs11.Attribute.ID]).hex()
                        certificate = x509.Certificate.load(bytes(obj[pkcs11.Attribute.VALUE]))
                        if not cert_id or certificate.ca:
                            continue
                        usage = certificate.key_usage_value
                        usages = usage.native if usage is not None else set()
                        if usages and not {"digital_signature", "non_repudiation"}.intersection(usages):
                            continue
                        validity = certificate['tbs_certificate']['validity']
                        now = datetime.now(timezone.utc)
                        valid = validity['not_before'].native <= now <= validity['not_after'].native
                        card['certificates'].append(dict(
                            id=cert_id, label=display(obj[pkcs11.Attribute.LABEL]),
                            name=display(certificate.subject.native.get('common_name', '')),
                            expires=validity['not_after'].native.date().isoformat(), valid=valid,
                            purpose="content commitment / signing" if 'non_repudiation' in usages else "digital signature / check issuer purpose",
                        ))
                    except Exception:
                        # Certificates not readable without authentication are not candidates.
                        continue
        except Exception:
            card['unavailable'] = True
            card['certificates'] = []
        cards.append(card)
    return cards


def discover(module):
    env = {key: value for key, value in os.environ.items()
           if not value.startswith("op://") and key not in
           ("PKCS11_PIN", "SIGNPDF_WORKER_PIN", "OP_SESSION", "OP_SERVICE_ACCOUNT_TOKEN", "OP_CONNECT_TOKEN")
           and not key.startswith("OP_SESSION_")}
    try:
        result = subprocess.run([sys.executable, "-m", "signing_tools.setup", module],
                                env=env, capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired:
        raise ConfigError("card discovery timed out; no PIN was used and nothing was saved") from None
    if result.returncode:
        raise ConfigError("cannot inspect this middleware without login; check the reader/card or use configure --manual")
    try:
        cards = json.loads(result.stdout)
        if not isinstance(cards, list):
            raise ValueError
        return cards
    except ValueError:
        raise ConfigError("middleware discovery returned an invalid response; nothing was saved") from None


def library_path(signing):
    from .signpdf import MODULE
    candidates = []
    for value in (signing.get('module'), MODULE, '/usr/local/lib/libstPKCS11.dylib',
                  '/Library/OpenSC/lib/opensc-pkcs11.so', '/opt/homebrew/lib/opensc-pkcs11.so'):
        if value and Path(value).is_file() and value not in candidates:
            candidates.append(value)
    if candidates:
        module = choose("Installed middleware libraries", candidates + [None],
                        lambda value: display(value) if value else 'Enter another library path', default=1)
    else:
        module = None
    if module is None:
        module = prompt("Issuer-supported PKCS#11 library (absolute path)")
    path = Path(module).expanduser()
    if not path.is_absolute() or not path.is_file():
        raise ConfigError("middleware must be an existing library at an absolute path")
    return str(path)


def guided(signing, *, manual=False):
    print("Card setup reads public certificates only. It will not log in, sign, or access 1Password.")
    print("Keep card/certificate details shown here private. Close other signing apps first.")
    if signing.get('key_uri') and signing['key_uri'] != complete_profile(signing)['key_uri']:
        print("This wizard replaces custom key URI qualifiers with the token/key URI shown before saving.")
    selected = dict(signing)
    selected['module'] = library_path(selected)
    if manual:
        print("Manual setup: enter issuer-confirmed identifiers; no card discovery is performed.")
        for name, label in (("slot", "Slot ID (not list index)"), ("token_label", "Token label"),
                            ("certificate_id", "Signing certificate ID (hex)"), ("key_id", "Private key ID (hex)")):
            selected[name] = prompt(label, selected.get(name, ''))
    else:
        cards = discover(selected['module'])
        card = choose("Cards", cards, lambda value:
                      f"{display(value['reader'])}; token {display(value['token_label'])}; slot {display(value['slot'])}")
        if sum(value['token_label'] == card['token_label'] for value in cards) != 1:
            raise ConfigError("multiple cards have the same token label; connect only the intended card and retry setup")
        certs = [cert for cert in card['certificates'] if cert['valid']]
        if not certs:
            raise ConfigError("no currently valid signing certificate is readable without login; check the issuer or use configure --manual")
        certificate = choose("Signing certificates (choose signing, not CNS authentication)", certs,
                             lambda cert: f"{display(cert['label'])}; {display(cert['name'])}; ID {cert['id']}; "
                             f"expires {cert['expires']}; {cert['purpose']}")
        same_certificate = (selected['module'] == signing.get('module')
                            and card['token_label'] == signing.get('token_label')
                            and certificate['id'] == signing.get('certificate_id'))
        key_default = signing.get('key_id', certificate['id']) if same_certificate else certificate['id']
        selected.update(slot=card['slot'], token_label=card['token_label'], certificate_id=certificate['id'])
        print("The private key is not opened. Its ID normally matches the selected certificate ID;")
        print("change this only if your issuer specifies a different private key ID.")
        if same_certificate and key_default != certificate['id']:
            print("The existing private key ID is retained for this same certificate/token/library.")
        selected['key_id'] = prompt("Private key ID (hex)", key_default)
    if manual:
        raw = prompt("Use the issuer's raw signing mechanism? (y/n)", 'y' if selected.get('raw_mechanism') else 'n').lower()
        if raw not in ('y', 'yes', 'n', 'no'):
            raise ConfigError("answer y or n for the mechanism; nothing was saved")
        selected['raw_mechanism'] = raw in ('y', 'yes')
    selected = complete_profile(selected)
    print("Configuration for both PDF and P7M:")
    for name in ('module', 'slot', 'token_label', 'certificate_id', 'key_id', 'key_uri', 'raw_mechanism'):
        print(f"  {name}: {display(selected[name])}")
    print("  pin_reference: configured (hidden)")
    print("Key URI was derived from the token label and private key ID. The PIN/key match is not verified.")
    if prompt("Save this configuration? (y/N)", 'n').lower() not in ('y', 'yes'):
        raise ConfigError("setup cancelled; nothing was saved")
    return selected


if __name__ == '__main__':
    try:
        print(json.dumps(inspect_module(sys.argv[1])))
    except Exception:
        # Native module errors and public certificate data are never echoed as diagnostics.
        sys.exit(1)
