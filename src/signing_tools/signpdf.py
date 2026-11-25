#!/usr/bin/env python3
"""Sign PDF documents with an on-card key and explicit placement."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
import importlib.metadata
import json
import logging
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile

from .signpdf_appearance import AppearanceError, appearance_settings, certificate_name, split_style
from .signpdf_picker import PickerCancelled, PickerError, choose_graphical
from . import __version__
from .tools import executable, available


MODULE = (
    "/Applications/SafeDive/STCryptoTokenKit.app/Contents/PlugIns/"
    "STToken.appex/Contents/Frameworks/libstPKCS11.dylib"
)
PIN_ENV = "SIGNPDF_WORKER_PIN"
POINTS_PER_MM = 72 / 25.4


class SignPDFError(Exception):
    """An operational error with a message safe to display."""


@dataclass(frozen=True)
class Placement:
    field: str
    existing: bool
    page: int = 0
    box: tuple[float, float, float, float] | None = None
    rotation: int = 0
    appearance: dict | None = None
    strict_pdf: bool = False


def rectangle(value: str) -> tuple[float, float, float, float]:
    try:
        result = tuple(float(x) for x in value.split(","))
    except ValueError:
        result = ()
    if len(result) != 4 or not all(math.isfinite(x) for x in result):
        raise argparse.ArgumentTypeError("expected four finite numbers: left,top,width,height")
    if min(result[:2]) < 0 or min(result[2:]) <= 0:
        raise argparse.ArgumentTypeError("offsets must be nonnegative; dimensions must be positive")
    return result


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sign a PDF using a smart card (PAdES).")
    p.add_argument("--version", action="version", version="signpdf " + __version__)
    p.add_argument("input", type=Path, help="input PDF; never overwritten")
    p.add_argument("-o", "--output", type=Path, help="output PDF (default: INPUT.signed.pdf)")
    p.add_argument("--strict-pdf", action="store_true",
                   help="reject recoverable PDF syntax/xref issues (default: compatible parsing)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--graphical", action="store_true", help="choose page and rectangle in a local browser (default)")
    mode.add_argument("--list-fields", action="store_true", help="list signature fields without authentication")
    mode.add_argument("--field", help="sign an existing empty signature field by name")
    mode.add_argument("--invisible", action="store_true", help="create an invisible signature")
    mode.add_argument("--rect-mm", type=rectangle, metavar="LEFT,TOP,WIDTH,HEIGHT",
                      help="visible rectangle in mm from the displayed page's top-left corner")
    p.add_argument("--page", help="page number starting at 1, or 'last' (default); initial page in graphical mode")
    p.add_argument("--name", help="name for a new signature field (default: first unused SignatureN)")
    p.add_argument("--appearance", choices=("simple", "split"),
                   help="visible style (default: split for graphical placement, simple for explicit modes)")
    p.add_argument("--location", help="declared signing location; stored in signature metadata")
    p.add_argument("--appearance-language", choices=("it", "en"), default="it",
                   help="labels for split appearances (default: it)")
    p.add_argument("--script-font", type=Path, help="standalone TTF/OTF for the cursive name")
    p.add_argument("--text-font", type=Path, help="standalone TTF/OTF for split-appearance details")
    return p


def pdf_reader(path: Path, *, strict_pdf: bool = False):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SignPDFError("missing pypdf; reinstall signing-tools through Homebrew") from None
    reader = PdfReader(str(path), strict=strict_pdf)
    if reader.is_encrypted:
        raise SignPDFError("encrypted PDFs are not supported in this version")
    if not len(reader.pages):
        raise SignPDFError("the PDF has no pages")
    return reader


def signature_fields(reader) -> dict:
    return {name: field for name, field in (reader.get_fields() or {}).items()
            if str(field.get("/FT")) == "/Sig"}


def filled(field) -> bool:
    from pypdf.generic import NullObject
    value = field.get("/V")
    return value is not None and not isinstance(value, NullObject)


def check_certification(reader):
    permissions = reader.trailer["/Root"].get("/Perms")
    if permissions is None:
        return
    certification = permissions.get_object().get("/DocMDP")
    if certification is None:
        return
    for reference in certification.get_object().get("/Reference", []):
        reference = reference.get_object()
        if (str(reference.get("/TransformMethod")) == "/DocMDP"
                and int(reference.get("/TransformParams", {}).get("/P", 2)) == 1):
            raise SignPDFError("document certification prohibits additional signatures")


def page_rotation(page) -> int:
    raw = float(page.rotation)
    if not math.isfinite(raw) or raw % 90:
        raise SignPDFError("page rotation must be a multiple of 90 degrees")
    return int(raw) % 360


def page_geometry(page):
    """Return the common geometry used by both preview and signing."""
    crop, media = page.cropbox, page.mediabox
    left = max(float(crop.left), float(media.left))
    bottom = max(float(crop.bottom), float(media.bottom))
    right = min(float(crop.right), float(media.right))
    top = min(float(crop.top), float(media.top))
    unit = float(page.user_unit)
    if not all(math.isfinite(x) for x in (left, bottom, right, top, unit)):
        raise SignPDFError("invalid page geometry")
    width, height = right - left, top - bottom
    if min(width, height, unit) <= 0:
        raise SignPDFError("invalid page geometry")
    rotation = page_rotation(page)
    return left, bottom, width, height, unit, rotation


def graphical_pages(reader):
    pages = []
    for page in reader.pages:
        left, bottom, width, height, unit, rotation = page_geometry(page)
        display_w, display_h = (height, width) if rotation in (90, 270) else (width, height)
        pages.append(dict(width_mm=display_w * unit / POINTS_PER_MM,
                          height_mm=display_h * unit / POINTS_PER_MM,
                          crop=(left, bottom, left + width, bottom + height), rotation=rotation))
    return pages


def page_index(value, count):
    try:
        index = count - 1 if value in (None, "last") else int(value) - 1
    except ValueError:
        raise SignPDFError("page must be a positive integer or 'last'") from None
    if not 0 <= index < count:
        raise SignPDFError("page number is outside the document")
    return index


def pdf_box(page, rect_mm) -> tuple[float, float, float, float]:
    """Convert displayed top-left millimetres into unrotated PDF user space."""
    left, bottom, width, height, unit, rotation = page_geometry(page)
    x, y, w, h = (n * POINTS_PER_MM / unit for n in rect_mm)
    display_w, display_h = (height, width) if rotation in (90, 270) else (width, height)
    if x + w > display_w + 1e-7 or y + h > display_h + 1e-7:
        raise SignPDFError("signature rectangle falls outside the displayed page")

    def native(u, v):
        if rotation == 0:
            return left + u, bottom + height - v
        if rotation == 90:
            return left + v, bottom + u
        if rotation == 180:
            return left + width - u, bottom + v
        return left + width - v, bottom + height - u

    corners = [native(u, v) for u in (x, x + w) for v in (y, y + h)]
    return (min(c[0] for c in corners), min(c[1] for c in corners),
            max(c[0] for c in corners), max(c[1] for c in corners))


def choose_placement(args, reader) -> Placement:
    fields = signature_fields(reader)
    all_names = set((reader.get_fields() or {}).keys())
    if args.field:
        if args.field not in fields:
            raise SignPDFError("the requested existing signature field was not found")
        if filled(fields[args.field]):
            raise SignPDFError("the requested signature field is already signed")
        field = fields[args.field]
        pages = reader.get_pages_showing_field(field)
        if len(pages) > 1:
            raise SignPDFError("signature fields with multiple widgets are not supported")
        raw_field = field.indirect_reference.get_object()
        widgets = raw_field.get("/Kids", [raw_field])
        if len(widgets) > 1:
            raise SignPDFError("signature fields with multiple widgets are not supported")
        widget = widgets[0].get_object() if widgets else raw_field
        rotation = page_rotation(pages[0]) if pages and not (int(widget.get("/F", 0)) & 16) else 0
        return Placement(args.field, existing=True, rotation=rotation)
    name = args.name
    if name is None:
        index = 1
        while f"Signature{index}" in all_names:
            index += 1
        name = f"Signature{index}"
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name):
        raise SignPDFError("new field names must start with a letter and contain only letters, digits, '_' or '-'")
    if name in all_names:
        raise SignPDFError("the new field name is already in use")
    if args.invisible:
        return Placement(name, existing=False)
    index = page_index(args.page, len(reader.pages))
    return Placement(name, existing=False, page=index,
                     box=pdf_box(reader.pages[index], args.rect_mm),
                     rotation=page_rotation(reader.pages[index]))


def file_identity(path: Path):
    if not path.exists() and not path.is_symlink():
        return None
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise SignPDFError("output must be a regular file, not a directory or symbolic link")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def output_path(source: Path, requested: Path | None) -> Path:
    raw = requested.expanduser() if requested else source.with_name(source.stem + ".signed.pdf")
    destination = raw.parent.resolve(strict=True) / raw.name
    file_identity(destination)
    if destination == source or (destination.exists() and destination.samefile(source)):
        raise SignPDFError("input and output must be different files")
    return destination


def valid_reference(value: str) -> bool:
    # Named vaults/items can contain spaces; a section is optional.
    component = r"[^/\x00-\x1f\x7f]+"
    return re.fullmatch(rf"op://{component}/{component}/{component}(?:/{component})?", value) is not None


def legacy_pin_reference(path: Path | None = None, *, target="PKCS11_PIN") -> str:
    """Read one literal PIN reference without executing the installed function."""
    path = path or Path.home() / ".config/fish/functions/signp7m.fish"
    if not path.is_file():
        return ""
    assignments: dict[str, set[str | None]] = {}
    allowed_flags = {"-l", "-x", "-g", "-f", "-lx", "-xl", "-gx", "-xg",
                     "--local", "--export", "--global", "--function"}
    for line in path.read_text().splitlines():
        try:
            words = shlex.split(line, comments=True, posix=True)
        except ValueError:
            continue
        if not words or words[0] != "set":
            continue
        if any(flag in words[1:] for flag in ("-e", "--erase", "-q", "--query")):
            continue
        index = 1
        while index < len(words) and words[index].startswith("-"):
            index += 1
        if index >= len(words) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", words[index]):
            continue
        name, values = words[index], words[index + 1:]
        value = values[0] if len(values) == 1 and set(words[1:index]) <= allowed_flags else None
        if value is not None and value.startswith("$"):
            alias_syntax = r'(?:^|\s)(?:"\$[A-Za-z_][A-Za-z0-9_]*"|\$[A-Za-z_][A-Za-z0-9_]*)\s*(?:#.*)?$'
            if not re.search(alias_syntax, line):
                value = None
        assignments.setdefault(name, set()).add(value)

    def resolve(name, seen):
        if name in seen or len(assignments.get(name, ())) != 1:
            return ""
        value = next(iter(assignments[name]))
        if value is None:
            return ""
        if re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", value):
            return resolve(value[1:], seen | {name})
        return value if "$" not in value and valid_reference(value) else ""

    # Follow only unambiguous scalar aliases; never execute or expand Fish code.
    return resolve(target, set())


def signing_settings() -> dict:
    env = os.environ
    reference = env.get("SIGNPDF_PIN_REF", env.get("SIGNP7M_PIN_REF", ""))
    if not valid_reference(reference):
        raise SignPDFError("configure a PIN reference with signing-tools configure or signing-tools migrate")
    module = env.get("SIGNPDF_MODULE", env.get("SIGNP7M_MODULE", MODULE))
    if not Path(module).is_file():
        raise SignPDFError("SafeDive PKCS#11 module not found")
    key_id = env.get("SIGNPDF_KEY_ID", env.get("SIGNP7M_KEY_ID", "445334"))
    cert_id = env.get("SIGNPDF_CERT_ID", key_id)
    for value in (key_id, cert_id):
        if not re.fullmatch(r"(?:[0-9a-fA-F]{2})+", value):
            raise SignPDFError("key and certificate IDs must contain complete hexadecimal bytes")
    token = env.get("SIGNPDF_TOKEN_LABEL", "CNS")
    if not token.strip():
        raise SignPDFError("token label must not be empty")
    raw = env.get("SIGNPDF_RAW_MECHANISM", "0")
    if raw not in ("0", "1"):
        raise SignPDFError("SIGNPDF_RAW_MECHANISM must be 0 or 1")
    if not available("op"):
        raise SignPDFError("1Password CLI 'op' was not found")
    return dict(reference=reference, module=module, token=token, key_id=key_id,
                cert_id=cert_id, raw_mechanism=raw == "1")


def require_signing_dependencies():
    try:
        if importlib.metadata.version("pyHanko") != "0.38.0":
            raise SignPDFError("this version requires pyHanko 0.38.0; reinstall signing-tools through Homebrew")
        import pkcs11  # noqa: F401
    except (ImportError, importlib.metadata.PackageNotFoundError):
        raise SignPDFError("missing signing dependencies; reinstall signing-tools through Homebrew") from None


def structure_issue(error, reader):
    """Map parser failures to public diagnostics without exposing raw PDF data."""
    text = str(error)
    code, message = "strict-structure", "The PDF failed a strict structural check; no further safe detail is available."
    if "a free xref with next generation 0" in text:
        code = "free-xref-generation-zero"
        message = ("A later PDF revision marks a free xref entry with generation 0. "
                   "Strict parsing rejects this because the object history is ambiguous.")
    elif "XRef stream objects must not be clobbered" in text:
        code, message = "overwritten-xref-stream", "A later revision overwrites an internal cross-reference stream."
    elif re.fullmatch(r"Object with id \d+ .*", text):
        code, message = "object-generation-conflict", "An internal object is reused with an inconsistent generation number."
    elif "EOF marker not found" in text:
        code, message = "missing-eof-marker", "The PDF is missing the expected end-of-file marker."
    elif "Multiple definitions in dictionary" in text:
        code, message = "duplicate-dictionary-entry", "A PDF dictionary contains duplicate entries."
    elif "xref table" in text.lower() or "startxref" in text.lower():
        code, message = "xref-structure", "The PDF's internal cross-reference index contains inconsistent entries or offsets."
    return dict(reader=reader, code=code, message=message)


def structure_warnings(path: Path) -> list[dict]:
    """Probe strict parsing after compatible validation, without rewriting bytes."""
    from pypdf.errors import PdfReadError as PyPDFReadError
    from pyhanko.pdf_utils.misc import PdfReadError as PyHankoReadError
    from pyhanko.pdf_utils.reader import PdfFileReader

    issues = []
    try:
        pdf_reader(path, strict_pdf=True)
    except PyPDFReadError as error:
        issues.append(structure_issue(error, "pypdf"))
    try:
        with path.open("rb") as stream:
            PdfFileReader(stream, strict=True)
    except PyHankoReadError as error:
        issues.append(structure_issue(error, "pyHanko"))
    return issues


def report_structure_warnings(issues):
    if issues:
        print("Warning: PDF structure failed strict checks; continuing in compatible mode.", file=sys.stderr)
        for issue in issues:
            print(f"  {issue['reader']} [{issue['code']}]: {issue['message']}", file=sys.stderr)


def verify_pdf(path: Path, expected_names: set[str] | None = None,
               new_field: str | None = None, *, strict_pdf: bool = False) -> set[str]:
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko.sign.validation.status import SignatureCoverageLevel
    from pyhanko_certvalidator import ValidationContext

    with path.open("rb") as stream:
        # Syntax tolerance never skips signature or permitted-change validation.
        reader = PdfFileReader(stream, strict=strict_pdf)
        names = set()
        for signature in reader.embedded_signatures:
            if str(signature.sig_object_type) != "/Sig":
                raise SignPDFError("document timestamps are not supported by this version")
            status = validate_pdf_signature(
                signature, signer_validation_context=ValidationContext(trust_roots=[], allow_fetching=False),
                skip_diff=False,
            )
            if (not status.intact or not status.valid or status.docmdp_ok is not True
                    or status.coverage not in (SignatureCoverageLevel.ENTIRE_FILE,
                                               SignatureCoverageLevel.ENTIRE_REVISION)):
                raise SignPDFError("a PDF signature failed integrity or permitted-change verification")
            if signature.field_name in names:
                raise SignPDFError("duplicate signed field names")
            names.add(signature.field_name)
            if signature.field_name == new_field:
                if status.coverage != SignatureCoverageLevel.ENTIRE_FILE:
                    raise SignPDFError("the new signature does not cover the final document revision")
                if str(signature.sig_object.get("/SubFilter")) != "/ETSI.CAdES.detached":
                    raise SignPDFError("the new signature does not use the PAdES subfilter")
                attributes = {attr["type"].native for attr in signature.signer_info["signed_attrs"]}
                if "signing_certificate_v2" not in attributes:
                    raise SignPDFError("the signing-certificate attribute is missing")
        if expected_names is not None and names != expected_names:
            raise SignPDFError("the output signature fields differ from the expected set")
        return names


def appearance_style(rotation: int, settings: dict | None = None):
    """Keep the appearance upright in the displayed page without moving its box."""
    if settings and settings.get("style") == "split":
        return split_style(rotation, settings)
    from pyhanko.pdf_utils import generic
    from pyhanko.pdf_utils.layout import BoxConstraints
    from pyhanko.pdf_utils.text import TextBoxStyle
    from pyhanko.stamp import TextStamp, TextStampStyle

    class UprightTextStamp(TextStamp):
        def as_form_xobject(self):
            form = super().as_form_xobject()
            w, h = self.box.width, self.box.height
            matrix = {0: (1, 0, 0, 1, 0, 0), 90: (0, 1, -1, 0, h, 0),
                      180: (-1, 0, 0, -1, w, h), 270: (0, -1, 1, 0, 0, w)}[rotation]
            form[generic.pdf_name("/Matrix")] = generic.ArrayObject(
                [generic.FloatObject(value) for value in matrix])
            return form

    class UprightTextStyle(TextStampStyle):
        def create_stamp(self, writer, box, text_params):
            if rotation in (90, 270):
                box = BoxConstraints(width=box.height, height=box.width)
            params = {"signer": "Certificate holder", **text_params}
            return UprightTextStamp(writer=writer, style=self, box=box, text_params=params)

    return UprightTextStyle(border_width=1, background=None,
                            text_box_style=TextBoxStyle(font_size=9),
                            stamp_text="Digitally signed\n%(signer)s\n%(ts)s")


def write_signed_pdf(source: Path, destination: Path, placement: Placement, signer):
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign.fields import SigFieldSpec, SigSeedSubFilter
    from pyhanko.sign.signers import PdfSignatureMetadata, PdfSigner

    settings = placement.appearance or {}
    text_params = ({"certificate_name": certificate_name(signer)}
                   if settings.get("style") == "split" else None)
    metadata = PdfSignatureMetadata(field_name=placement.field, md_algorithm="sha256",
                                    subfilter=SigSeedSubFilter.PADES, location=settings.get("location"))
    field = None if placement.existing else SigFieldSpec(
        sig_field_name=placement.field, on_page=placement.page, box=placement.box)
    with source.open("rb") as incoming, destination.open("wb") as outgoing:
        PdfSigner(metadata, signer=signer, new_field_spec=field,
                  stamp_style=appearance_style(placement.rotation, settings)).sign_pdf(
            IncrementalPdfFileWriter(incoming, strict=placement.strict_pdf), existing_fields_only=placement.existing,
            output=outgoing, appearance_text_params=text_params,
        )


def worker(request_path: Path) -> int:
    # No real PIN is accepted as a command-line argument or stored in a file.
    pin = os.environ.pop(PIN_ENV, None)
    if not pin or pin.startswith("op://"):
        raise SignPDFError("1Password did not provide the worker PIN")
    require_signing_dependencies()
    import pkcs11
    from pyhanko.sign.pkcs11 import PKCS11Signer

    request = json.loads(request_path.read_text())
    settings = request["settings"]
    tokens = list(pkcs11.lib(settings["module"]).get_tokens(token_label=settings["token"]))
    if len(tokens) != 1:
        raise SignPDFError("exactly one token must match the configured token label")
    try:
        with tokens[0].open(user_pin=pin) as session:
            pin = None
            signer = PKCS11Signer(
                session, key_id=bytes.fromhex(settings["key_id"]),
                cert_id=bytes.fromhex(settings["cert_id"]), bulk_fetch=False,
                use_raw_mechanism=settings["raw_mechanism"],
            )
            write_signed_pdf(Path(request["source"]), Path(request["output"]),
                             Placement(**request["placement"]), signer)
    finally:
        pin = None
    return 0


def authenticate_and_sign(source, staged, placement, settings, directory):
    request = directory / "request.json"
    public_settings = {key: value for key, value in settings.items() if key != "reference"}
    request.write_text(json.dumps(dict(source=str(source), output=str(staged),
                                      placement=asdict(placement), settings=public_settings)))
    request.chmod(0o600)
    # op run resolves every reference in its environment. Supply only this one,
    # avoiding duplicate PIN copies or resolution of unrelated references.
    env = {key: value for key, value in os.environ.items()
           if not value.startswith("op://") and key not in ("PKCS11_PIN", PIN_ENV)}
    env[PIN_ENV] = settings["reference"]
    result = subprocess.run(
        [executable("op"), "run", "--", sys.executable, "-m", "signing_tools.worker", str(request)], env=env,
    )
    if result.returncode:
        raise SignPDFError("smart-card signing failed; no output was published")


def check_original_prefix(original: Path, signed: Path):
    with original.open("rb") as first, signed.open("rb") as second:
        while chunk := first.read(1024 * 1024):
            if second.read(len(chunk)) != chunk:
                raise SignPDFError("the original PDF bytes were not preserved")


def publish(staged: Path, destination: Path, original_identity):
    if file_identity(destination) != original_identity:
        raise SignPDFError("output changed during signing; refusing to replace it")
    staged.chmod(0o600)
    if original_identity is None:
        # Same-filesystem link publishes without replacing a newly created path.
        os.link(staged, destination)
    else:
        os.replace(staged, destination)


@contextmanager
def private_workspace(parent: Path):
    with tempfile.TemporaryDirectory(prefix=".signpdf.", dir=parent) as directory:
        path = Path(directory)
        path.chmod(0o700)
        yield path


def execute(args) -> int:
    source = args.input.expanduser().resolve(strict=True)
    if not source.is_file():
        raise SignPDFError("input must be a regular PDF file")
    graphical = args.graphical or not (args.rect_mm is not None or args.field or args.invisible or args.list_fields)
    if args.page is not None and args.rect_mm is None and not graphical:
        raise SignPDFError("--page requires --rect-mm or graphical placement")
    if args.name is not None and (args.field or args.list_fields):
        raise SignPDFError("--name applies only to new visible or invisible signatures")
    if args.appearance is None:
        args.appearance = "split" if graphical else "simple"
    appearance = appearance_settings(args)
    if args.list_fields:
        if args.output is not None:
            raise SignPDFError("--output cannot be used with --list-fields")
        fields = signature_fields(pdf_reader(source, strict_pdf=args.strict_pdf))
        if not fields:
            print("No signature fields found.")
        for name, field in fields.items():
            print(json.dumps(dict(name=name, status="signed" if filled(field) else "empty")))
        return 0

    destination = output_path(source, args.output)
    identity = file_identity(destination)
    # Parse layout before asking for authentication or replacement approval.
    reader = pdf_reader(source, strict_pdf=args.strict_pdf)
    if graphical:
        page_index(args.page, len(reader.pages))
    else:
        choose_placement(args, reader)
    check_certification(reader)
    require_signing_dependencies()
    with private_workspace(destination.parent) as directory:
        snapshot = directory / "input.pdf"
        # Create a private snapshot before launching any credential-bearing child.
        with source.open("rb") as incoming, snapshot.open("xb") as outgoing:
            os.chmod(snapshot, 0o600)
            shutil.copyfileobj(incoming, outgoing)
        reader = pdf_reader(snapshot, strict_pdf=args.strict_pdf)
        check_certification(reader)
        previous = verify_pdf(snapshot, strict_pdf=args.strict_pdf)
        issues = [] if args.strict_pdf else structure_warnings(snapshot)
        report_structure_warnings(issues)
        if graphical:
            try:
                number, rect = choose_graphical(snapshot, graphical_pages(reader),
                                                page_index(args.page, len(reader.pages)) + 1,
                                                source.name, appearance, warnings=issues)
            except PickerCancelled:
                print("Operation cancelled.")
                return 0
            # Apply the same bounds/conversion checks as explicit CLI placement.
            selected = argparse.Namespace(**vars(args))
            selected.page, selected.rect_mm = str(number), rect
            placement = replace(choose_placement(selected, reader), appearance=appearance, strict_pdf=args.strict_pdf)
            print(f"Selected page: {number}; rectangle (mm): " + ",".join(f"{n:.3f}" for n in rect))
        else:
            placement = replace(choose_placement(args, reader), appearance=appearance, strict_pdf=args.strict_pdf)
        settings = signing_settings()
        if identity is not None:
            print(f"The output file already exists:\n{destination}")
            try:
                answer = input("Overwrite existing file? [y/N] ").strip().lower()
            except EOFError:
                answer = ""
            if answer not in ("y", "yes"):
                print("Operation cancelled.")
                return 0
        staged = directory / "signed.pdf"
        print("Authenticating through 1Password...")
        authenticate_and_sign(snapshot, staged, placement, settings, directory)
        print("Verifying PDF signatures and permitted changes...")
        check_original_prefix(snapshot, staged)
        verify_pdf(staged, expected_names=previous | {placement.field}, new_field=placement.field,
                   strict_pdf=args.strict_pdf)
        publish(staged, destination, identity)
    print("\nSignature completed successfully.")
    print("Cryptographic integrity: PASSED")
    print("Previous signatures and permitted changes: PASSED")
    print("PAdES subfilter and signing-certificate attribute: PRESENT")
    print("Certificate trust, revocation and trusted timestamp: NOT VALIDATED")
    print(f"Output: {destination}")
    return 0


def main(argv=None) -> int:
    # Suppress third-party diagnostics that may include document or token data.
    logging.disable(logging.CRITICAL)
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if arguments[:1] == ["--_sign-worker"]:
            if len(arguments) != 2:
                raise SignPDFError("invalid worker invocation")
            return worker(Path(arguments[1]))
        return execute(parser().parse_args(arguments))
    except (SignPDFError, AppearanceError, PickerError) as error:
        print(f"Error: {error}", file=sys.stderr)
    except KeyboardInterrupt:
        print("Operation cancelled.", file=sys.stderr)
        return 130
    except Exception as error:
        # Exception text, tracebacks and environment contents are never printed.
        kind = type(error).__name__
        print(f"Error: PDF operation failed ({kind}).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
