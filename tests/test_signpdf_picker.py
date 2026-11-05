"""Placement geometry, local server boundaries, cancellation and lifecycle tests."""

from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
import socket
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from test_signpdf import PDFTestBase
import signpdf
import signpdf_picker as picker


class PickerTests(PDFTestBase):
    def session(self):
        return picker.PlacementSession(self.source, signpdf.graphical_pages(signpdf.pdf_reader(self.source)),
                                       1, "Synthetic placement test.pdf", {"style": "simple"})

    def server(self):
        session = self.session()
        server = picker.make_server(session)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        def close():
            server.shutdown()
            server.server_close()
            thread.join()
            session.close()
        self.addCleanup(close)
        return session, server, server.origin + "/" + session.token + "/"

    def request(self, server, url, payload=None, **headers):
        if payload is not None:
            headers = {"Origin": server.origin, "Content-Type": "application/json",
                       "X-Signpdf-Request": "1", **headers}
            data = json.dumps(payload).encode()
        else:
            data = None
        return urlopen(Request(url, data=data, headers=headers), timeout=5)

    def test_invalid_browser_coordinates_are_rejected(self):
        pages = [{"width_mm": 210, "height_mm": 297}]
        for payload in (None, {}, {"page": True, "rect": [0, 0, .5, .1]},
                        {"page": 2, "rect": [0, 0, .5, .1]},
                        {"page": 1, "rect": [0, 0, float("nan"), .1]},
                        {"page": 1, "rect": [0, 0, True, .1]},
                        {"page": 1, "rect": [-.1, 0, .5, .1]},
                        {"page": 1, "rect": [0, 0, 0, .1]},
                        {"page": 1, "rect": [.8, 0, .5, .1]}):
            with self.subTest(payload=payload), self.assertRaises(picker.PickerError):
                picker.selection_mm(payload, pages)

    def test_browser_coordinates_convert_to_physical_millimetres(self):
        pages = [{"width_mm": 210, "height_mm": 297}, {"width_mm": 100, "height_mm": 200}]
        self.assertEqual(picker.selection_mm({"page": 2, "rect": [.1, .2, .5, .1]}, pages),
                         (2, (10, 40, 50, 20)))

    def test_info_serves_structure_warning_for_the_previewed_snapshot(self):
        self.append_legacy_free_xref()
        warnings = signpdf.structure_warnings(self.source)
        session = picker.PlacementSession(
            self.source, signpdf.graphical_pages(signpdf.pdf_reader(self.source)),
            1, "Synthetic test.pdf", {}, warnings=warnings)
        try:
            self.assertEqual(session.info()["warnings"], warnings)
            self.assertEqual(warnings[0]["code"], "free-xref-generation-zero")
            self.assertTrue(session.render(0).startswith(b"\x89PNG"))
        finally:
            session.close()

    def test_preview_matches_crop_rotation_and_user_unit(self):
        from PIL import Image
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import NameObject, DecodedStreamObject
        for rotation in (0, 90, 180, 270):
            with self.subTest(rotation=rotation):
                self.create_pdf(self.source, rotation=rotation, crop=(10, 20, 510, 720), unit=2)
                reader = PdfReader(self.source)
                left, bottom, right, top = signpdf.pdf_box(reader.pages[0], (10, 15, 30, 10))
                writer = PdfWriter()
                writer.clone_document_from_reader(reader)
                content = DecodedStreamObject()
                content.set_data(f"q 1 0 0 rg {left} {bottom} {right-left} {top-bottom} re f Q".encode())
                writer.pages[0][NameObject("/Contents")] = writer._add_object(content)
                with self.source.open("wb") as stream:
                    writer.write(stream)
                session = self.session()
                try:
                    png = session.render(0)
                    with Image.open(BytesIO(png)) as image:
                        page = session.pages[0]
                        x, y = round(25 / page["width_mm"] * image.width), round(20 / page["height_mm"] * image.height)
                        pixel = image.convert("RGB").getpixel((x, y))
                        self.assertEqual(pixel, (255, 0, 0))
                finally:
                    session.close()

    def test_listener_is_bound_exclusively_to_ipv4_loopback(self):
        _, server, _ = self.server()
        self.assertEqual(server.socket.family, socket.AF_INET)
        self.assertEqual(server.socket.getsockname(), ("127.0.0.1", server.server_port))
        self.assertGreater(server.server_port, 0)

    def test_loopback_server_rejects_foreign_origins_and_missing_capability(self):
        _, server, url = self.server()
        for target, headers in ((server.origin + "/api/info", {}),
                                (url + "api/info", {"Host": "untrusted.example"}),
                                (url + "api/info", {"Origin": "https://untrusted.example"}),
                                (url + "api/info", {"Sec-Fetch-Site": "cross-site"})):
            with self.subTest(target=target, headers=headers), self.assertRaises(HTTPError) as error:
                self.request(server, target, **headers)
            self.assertEqual(error.exception.code, 403)
        for headers in ({"Origin": "https://untrusted.example"}, {"X-Signpdf-Request": ""}):
            with self.subTest(headers=headers), self.assertRaises(HTTPError) as error:
                self.request(server, url + "api/cancel", {}, **headers)
            self.assertEqual(error.exception.code, 403)

    def test_loopback_server_serves_only_preview_and_accepts_one_selection(self):
        session, server, url = self.server()
        with self.request(server, url + "api/info") as response:
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertNotIn(str(self.source), response.read().decode())
        with self.request(server, url + "api/pages/0.png") as response:
            self.assertTrue(response.read().startswith(b"\x89PNG\r\n"))
        for path in ("input.pdf", "../signpdf.py", "api/pages/1.png"):
            with self.assertRaises(HTTPError) as error:
                self.request(server, url + path)
            self.assertEqual(error.exception.code, 404)
        with self.request(server, url + "api/select", {"page": 1, "rect": [.1, .2, .5, .1]}) as response:
            self.assertEqual(response.status, 200)
        self.assertTrue(session.done.is_set())
        self.assertEqual(session.result[0], 1)
        with self.assertRaises(HTTPError) as error:
            self.request(server, url + "api/cancel", {})
        self.assertEqual(error.exception.code, 409)

    def test_graphical_cancellation_closes_server(self):
        port = None
        def ready(url):
            nonlocal port
            parts = urlsplit(url)
            port = parts.port
            request = Request(url + "api/cancel", data=b"{}", headers={"Origin": f"{parts.scheme}://{parts.netloc}",
                              "Content-Type": "application/json", "X-Signpdf-Request": "1"})
            with urlopen(request, timeout=5) as response:
                self.assertEqual(response.status, 200)
        with self.assertRaises(picker.PickerCancelled):
            picker.choose_graphical(self.source, signpdf.graphical_pages(signpdf.pdf_reader(self.source)),
                                    1, "Synthetic", {}, open_browser=False, ready=ready)
        with socket.socket() as connection:
            self.assertNotEqual(connection.connect_ex(("127.0.0.1", port)), 0)

    def test_confirmation_and_timeout_close_listener_before_returning(self):
        for confirmed in (True, False):
            with self.subTest(confirmed=confirmed):
                port = None
                def ready(url):
                    nonlocal port
                    parts = urlsplit(url)
                    port = parts.port
                    if confirmed:
                        request = Request(url + "api/select", data=json.dumps(
                            {"page": 1, "rect": [.1, .2, .5, .1]}).encode(), headers={
                                "Origin": f"{parts.scheme}://{parts.netloc}",
                                "Content-Type": "application/json", "X-Signpdf-Request": "1"})
                        with urlopen(request, timeout=5) as response:
                            self.assertEqual(response.status, 200)
                options = dict(open_browser=False, ready=ready, timeout=0)
                arguments = (self.source, signpdf.graphical_pages(signpdf.pdf_reader(self.source)),
                             1, "Synthetic", {})
                if confirmed:
                    self.assertEqual(picker.choose_graphical(*arguments, **options)[0], 1)
                else:
                    with self.assertRaises(picker.PickerCancelled):
                        picker.choose_graphical(*arguments, **options)
                with socket.socket() as connection:
                    self.assertNotEqual(connection.connect_ex(("127.0.0.1", port)), 0)

    def test_default_graphical_cancellation_never_requests_credentials(self):
        args = self.args("--appearance", "simple")
        with patch.object(signpdf, "choose_graphical", side_effect=picker.PickerCancelled), \
             patch.object(signpdf, "signing_settings") as settings, \
             patch.object(signpdf, "authenticate_and_sign") as auth, redirect_stdout(StringIO()):
            self.assertEqual(signpdf.execute(args), 0)
        settings.assert_not_called()
        auth.assert_not_called()
        self.assertEqual(list(self.root.glob(".signpdf.*")), [])
        self.assertFalse((self.root / "document.signed.pdf").exists())


if __name__ == "__main__":
    unittest.main()
