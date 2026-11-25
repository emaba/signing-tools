"""Safety and geometry tests; optional real PDF signing uses synthetic keys only."""

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import signpdf
import signpdf_appearance

try:
    import pypdf
except ImportError:
    pypdf = None


class PDFTestBase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "document.pdf"
        self.create_pdf(self.source)

    def split_appearance(self, *options, units_per_em=1000):
        # Build a redistributable test font; never depend on proprietary fonts in CI.
        from fontTools.fontBuilder import FontBuilder
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        path = self.root / "synthetic-font.ttf"
        builder = FontBuilder(1000, isTTF=True)
        cmap = {n: f"char{n}" for n in range(32, 256)}
        names = [".notdef", *cmap.values()]
        builder.setupGlyphOrder(names)
        builder.setupCharacterMap(cmap)
        glyphs = {}
        for name in names:
            pen = TTGlyphPen(None)
            if name != "char32":
                pen.moveTo((30, -180))
                pen.lineTo((530, -180))
                pen.lineTo((530, 760))
                pen.lineTo((30, 760))
                pen.closePath()
            glyphs[name] = pen.glyph()
        builder.setupGlyf(glyphs)
        builder.setupHorizontalMetrics({name: (600, 30) for name in names})
        builder.setupHorizontalHeader(ascent=850, descent=-200)
        builder.setupNameTable({"familyName": "Synthetic Test", "styleName": "Regular",
                               "uniqueFontIdentifier": "SyntheticTest-Regular",
                               "fullName": "Synthetic Test Regular", "psName": "SyntheticTest-Regular"})
        builder.setupOS2(sTypoAscender=850, sTypoDescender=-200, usWinAscent=850, usWinDescent=200, fsType=0)
        builder.setupPost()
        if units_per_em != 1000:
            from fontTools.ttLib.scaleUpem import scale_upem
            scale_upem(builder.font, units_per_em)
        builder.save(path)
        args = signpdf.parser().parse_args([str(self.source), "--rect-mm", "10,10,95,25",
                                           "--appearance", "split", "--script-font", str(path),
                                           "--text-font", str(path), *options])
        return signpdf_appearance.appearance_settings(args)

    def create_pdf(self, path, *, rotation=0, crop=None, unit=1, field=None, signed=False):
        from pypdf import PdfWriter
        from pypdf.generic import (ArrayObject, ByteStringObject, DictionaryObject,
                                   FloatObject, NameObject, NumberObject, TextStringObject)
        writer = PdfWriter()
        page = writer.add_blank_page(width=600, height=800)
        page[NameObject("/Rotate")] = NumberObject(rotation)
        page[NameObject("/UserUnit")] = FloatObject(unit)
        if crop is not None:
            page.cropbox = pypdf.generic.RectangleObject(crop)
        if field:
            widget = DictionaryObject({
                NameObject("/FT"): NameObject("/Sig"),
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/T"): TextStringObject(field),
                NameObject("/Rect"): ArrayObject([NumberObject(v) for v in (20, 20, 180, 80)]),
                NameObject("/P"): page.indirect_reference,
            })
            if signed:
                widget[NameObject("/V")] = ByteStringObject(b"synthetic occupied field")
            ref = writer._add_object(widget)
            page[NameObject("/Annots")] = ArrayObject([ref])
            writer.root_object[NameObject("/AcroForm")] = writer._add_object(
                DictionaryObject({NameObject("/Fields"): ArrayObject([ref])}))
        with path.open("wb") as stream:
            writer.write(stream)

    def args(self, *extra):
        return signpdf.parser().parse_args([str(self.source), *extra])

    def append_legacy_free_xref(self):
        """Synthetic incremental save with a generation-zero free xref entry."""
        data = self.source.read_bytes()
        reader = pypdf.PdfReader(self.source)
        root = reader.trailer.raw_get("/Root")
        previous = int(re.findall(rb"startxref\s+(\d+)", data)[-1])
        unused = int(reader.trailer["/Size"])
        prefix = data + b"\n"
        update = (f"xref\n{unused} 1\n0000000000 00000 f \ntrailer\n"
                  f"<< /Size {unused + 1} /Root {root.idnum} {root.generation} R /Prev {previous} >>\n"
                  f"startxref\n{len(prefix)}\n%%EOF\n").encode()
        self.source.write_bytes(prefix + update)


@unittest.skipUnless(pypdf, "pypdf is required for layout and file-safety tests")
class PDFCase(PDFTestBase):
    def test_legacy_xref_warning_is_printed_and_sent_to_graphical_picker(self):
        self.append_legacy_free_xref()
        terminal = io.StringIO()
        with patch.object(signpdf, "choose_graphical", side_effect=signpdf.PickerCancelled) as picker, \
             patch.object(signpdf, "signing_settings") as settings, \
             redirect_stderr(terminal), redirect_stdout(io.StringIO()):
            self.assertEqual(signpdf.execute(self.args()), 0)
        issues = picker.call_args.kwargs["warnings"]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["code"], "free-xref-generation-zero")
        self.assertIn("generation 0", issues[0]["message"])
        self.assertIn(issues[0]["message"], terminal.getvalue())
        self.assertIn("continuing in compatible mode", terminal.getvalue())
        settings.assert_not_called()
        self.assertEqual(list(self.root.glob(".signpdf.*")), [])

    def test_well_formed_pdf_has_no_structure_warnings(self):
        self.assertEqual(signpdf.structure_warnings(self.source), [])

    def test_raw_parser_diagnostics_are_never_reported(self):
        marker = "SYNTHETIC_PRIVATE_PDF_PAYLOAD"
        for message in (marker, "Multiple definitions in dictionary " + marker,
                        "xref table contains " + marker):
            issue = signpdf.structure_issue(Exception(message), "pypdf")
            terminal = io.StringIO()
            with redirect_stderr(terminal):
                signpdf.report_structure_warnings([issue])
            self.assertNotIn(marker, json.dumps(issue) + terminal.getvalue())

    def test_unrecoverable_pdf_still_fails_before_credentials(self):
        self.source.write_bytes(b"SYNTHETIC INVALID PDF\n")
        with patch.object(signpdf, "signing_settings") as settings, \
             patch.object(signpdf, "authenticate_and_sign") as auth:
            with self.assertRaises(Exception):
                signpdf.execute(self.args("--invisible"))
        settings.assert_not_called()
        auth.assert_not_called()

    def test_encrypted_pdf_still_fails_before_credentials(self):
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=600, height=800)
        writer.encrypt("SYNTHETIC TEST PASSWORD")
        with self.source.open("wb") as stream:
            writer.write(stream)
        with patch.object(signpdf, "signing_settings") as settings, \
             patch.object(signpdf, "authenticate_and_sign") as auth:
            with self.assertRaises(signpdf.SignPDFError):
                signpdf.execute(self.args("--invisible"))
        settings.assert_not_called()
        auth.assert_not_called()

    def test_lists_canonical_signature_field_without_authentication(self):
        self.create_pdf(self.source, field="SupplierSignature")
        output = io.StringIO()
        with redirect_stdout(output), patch.object(signpdf, "authenticate_and_sign") as auth:
            self.assertEqual(signpdf.execute(self.args("--list-fields")), 0)
        self.assertEqual(json.loads(output.getvalue()), dict(name="SupplierSignature", status="empty"))
        auth.assert_not_called()

    def test_selects_existing_empty_field(self):
        self.create_pdf(self.source, field="SupplierSignature")
        chosen = signpdf.choose_placement(self.args("--field", "SupplierSignature"),
                                          signpdf.pdf_reader(self.source))
        self.assertEqual(chosen, signpdf.Placement("SupplierSignature", existing=True))

    def test_rejects_missing_and_occupied_fields(self):
        for signed in (False, True):
            self.create_pdf(self.source, field="SupplierSignature", signed=signed)
            name = "SupplierSignature" if signed else "MissingSignature"
            with self.subTest(signed=signed), self.assertRaises(signpdf.SignPDFError):
                signpdf.choose_placement(self.args("--field", name), signpdf.pdf_reader(self.source))

    def test_new_name_does_not_reuse_existing_field(self):
        self.create_pdf(self.source, field="Signature1")
        chosen = signpdf.choose_placement(self.args("--invisible"), signpdf.pdf_reader(self.source))
        self.assertEqual(chosen.field, "Signature2")

    def test_rejects_duplicate_and_invalid_new_names(self):
        self.create_pdf(self.source, field="Signature1")
        for name in ("Signature1", "", "Nested.Field", "1Name", "Line\nBreak"):
            with self.subTest(name=name), self.assertRaises(signpdf.SignPDFError):
                signpdf.choose_placement(self.args("--invisible", "--name", name),
                                         signpdf.pdf_reader(self.source))

    def test_mm_geometry_for_all_quarter_turns(self):
        # A 10x20 unit rectangle starts 30 units right and 40 units down.
        rect = tuple(n / signpdf.POINTS_PER_MM for n in (30, 40, 10, 20))
        expected = {0: (40, 660, 50, 680), 90: (50, 50, 70, 60),
                    180: (470, 60, 480, 80), 270: (450, 680, 470, 690)}
        for rotation, box in expected.items():
            self.create_pdf(self.source, rotation=rotation, crop=(10, 20, 510, 720))
            page = signpdf.pdf_reader(self.source).pages[0]
            actual = signpdf.pdf_box(page, rect)
            with self.subTest(rotation=rotation):
                for observed, wanted in zip(actual, box):
                    self.assertAlmostEqual(observed, wanted)

    def test_user_unit_scales_physical_dimensions(self):
        self.create_pdf(self.source, unit=2)
        page = signpdf.pdf_reader(self.source).pages[0]
        actual = signpdf.pdf_box(page, (0, 0, 25.4, 25.4))
        self.assertEqual(actual, (0, 764, 36, 800))

    def test_crop_is_intersected_with_media_box(self):
        self.create_pdf(self.source, crop=(-100, -100, 900, 900))
        page = signpdf.pdf_reader(self.source).pages[0]
        self.assertEqual(signpdf.pdf_box(page, (0, 0, 25.4, 25.4)), (0, 728, 72, 800))

    def test_rejects_out_of_page_rectangle_and_invalid_page(self):
        for extra in [("--rect-mm", "200,200,50,50"),
                      ("--rect-mm", "0,0,10,10", "--page", "0"),
                      ("--rect-mm", "0,0,10,10", "--page", "2"),
                      ("--rect-mm", "0,0,10,10", "--page", "wrong")]:
            with self.subTest(extra=extra), self.assertRaises(signpdf.SignPDFError):
                signpdf.choose_placement(self.args(*extra), signpdf.pdf_reader(self.source))

    def test_rejects_bad_rectangle_numbers(self):
        for value in ("nan,0,1,1", "0,0,inf,1", "0,0,1", "-1,0,2,2", "0,0,0,2"):
            with self.subTest(value=value), self.assertRaises(Exception):
                signpdf.rectangle(value)

    def test_default_output_is_a_separate_pdf(self):
        self.assertEqual(signpdf.output_path(self.source, None), self.root.resolve() / "document.signed.pdf")

    def test_rejects_input_output_aliases(self):
        hardlink = self.root / "hardlink.pdf"
        os.link(self.source, hardlink)
        alias = self.root / "directory-alias"
        alias.symlink_to(self.root, target_is_directory=True)
        for candidate in (self.source, hardlink, alias / self.source.name):
            with self.subTest(candidate=candidate), self.assertRaises(signpdf.SignPDFError):
                signpdf.output_path(self.source, candidate)

    def test_rejects_output_symlinks_and_directories(self):
        symlink = self.root / "symlink.pdf"
        symlink.symlink_to(self.root / "missing.pdf")
        for candidate in (symlink, self.root):
            with self.subTest(candidate=candidate), self.assertRaises(signpdf.SignPDFError):
                signpdf.output_path(self.source, candidate)

    def test_publish_does_not_replace_a_newly_created_path(self):
        staged = self.root / "staged.pdf"
        staged.write_bytes(b"synthetic signed result")
        output = self.root / "output.pdf"
        output.write_bytes(b"other writer")
        with self.assertRaises(signpdf.SignPDFError):
            signpdf.publish(staged, output, None)
        self.assertEqual(output.read_bytes(), b"other writer")

    def test_publish_permissions_and_changed_output(self):
        staged = self.root / "staged.pdf"
        staged.write_bytes(b"synthetic signed result")
        output = self.root / "output.pdf"
        signpdf.publish(staged, output, None)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        original = signpdf.file_identity(output)
        output.write_bytes(b"changed by another writer")
        with self.assertRaises(signpdf.SignPDFError):
            signpdf.publish(staged, output, original)

    def test_existing_output_survives_signing_failure(self):
        output = self.root / "document.signed.pdf"
        output.write_bytes(b"existing output")
        with patch.object(signpdf, "require_signing_dependencies"), \
             patch.object(signpdf, "signing_settings", return_value={}), \
             patch.object(signpdf, "verify_pdf", return_value=set()), \
             patch.object(signpdf, "authenticate_and_sign", side_effect=signpdf.SignPDFError("test failure")), \
             patch("builtins.input", return_value="y"), redirect_stdout(io.StringIO()):
            with self.assertRaises(signpdf.SignPDFError):
                signpdf.execute(self.args("--invisible"))
        self.assertEqual(output.read_bytes(), b"existing output")
        self.assertEqual(list(self.root.glob(".signpdf.*")), [])

    def test_rejected_verification_never_publishes(self):
        def synthetic_sign(source, staged, *unused):
            staged.write_bytes(source.read_bytes() + b"\n% synthetic test trailer\n")
        with patch.object(signpdf, "require_signing_dependencies"), \
             patch.object(signpdf, "signing_settings", return_value={}), \
             patch.object(signpdf, "verify_pdf", side_effect=[set(), signpdf.SignPDFError("invalid")]), \
             patch.object(signpdf, "authenticate_and_sign", side_effect=synthetic_sign), \
             redirect_stdout(io.StringIO()):
            with self.assertRaises(signpdf.SignPDFError):
                signpdf.execute(self.args("--invisible"))
        self.assertFalse((self.root / "document.signed.pdf").exists())
        self.assertEqual(list(self.root.glob(".signpdf.*")), [])

    def test_cancelled_overwrite_never_authenticates(self):
        (self.root / "document.signed.pdf").write_bytes(b"existing output")
        with patch.object(signpdf, "require_signing_dependencies"), \
             patch.object(signpdf, "signing_settings", return_value={}), \
             patch.object(signpdf, "authenticate_and_sign") as auth, \
             patch("builtins.input", return_value="n"), redirect_stdout(io.StringIO()):
            self.assertEqual(signpdf.execute(self.args("--invisible")), 0)
        auth.assert_not_called()

    def test_preexisting_signature_failure_prevents_authentication(self):
        with patch.object(signpdf, "require_signing_dependencies"), \
             patch.object(signpdf, "signing_settings", return_value={}), \
             patch.object(signpdf, "verify_pdf", side_effect=signpdf.SignPDFError("invalid signature")), \
             patch.object(signpdf, "authenticate_and_sign") as auth:
            with self.assertRaises(signpdf.SignPDFError):
                signpdf.execute(self.args("--invisible"))
        auth.assert_not_called()

    def test_op_request_never_contains_the_secret_reference(self):
        settings = dict(reference="op://TEST_VAULT/TEST_ITEM/TEST_FIELD", module="test-module",
                        token="TEST", key_id="01", cert_id="01", raw_mechanism=False)
        with signpdf.private_workspace(self.root) as directory:
            with patch.object(signpdf.subprocess, "run") as run, \
                 patch.dict(os.environ, {"PKCS11_PIN": "SYNTHETIC_STALE_VALUE", signpdf.PIN_ENV: "SYNTHETIC_STALE_VALUE"}):
                run.return_value.returncode = 0
                signpdf.authenticate_and_sign(self.source, directory / "signed.pdf",
                                              signpdf.Placement("Signature1", False), settings, directory)
            self.assertNotIn("op://", (directory / "request.json").read_text())
            self.assertEqual(run.call_args.kwargs["env"][signpdf.PIN_ENV], settings["reference"])
            self.assertNotIn(settings["reference"], run.call_args.args[0])
            self.assertNotIn("PKCS11_PIN", run.call_args.kwargs["env"])
            self.assertNotIn("SYNTHETIC_STALE_VALUE", run.call_args.kwargs["env"].values())
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)

    def test_exception_payloads_are_not_printed(self):
        output = io.StringIO()
        with patch.object(signpdf, "execute", side_effect=ValueError("SYNTHETIC_DO_NOT_DISPLAY")), \
             redirect_stderr(output):
            self.assertEqual(signpdf.main([str(self.source), "--invisible"]), 1)
        self.assertNotIn("SYNTHETIC_DO_NOT_DISPLAY", output.getvalue())


@unittest.skipUnless(pypdf and importlib.util.find_spec("fontTools"), "fontTools required for appearance tests")
class AppearanceTests(PDFTestBase):
    def test_rejects_invalid_appearance_options_before_authentication(self):
        for options in (("--invisible", "--appearance", "split"),
                        ("--list-fields", "--location", "Genova"),
                        ("--invisible", "--script-font", "unused.ttf"),
                        ("--invisible", "--location", "Genova\nHidden line"),
                        ("--invisible", "--location", "\u202eGenova"),
                        ("--invisible", "--location", " " )):
            args = signpdf.parser().parse_args([str(self.source), *options])
            with self.subTest(options=options), patch.object(signpdf, "authenticate_and_sign") as auth:
                with self.assertRaises(signpdf_appearance.AppearanceError):
                    signpdf.execute(args)
                auth.assert_not_called()

    def test_missing_font_is_rejected(self):
        args = signpdf.parser().parse_args([str(self.source), "--rect-mm", "0,0,95,25",
                                           "--appearance", "split", "--script-font", str(self.root / "absent.ttf")])
        with self.assertRaises(signpdf_appearance.AppearanceError):
            signpdf_appearance.appearance_settings(args)

    def test_embedding_restrictions_are_respected(self):
        from fontTools.ttLib import TTFont
        settings = self.split_appearance()
        path = Path(settings["script_font"])
        for flags in (2, 4, 0x100, 0x200):
            with TTFont(path) as font:
                font["OS/2"].fsType = flags
                font.save(path)
            with self.subTest(flags=flags), self.assertRaises(signpdf_appearance.AppearanceError):
                signpdf_appearance.check_font(path)

    def test_2048_unit_fonts_have_pdf_compatible_metrics(self):
        from pyhanko.pdf_utils.writer import PdfFileWriter
        settings = self.split_appearance(units_per_em=2048)
        engine = signpdf_appearance._font_engine(PdfFileWriter(), settings["text_font"], 34)
        self.assertEqual(engine.tt["head"].unitsPerEm, 2048)
        self.assertEqual(engine.units_per_em, 1000)
        self.assertAlmostEqual(engine.shape("AB").x_advance, 1.2, places=3)
        self.assertTrue(all(abs(width - 600) <= 1 for _, width in engine._glyphs.values()))

    def test_certificate_names_use_given_name_and_surname_before_common_name(self):
        signer = unittest.mock.MagicMock()
        signer.signing_cert.subject.native = dict(given_name="Emilia", surname="Rossi", common_name="OTHER VALUE")
        self.assertEqual(signpdf_appearance.certificate_name(signer), "Emilia Rossi")
        signer.signing_cert.subject.native = dict(common_name="Émilie Rossi")
        self.assertEqual(signpdf_appearance.certificate_name(signer), "Émilie Rossi")
        signer.signing_cert = None
        with self.assertRaises(signpdf_appearance.AppearanceError):
            signpdf_appearance.certificate_name(signer)


class ReferenceTests(unittest.TestCase):
    def test_named_references_with_spaces_and_optional_section(self):
        for reference in ("op://Test Vault/Test Item/password",
                          "op://Test Vault/Test Item/Test Section/password"):
            self.assertTrue(signpdf.valid_reference(reference))

    def test_invalid_references_are_rejected(self):
        for reference in ("", "synthetic literal value", "op://a/b", "op://a//b",
                          "op://a/b/c/d/e", "op://a/b/c\n", "op://a/b/c\x00"):
            with self.subTest(reference=reference):
                self.assertFalse(signpdf.valid_reference(reference))

    def test_legacy_reference_is_read_without_executing_fish(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signp7m.fish"
            path.write_text("function signp7m\n"
                            "    set -lx PKCS11_PIN 'op://Test Vault/Test Item/password'\n"
                            "    touch SHOULD_NEVER_BE_EXECUTED\n"
                            "    set -e PKCS11_PIN\nend\n")
            with patch.object(signpdf.subprocess, "run") as run:
                self.assertEqual(signpdf.legacy_pin_reference(path),
                                 "op://Test Vault/Test Item/password")
            run.assert_not_called()
            self.assertFalse((Path(directory) / "SHOULD_NEVER_BE_EXECUTED").exists())

    def test_ambiguous_or_expanded_legacy_assignments_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signp7m.fish"
            for content in (
                "set -lx PKCS11_PIN 'op://A/B/C'\nset -lx PKCS11_PIN 'op://D/E/F'\n",
                "set -lx PKCS11_PIN 'op://A/B/C'\nset -lx PKCS11_PIN '$reference'\n",
                "set -lx PKCS11_PIN (op read 'op://A/B/C')\n",
                "# set -lx PKCS11_PIN 'op://A/B/C'\n",
            ):
                path.write_text(content)
                self.assertEqual(signpdf.legacy_pin_reference(path), "")

    def test_legacy_scalar_alias_and_cycles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signp7m.fish"
            path.write_text("set -l onepassword_pin_ref 'op://Test Vault/Test Item/password'\n"
                            'set -lx PKCS11_PIN "$onepassword_pin_ref"\n'
                            "set -e PKCS11_PIN\n")
            self.assertEqual(signpdf.legacy_pin_reference(path), "op://Test Vault/Test Item/password")
            path.write_text('set -l reference "$PKCS11_PIN"\nset -lx PKCS11_PIN "$reference"\n')
            self.assertEqual(signpdf.legacy_pin_reference(path), "")
            path.write_text("set -l reference 'op://Test Vault/Item/password'\n"
                            "set -lx PKCS11_PIN '$reference'\n")
            self.assertEqual(signpdf.legacy_pin_reference(path), "")

    def test_explicit_reference_takes_precedence(self):
        with patch.dict(os.environ, {"SIGNPDF_PIN_REF": "op://Explicit Vault/Item/password"}, clear=True), \
             patch.object(signpdf, "legacy_pin_reference") as legacy, \
             patch.object(Path, "is_file", return_value=True), \
             patch.object(signpdf.shutil, "which", return_value="/synthetic/op"):
            self.assertEqual(signpdf.signing_settings()["reference"], "op://Explicit Vault/Item/password")
        legacy.assert_not_called()

    def test_missing_reference_does_not_implicitly_read_fish(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(signpdf, "legacy_pin_reference", return_value="op://Test Vault/Item/password") as legacy, \
             patch.object(Path, "is_file", return_value=True), \
             patch.object(signpdf.shutil, "which", return_value="/synthetic/op"):
            with self.assertRaises(signpdf.SignPDFError):
                signpdf.signing_settings()
            legacy.assert_not_called()

    def test_unrelated_references_are_not_resolved_by_op_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = dict(reference="op://PIN Vault/Item/password")
            with patch.dict(os.environ, {"UNRELATED_REF": "op://Other/Item/password",
                                         "SIGNPDF_PIN_REF": settings["reference"]}, clear=True), \
                 patch.object(signpdf.subprocess, "run") as run:
                run.return_value.returncode = 0
                signpdf.authenticate_and_sign(root / "input.pdf", root / "output.pdf",
                                              signpdf.Placement("Signature1", False), settings, root)
            env = run.call_args.kwargs["env"]
            self.assertNotIn("UNRELATED_REF", env)
            self.assertNotIn("SIGNPDF_PIN_REF", env)
            self.assertEqual(env[signpdf.PIN_ENV], settings["reference"])


@unittest.skipUnless(pypdf and importlib.util.find_spec("pyhanko"), "pyHanko required for real cryptographic PDF tests")
class CryptographicPDFTests(PDFTestBase):
    """Generate synthetic signing material in memory; never load user credentials."""

    @classmethod
    def setUpClass(cls):
        previous_logging_level = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        cls.addClassCleanup(logging.disable, previous_logging_level)
        from asn1crypto import keys, x509 as asn1_x509
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        from pyhanko.sign.signers import SimpleSigner

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic PDF Test Signer")])
        now = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
                .add_extension(x509.KeyUsage(True, True, False, False, False, False, False, False, False), critical=True)
                .sign(key, hashes.SHA256()))
        cls.signer = SimpleSigner(
            signing_cert=asn1_x509.Certificate.load(cert.public_bytes(serialization.Encoding.DER)),
            signing_key=keys.PrivateKeyInfo.load(key.private_bytes(
                serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())),
            cert_registry=None,
        )

    def test_real_invisible_signature(self):
        output = self.root / "signed.pdf"
        signpdf.write_signed_pdf(self.source, output, signpdf.Placement("Signature1", False), self.signer)
        signpdf.check_original_prefix(self.source, output)
        self.assertEqual(signpdf.verify_pdf(output, {"Signature1"}, "Signature1"), {"Signature1"})

    def test_compatible_pipeline_preserves_legacy_xrefs_and_two_signatures(self):
        from pyhanko.pdf_utils.misc import PdfStrictReadError
        self.append_legacy_free_xref()
        original = self.source.read_bytes()
        with self.assertRaises(PdfStrictReadError):
            signpdf.verify_pdf(self.source, strict_pdf=True)
        self.assertEqual(signpdf.verify_pdf(self.source), set())
        def synthetic_card_sign(source, staged, placement, *unused):
            self.assertFalse(placement.strict_pdf)
            signpdf.write_signed_pdf(source, staged, placement, self.signer)
        first, second = self.root / "first.pdf", self.root / "second.pdf"
        with patch.object(signpdf, "signing_settings", return_value={}), \
             patch.object(signpdf, "authenticate_and_sign", side_effect=synthetic_card_sign), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(signpdf.execute(self.args("--invisible", "-o", str(first))), 0)
            args = signpdf.parser().parse_args([str(first), "--invisible", "-o", str(second)])
            self.assertEqual(signpdf.execute(args), 0)
        self.assertEqual(self.source.read_bytes(), original)
        signpdf.check_original_prefix(self.source, first)
        signpdf.check_original_prefix(first, second)
        expected = {"Signature1", "Signature2"}
        self.assertEqual(signpdf.verify_pdf(second, expected, "Signature2"), expected)
        self.assertEqual(list(self.root.glob(".signpdf.*")), [])

    def test_strict_mode_rejects_legacy_xrefs_before_credentials(self):
        from pyhanko.pdf_utils.misc import PdfStrictReadError
        self.append_legacy_free_xref()
        with patch.object(signpdf, "signing_settings") as settings, \
             patch.object(signpdf, "authenticate_and_sign") as auth:
            with self.assertRaises(PdfStrictReadError):
                signpdf.execute(self.args("--invisible", "--strict-pdf"))
        settings.assert_not_called()
        auth.assert_not_called()
        self.assertEqual(list(self.root.glob(".signpdf.*")), [])

    def test_compatible_mode_rejects_tampering_before_credentials(self):
        self.append_legacy_free_xref()
        signed = self.root / "signed.pdf"
        signpdf.write_signed_pdf(self.source, signed, signpdf.Placement("Signature1", False), self.signer)
        data = signed.read_bytes()
        self.assertTrue(data.startswith(b"%PDF-1."))
        # Keep a parseable header but alter bytes covered by the signature.
        signed.write_bytes(data[:7] + (b"4" if data[7:8] != b"4" else b"5") + data[8:])
        with self.assertRaises(signpdf.SignPDFError):
            signpdf.verify_pdf(signed)
        args = signpdf.parser().parse_args([str(signed), "--invisible"])
        with patch.object(signpdf, "signing_settings") as settings, \
             patch.object(signpdf, "authenticate_and_sign") as auth:
            with self.assertRaises(signpdf.SignPDFError):
                signpdf.execute(args)
        settings.assert_not_called()
        auth.assert_not_called()

    def test_strict_mode_signs_well_formed_pdf(self):
        def synthetic_card_sign(source, staged, placement, *unused):
            self.assertTrue(placement.strict_pdf)
            signpdf.write_signed_pdf(source, staged, placement, self.signer)
        with patch.object(signpdf, "signing_settings", return_value={}), \
             patch.object(signpdf, "authenticate_and_sign", side_effect=synthetic_card_sign), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(signpdf.execute(self.args("--invisible", "--strict-pdf")), 0)
        output = self.root / "document.signed.pdf"
        self.assertEqual(signpdf.verify_pdf(output, {"Signature1"}, "Signature1", strict_pdf=True), {"Signature1"})

    def test_default_graphical_pipeline_signs_the_selected_third_page(self):
        from pypdf import PdfWriter
        from pypdf.generic import NameObject, NumberObject
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=600, height=800)
        writer.pages[2][NameObject("/Rotate")] = NumberObject(90)
        with self.source.open("wb") as stream:
            writer.write(stream)
        appearance = self.split_appearance()
        def synthetic_sign(source, staged, placement, *unused):
            self.assertEqual(placement.page, 2)
            self.assertEqual(placement.rotation, 90)
            self.assertEqual(placement.appearance["style"], "split")
            signpdf.write_signed_pdf(source, staged, placement, self.signer)
        def select(source, pages, initial_page, title, style, *, warnings):
            self.assertEqual(warnings, [])
            self.assertEqual(initial_page, 3)
            self.assertEqual(source.read_bytes(), self.source.read_bytes())
            self.assertEqual(stat.S_IMODE(source.stat().st_mode), 0o600)
            return 3, (10, 15, 110, 27)
        with patch.object(signpdf, "appearance_settings", return_value=appearance), \
             patch.object(signpdf, "choose_graphical", side_effect=select), \
             patch.object(signpdf, "signing_settings", return_value={}), \
             patch.object(signpdf, "authenticate_and_sign", side_effect=synthetic_sign), redirect_stdout(io.StringIO()):
            self.assertEqual(signpdf.execute(self.args()), 0)
        output = self.root / "document.signed.pdf"
        signpdf.verify_pdf(output, {"Signature1"}, "Signature1")
        reader = signpdf.pdf_reader(output)
        field = signpdf.signature_fields(reader)["Signature1"].indirect_reference.get_object()
        self.assertEqual(field["/P"].indirect_reference, reader.pages[2].indirect_reference)

    def test_split_appearance_embeds_fonts_and_matches_signature_metadata(self):
        from pypdf.generic import ContentStream
        settings = self.split_appearance("--location", "Genova")
        placement = signpdf.Placement("Signature1", False, box=(20, 20, 300, 100), appearance=settings)
        output = self.root / "split.pdf"
        signpdf.write_signed_pdf(self.source, output, placement, self.signer)
        signpdf.verify_pdf(output, {"Signature1"}, "Signature1")
        reader = signpdf.pdf_reader(output)
        field = signpdf.signature_fields(reader)["Signature1"].indirect_reference.get_object()
        signature = field["/V"].get_object()
        self.assertEqual(signature["/Location"], "Genova")
        appearance = field["/AP"]["/N"].get_object()
        lines = [str(operands[1]["/ActualText"]) for operands, operator in ContentStream(appearance, reader).operations
                 if operator == b"BDC" and len(operands) == 2 and "/ActualText" in operands[1]]
        self.assertIn("Synthetic PDF Test Signer", lines)
        self.assertIn("da: SYNTHETIC PDF TEST SIGNER", lines)
        self.assertIn("Luogo: Genova", lines)
        stamp = datetime.strptime(str(signature["/M"])[2:16], "%Y%m%d%H%M%S")
        self.assertIn("Data: " + stamp.strftime("%d/%m/%Y"), lines)
        self.assertIn(stamp.strftime("%H:%M:%S"), lines)
        fonts = appearance["/Resources"]["/Font"]
        self.assertEqual(len(fonts), 2)
        for font in fonts.values():
            descriptor = font.get_object()["/DescendantFonts"][0].get_object()["/FontDescriptor"]
            self.assertIn("/FontFile2", descriptor)

    def test_split_second_signature_preserves_first_at_all_rotations(self):
        settings = self.split_appearance("--appearance-language", "en")
        for rotation in (0, 90, 180, 270):
            with self.subTest(rotation=rotation):
                self.create_pdf(self.source, rotation=rotation, crop=(10, 20, 510, 720))
                first, second = self.root / "first.pdf", self.root / "second.pdf"
                signpdf.write_signed_pdf(self.source, first, signpdf.Placement("First", False), self.signer)
                placement = signpdf.choose_placement(self.args("--rect-mm", "10,15,95,25"),
                                                      signpdf.pdf_reader(first))
                from dataclasses import replace
                placement = replace(placement, appearance=settings)
                signpdf.write_signed_pdf(first, second, placement, self.signer)
                signpdf.check_original_prefix(first, second)
                self.assertEqual(signpdf.verify_pdf(second), {"First", placement.field})
                field = signpdf.signature_fields(signpdf.pdf_reader(second))[placement.field]
                matrix = field.indirect_reference.get_object()["/AP"]["/N"]["/Matrix"]
                self.assertEqual(list(matrix)[:4], {0: [1, 0, 0, 1], 90: [0, 1, -1, 0],
                                                  180: [-1, 0, 0, -1], 270: [0, -1, 1, 0]}[rotation])

    def test_split_missing_glyph_never_produces_a_valid_output(self):
        settings = self.split_appearance("--location", "東京")
        output = self.root / "bad-font.pdf"
        placement = signpdf.Placement("First", False, box=(20, 20, 300, 100), appearance=settings)
        with self.assertRaises(signpdf_appearance.AppearanceError):
            signpdf.write_signed_pdf(self.source, output, placement, self.signer)

    def test_real_visible_signature_on_rotated_cropped_page(self):
        self.create_pdf(self.source, rotation=90, crop=(10, 20, 510, 720))
        placement = signpdf.choose_placement(self.args("--rect-mm", "10,15,55,20"),
                                              signpdf.pdf_reader(self.source))
        output = self.root / "signed.pdf"
        signpdf.write_signed_pdf(self.source, output, placement, self.signer)
        self.assertEqual(signpdf.verify_pdf(output, {placement.field}, placement.field), {placement.field})

    def test_real_existing_field(self):
        self.create_pdf(self.source, field="SupplierSignature")
        output = self.root / "signed.pdf"
        signpdf.write_signed_pdf(self.source, output, signpdf.Placement("SupplierSignature", True), self.signer)
        self.assertEqual(signpdf.verify_pdf(output, {"SupplierSignature"}, "SupplierSignature"), {"SupplierSignature"})

    def test_real_rotated_existing_field_uses_upright_appearance(self):
        self.create_pdf(self.source, field="SupplierSignature", rotation=90)
        placement = signpdf.choose_placement(self.args("--field", "SupplierSignature"),
                                             signpdf.pdf_reader(self.source))
        self.assertEqual(placement.rotation, 90)
        output = self.root / "signed.pdf"
        signpdf.write_signed_pdf(self.source, output, placement, self.signer)
        signpdf.verify_pdf(output, {placement.field}, placement.field)
        field = signpdf.signature_fields(signpdf.pdf_reader(output))[placement.field]
        widget = field.indirect_reference.get_object()
        matrix = widget["/AP"]["/N"].get_object()["/Matrix"]
        self.assertEqual(list(matrix)[:4], [0, 1, -1, 0])

    def test_real_second_signature_preserves_first(self):
        first, second = self.root / "first.pdf", self.root / "second.pdf"
        signpdf.write_signed_pdf(self.source, first, signpdf.Placement("Signature1", False), self.signer)
        signpdf.write_signed_pdf(first, second, signpdf.Placement("Signature2", False), self.signer)
        signpdf.check_original_prefix(first, second)
        expected = {"Signature1", "Signature2"}
        self.assertEqual(signpdf.verify_pdf(second, expected, "Signature2"), expected)

    def test_tampered_signature_is_rejected(self):
        output = self.root / "signed.pdf"
        signpdf.write_signed_pdf(self.source, output, signpdf.Placement("Signature1", False), self.signer)
        data = output.read_bytes()
        self.assertIn(b"/MediaBox", data)
        output.write_bytes(data.replace(b"/MediaBox", b"/MediaBax", 1))
        with self.assertRaises(Exception):
            signpdf.verify_pdf(output)

    def test_full_document_pipeline_preserves_input_and_adds_two_signatures(self):
        original = self.source.read_bytes()
        def synthetic_card_sign(source, staged, placement, *unused):
            signpdf.write_signed_pdf(source, staged, placement, self.signer)
        with patch.object(signpdf, "signing_settings", return_value={}), \
             patch.object(signpdf, "authenticate_and_sign", side_effect=synthetic_card_sign), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(signpdf.execute(self.args("--invisible")), 0)
            first = self.root / "document.signed.pdf"
            second = self.root / "both.pdf"
            args = signpdf.parser().parse_args([str(first), "--invisible", "-o", str(second)])
            self.assertEqual(signpdf.execute(args), 0)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(signpdf.verify_pdf(second), {"Signature1", "Signature2"})
        self.assertEqual(stat.S_IMODE(second.stat().st_mode), 0o600)
        self.assertEqual(list(self.root.glob(".signpdf.*")), [])

    def test_certified_document_rejects_signing_before_authentication(self):
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.sign.fields import MDPPerm, SigSeedSubFilter
        from pyhanko.sign.signers import PdfSignatureMetadata, PdfSigner
        certified = self.root / "certified.pdf"
        metadata = PdfSignatureMetadata(field_name="Certification", certify=True,
                                        docmdp_permissions=MDPPerm.NO_CHANGES,
                                        subfilter=SigSeedSubFilter.PADES)
        with self.source.open("rb") as incoming, certified.open("wb") as outgoing:
            PdfSigner(metadata, signer=self.signer).sign_pdf(
                IncrementalPdfFileWriter(incoming), output=outgoing)
        args = signpdf.parser().parse_args([str(certified), "--invisible"])
        with patch.object(signpdf, "authenticate_and_sign") as auth:
            with self.assertRaises(signpdf.SignPDFError):
                signpdf.execute(args)
        auth.assert_not_called()

    def test_worker_uses_configured_objects_and_consumes_pin_environment(self):
        import pkcs11
        settings = dict(module="synthetic-module", token="SYNTHETIC_TOKEN", key_id="0102",
                        cert_id="0304", raw_mechanism=False)
        request = self.root / "request.json"
        request.write_text(json.dumps(dict(settings=settings, source=str(self.source),
                                          output=str(self.root / "signed.pdf"),
                                          placement=dict(field="Signature1", existing=False, strict_pdf=True))))
        with patch.dict(os.environ, {signpdf.PIN_ENV: "SYNTHETIC_TEST_PIN"}, clear=True), \
             patch.object(pkcs11, "lib") as library, \
             patch("pyhanko.sign.pkcs11.PKCS11Signer") as signer_factory, \
             patch.object(signpdf, "write_signed_pdf") as write:
            token = library.return_value.get_tokens.return_value = [unittest.mock.MagicMock()]
            library.side_effect = lambda *args: (
                self.assertNotIn(signpdf.PIN_ENV, os.environ) or library.return_value)
            self.assertEqual(signpdf.worker(request), 0)
            token[0].open.assert_called_once_with(user_pin="SYNTHETIC_TEST_PIN")
            self.assertEqual(signer_factory.call_args.kwargs["key_id"], b"\x01\x02")
            self.assertEqual(signer_factory.call_args.kwargs["cert_id"], b"\x03\x04")
            write.assert_called_once()
            self.assertTrue(write.call_args.args[2].strict_pdf)

    def test_worker_rejects_unresolved_reference_before_loading_module(self):
        with patch.dict(os.environ, {signpdf.PIN_ENV: "op://TEST_VAULT/TEST_ITEM/TEST_FIELD"}, clear=True):
            with self.assertRaises(signpdf.SignPDFError):
                signpdf.worker(self.root / "missing-request.json")
            self.assertNotIn(signpdf.PIN_ENV, os.environ)


if __name__ == "__main__":
    unittest.main()
