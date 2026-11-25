"""Vector signature appearances with embedded fonts and certificate-derived names."""

from pathlib import Path
from io import BytesIO
import unicodedata


FONT_DIRECTORY = Path("/System/Library/Fonts/Supplemental")
BUNDLED_SCRIPT = Path(__file__).resolve().parent / "assets/fonts/KaushanScript-Regular.ttf"


class AppearanceError(Exception):
    """A controlled appearance error that contains no document or credential data."""


def checked_text(value: str, label: str) -> str:
    value = value.strip()
    if not value or len(value) > 200 or any(unicodedata.category(c).startswith("C") for c in value):
        raise AppearanceError(f"{label} must be nonempty, at most 200 characters, and contain no control characters")
    return value


def check_font(path: Path):
    from fontTools.ttLib import TTFont

    if not path.is_file() or path.suffix.lower() not in (".ttf", ".otf"):
        raise AppearanceError("appearance fonts must be existing standalone TTF or OTF files")
    try:
        with TTFont(path) as font:
            flags = font["OS/2"].fsType
            # Accept installable or editable embedding, including font subsetting.
            if (flags and not flags & 8) or flags & (0x100 | 0x200):
                raise AppearanceError("the selected font does not permit editable subset embedding")
            if not font.getBestCmap():
                raise AppearanceError("the selected font has no Unicode character map")
    except AppearanceError:
        raise
    except Exception:
        raise AppearanceError("the selected appearance font could not be read") from None


def appearance_settings(args) -> dict:
    style = args.appearance or "simple"
    location = checked_text(args.location, "location") if args.location is not None else None
    if args.list_fields:
        if style != "simple" or location or args.script_font or args.text_font:
            raise AppearanceError("appearance and location options cannot be used with --list-fields")
        return {}
    if style == "split" and args.invisible:
        raise AppearanceError("--appearance split requires a visible rectangle or existing field")
    if style != "split" and (args.script_font or args.text_font):
        raise AppearanceError("font options require --appearance split")
    result = dict(style=style, location=location, language=args.appearance_language)
    if style == "split":
        try:
            from pyhanko.pdf_utils.font.opentype import GlyphAccumulatorFactory  # noqa: F401
        except ImportError:
            raise AppearanceError("split appearances require pyHanko[opentype]; reinstall signing-tools through Homebrew") from None
        for key, supplied, default in (("script_font", args.script_font, BUNDLED_SCRIPT),
                                        ("text_font", args.text_font, FONT_DIRECTORY / "Arial.ttf")):
            path = (supplied or default).expanduser().resolve()
            check_font(path)
            result[key] = str(path)
    return result


def certificate_name(signer) -> str:
    certificate = signer.signing_cert
    if certificate is None:
        raise AppearanceError("a signing certificate is required for the visible name")
    subject = certificate.subject.native
    given, surname = subject.get("given_name"), subject.get("surname")
    name = f"{given} {surname}" if given and surname else subject.get("common_name")
    if not isinstance(name, str):
        raise AppearanceError("the signing certificate has no supported display name")
    return checked_text(name, "certificate display name")


def detail_lines(name: str, location: str | None, timestamp: str, language: str) -> list[str]:
    date, time = timestamp.split("\n", 1)
    if language == "it":
        lines = ["Firmato digitalmente", f"da: {name.upper()}"]
        if location:
            lines.append(f"Luogo: {location}")
        return lines + [f"Data: {date}", time]
    lines = ["Digitally signed", f"by: {name.upper()}"]
    if location:
        lines.append(f"Location: {location}")
    return lines + [f"Date: {date}", time]


def _shaped_line(engine, text):
    """Measure ink bounds, including overhangs and descenders, before fitting."""
    import uharfbuzz as hb

    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(engine.hb_font, buffer)
    x = y = 0
    bounds = []
    for glyph, position in zip(buffer.glyph_infos, buffer.glyph_positions):
        if glyph.codepoint == 0:
            raise AppearanceError("an appearance font cannot render the required text; choose another font")
        extents = engine.hb_font.get_glyph_extents(glyph.codepoint)
        if extents is not None:
            left = x + position.x_offset + extents.x_bearing
            top = y + position.y_offset + extents.y_bearing
            bounds.append((left, top + extents.height, left + extents.width, top))
        x += position.x_advance
        y += position.y_advance
    if not bounds:
        raise AppearanceError("appearance text has no drawable characters")
    unit = engine.font_size / engine.units_per_em
    box = (min(b[0] for b in bounds), min(b[1] for b in bounds),
           max(b[2] for b in bounds), max(b[3] for b in bounds))
    return engine.shape(text).graphics_ops, tuple(n * unit for n in box)


def _text_block(engine, lines, resource, region, *, centered, size_scale=1):
    leading = engine.font_size * 1.08
    shaped = [_shaped_line(engine, line) for line in lines]
    left = min(box[0] for _, box in shaped)
    bottom = min(box[1] - i * leading for i, (_, box) in enumerate(shaped))
    right = max(box[2] for _, box in shaped)
    top = max(box[3] - i * leading for i, (_, box) in enumerate(shaped))
    x, y, width, height = region
    scale = size_scale * min(width / (right - left), height / (top - bottom))
    offset_x = x + ((width - scale * (right - left)) / 2 if centered else 0) - scale * left
    offset_y = (y + (height - scale * (top - bottom)) / 2 - scale * bottom if centered
                else y + height - scale * top)
    commands = [b"q %g 0 0 %g %g %g cm" % (scale, scale, offset_x, offset_y)]
    for index, (operations, _) in enumerate(shaped):
        commands.append(b"BT /%s %g Tf 1 0 0 1 0 %g Tm "
                        % (resource.encode("ascii"), engine.font_size, -index * leading)
                        + operations + b" ET")
    commands.append(b"Q")
    return b" ".join(commands)


def _font_engine(writer, path, size):
    from pyhanko.pdf_utils import generic
    from pyhanko.pdf_utils.font.opentype import GlyphAccumulator

    # pyHanko 0.38 emits CID widths and TJ adjustments in native font units.
    # PDF metrics require a 1000-unit em. Scale shaping and PDF metrics while
    # preserving the original font program and its OpenType/AAT layout tables.
    class PdfMetricFont(GlyphAccumulator):
        def _get_cid_and_width(self, glyph_id):
            if glyph_id in self._glyphs:
                return self._glyphs[glyph_id]
            cid, width = super()._get_cid_and_width(glyph_id)
            result = cid, round(width * self.pdf_scale)
            self._glyphs[glyph_id] = result
            return result

    engine = PdfMetricFont(writer, BytesIO(Path(path).read_bytes()), font_size=size)
    engine.pdf_scale = 1000 / engine.units_per_em
    engine.units_per_em = 1000
    engine.hb_font.scale = (1000, 1000)
    descriptor = engine.cidfont_obj._font_descriptor
    for key in ("/Ascent", "/Descent", "/CapHeight"):
        descriptor[generic.pdf_name(key)] = generic.FloatObject(float(descriptor[key]) * engine.pdf_scale)
    descriptor[generic.pdf_name("/FontBBox")] = generic.ArrayObject(
        [generic.FloatObject(float(n) * engine.pdf_scale) for n in descriptor["/FontBBox"]])
    return engine


def split_style(rotation: int, settings: dict):
    from pyhanko.pdf_utils import generic
    from pyhanko.pdf_utils.content import ResourceType
    from pyhanko.pdf_utils.layout import BoxConstraints
    from pyhanko.stamp import TextStamp, TextStampStyle

    class SplitStamp(TextStamp):
        def _render_inner_content(self):
            name = checked_text(self.text_params["certificate_name"], "certificate display name")
            script_name = name.title() if name.isupper() else name
            script = _font_engine(self.writer, settings["script_font"], 64)
            regular = _font_engine(self.writer, settings["text_font"], 34)
            left = _text_block(script, [script_name], "SignatureScript", (20, 26, 410, 188), centered=True)
            right = _text_block(regular, detail_lines(name, settings.get("location"), self.text_params["ts"],
                                                     settings["language"]),
                                "SignatureDetails", (500, 24, 480, 192), centered=False, size_scale=0.88)
            for key, engine in (("SignatureScript", script), ("SignatureDetails", regular)):
                self.set_resource(ResourceType.FONT, generic.pdf_name("/" + key), engine.as_resource())
            scale = min(self.box.width / 1000, self.box.height / 240)
            x, y = (self.box.width - 1000 * scale) / 2, (self.box.height - 240 * scale) / 2
            return [b"q 0 g 0 G %g 0 0 %g %g %g cm" % (scale, scale, x, y),
                    left, b"6 w 460 20 m 460 220 l S", right, b"Q"]

        def as_form_xobject(self):
            form = super().as_form_xobject()
            w, h = self.box.width, self.box.height
            matrix = {0: (1, 0, 0, 1, 0, 0), 90: (0, 1, -1, 0, h, 0),
                      180: (-1, 0, 0, -1, w, h), 270: (0, -1, 1, 0, 0, w)}[rotation]
            form[generic.pdf_name("/Matrix")] = generic.ArrayObject([generic.FloatObject(n) for n in matrix])
            return form

    class SplitStyle(TextStampStyle):
        def create_stamp(self, writer, box, text_params):
            if rotation in (90, 270):
                box = BoxConstraints(width=box.height, height=box.width)
            return SplitStamp(writer=writer, style=self, box=box, text_params=text_params)

    return SplitStyle(border_width=0, background=None, timestamp_format="%d/%m/%Y\n%H:%M:%S")
