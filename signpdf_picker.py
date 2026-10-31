"""Private loopback-only PDF placement UI; no credentials or signing operations."""

from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import math
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit
import webbrowser


ASSETS = Path(__file__).resolve().parent / "assets/placement"


class PickerError(Exception):
    """A controlled placement error safe for terminal output."""


class PickerCancelled(Exception):
    """Placement ended before any signing was requested."""


def selection_mm(payload, pages):
    """Validate an untrusted browser selection against physical page dimensions."""
    if not isinstance(payload, dict):
        raise PickerError("invalid page selection")
    number, rect = payload.get("page"), payload.get("rect")
    if type(number) is not int or not 1 <= number <= len(pages):
        raise PickerError("invalid page selection")
    if not isinstance(rect, list) or len(rect) != 4:
        raise PickerError("invalid signature rectangle")
    if any(type(n) not in (int, float) or not math.isfinite(n) for n in rect):
        raise PickerError("invalid signature rectangle")
    x, y, width, height = rect
    if min(x, y) < 0 or min(width, height) <= 0 or x >= 1 or y >= 1 or x + width > 1 + 1e-9 or y + height > 1 + 1e-9:
        raise PickerError("signature rectangle falls outside the displayed page")
    width, height = min(width, 1 - x), min(height, 1 - y)
    page = pages[number - 1]
    return number, (x * page["width_mm"], y * page["height_mm"],
                    width * page["width_mm"], height * page["height_mm"])


class PlacementSession:
    def __init__(self, source, pages, initial_page, title, appearance):
        try:
            import pypdfium2 as pdfium
            from PIL import Image  # noqa: F401
        except ImportError:
            raise PickerError("graphical placement needs pypdfium2 and Pillow; install requirements-signpdf.txt") from None
        self.document = pdfium.PdfDocument(str(source))
        if len(self.document) != len(pages):
            self.document.close()
            raise PickerError("PDF preview page count does not match the signing document")
        try:
            self.document.init_forms()
        except Exception:
            self.document.close()
            raise PickerError("PDF forms could not be prepared for preview") from None
        self.pages, self.initial_page = pages, initial_page
        self.title, self.appearance = title, appearance
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.done = threading.Event()
        self.result = None
        self.cache = OrderedDict()

    def info(self):
        return dict(title=self.title, initial_page=self.initial_page,
                    pages=[{k: page[k] for k in ("width_mm", "height_mm")} for page in self.pages],
                    style=self.appearance.get("style", "simple"))

    def render(self, index):
        # PDFium is not thread-safe. Serialize every use of the document.
        with self.lock:
            if index in self.cache:
                self.cache.move_to_end(index)
                return self.cache[index]
            geometry = self.pages[index]
            page = self.document[index]
            bitmap = image = None
            try:
                page.set_cropbox(*geometry["crop"])
                page.set_rotation(geometry["rotation"])
                left, bottom, right, top = geometry["crop"]
                expected = (right - left, top - bottom)
                if geometry["rotation"] in (90, 270):
                    expected = expected[::-1]
                actual = page.get_size()
                if not all(math.isclose(a, b, rel_tol=1e-5, abs_tol=0.02)
                           for a, b in zip(actual, expected)):
                    raise PickerError("PDF preview geometry does not match the signing page")
                scale = min(2.5, 2000 / max(actual))
                bitmap = page.render(scale=scale, draw_annots=True)
                image = bitmap.to_pil()
                buffer = BytesIO()
                image.save(buffer, format="PNG")
                data = buffer.getvalue()
            finally:
                if image is not None:
                    image.close()
                if bitmap is not None:
                    bitmap.close()
                page.close()
            self.cache[index] = data
            while len(self.cache) > 2:
                self.cache.popitem(last=False)
            return data

    def close(self):
        with self.lock:
            self.cache.clear()
            self.document.close()


def make_server(session):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *unused):
            # Do not log document names, capability URLs or request bodies.
            pass

        def reply(self, status, body=b"", content_type="text/plain; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; "
                             "style-src 'self' 'unsafe-inline'; img-src 'self'; font-src 'self'; "
                             "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def route(self, post=False):
            if self.headers.get("Host") != self.server.authority:
                return None
            origin = self.headers.get("Origin")
            if origin is not None and origin != self.server.origin:
                return None
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                return None
            prefix = "/" + session.token + "/"
            path = urlsplit(self.path)
            if not path.path.startswith(prefix) or path.query or path.fragment:
                return None
            if post and (origin != self.server.origin or self.headers.get("X-Signpdf-Request") != "1"
                         or self.headers.get("Content-Type") != "application/json"):
                return None
            return path.path[len(prefix):]

        def do_GET(self):
            route = self.route()
            if route is None:
                return self.reply(403)
            try:
                if route in ("", "app.js", "style.css"):
                    name = route or "index.html"
                    kind = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8",
                            "style.css": "text/css; charset=utf-8"}[name]
                    return self.reply(200, (ASSETS / name).read_bytes(), kind)
                if route == "font.ttf" and session.appearance.get("script_font"):
                    return self.reply(200, Path(session.appearance["script_font"]).read_bytes(), "font/ttf")
                if route == "api/info":
                    return self.reply(200, json.dumps(session.info()).encode(), "application/json")
                if route.startswith("api/pages/") and route.endswith(".png"):
                    number = route[len("api/pages/"):-4]
                    if not number.isascii() or not number.isdigit() or len(number) > 8:
                        return self.reply(404)
                    index = int(number)
                    if not 0 <= index < len(session.pages):
                        return self.reply(404)
                    return self.reply(200, session.render(index), "image/png")
                return self.reply(404)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                # No renderer exception, document data or filesystem path reaches the UI.
                return self.reply(500, b"The page preview could not be rendered.")

        def do_POST(self):
            route = self.route(post=True)
            if route not in ("api/select", "api/cancel"):
                return self.reply(403)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    return self.reply(400)
                payload = json.loads(self.rfile.read(length))
                result = selection_mm(payload, session.pages) if route == "api/select" else None
            except (ValueError, PickerError, UnicodeError):
                return self.reply(400, b"Choose a rectangle inside the page.")
            with session.lock:
                if session.done.is_set():
                    return self.reply(409)
                session.result = result
                try:
                    self.reply(200, b"{}", "application/json")
                finally:
                    session.done.set()

    class QuietServer(ThreadingHTTPServer):
        daemon_threads = False

        def handle_error(self, *unused):
            pass

    # Bind the IPv4 loopback address explicitly; never expose previews on LAN interfaces.
    server = QuietServer(("127.0.0.1", 0), Handler)
    server.authority = f"127.0.0.1:{server.server_port}"
    server.origin = "http://" + server.authority
    return server


def choose_graphical(source, pages, initial_page, title, appearance, *, open_browser=True, ready=None, timeout=1800):
    session = PlacementSession(source, pages, initial_page, title, appearance)
    server = thread = None
    try:
        server = make_server(session)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        thread.start()
        url = f"{server.origin}/{session.token}/"
        if ready is not None:
            ready(url)
        if open_browser:
            if not webbrowser.open(url):
                raise PickerError("the browser could not be opened; use --rect-mm for terminal placement")
            print("Choose the page and signature box in your browser. Confirm there, or cancel with Ctrl+C.")
        deadline = time.monotonic() + timeout
        while not session.done.wait(0.2):
            if time.monotonic() >= deadline:
                raise PickerCancelled()
        if session.result is None:
            raise PickerCancelled()
        return session.result
    finally:
        if server is not None:
            if thread is not None:
                server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
        session.close()
