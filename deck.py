"""Builds a client-facing PowerPoint deck (.pptx) from the consultant's results.

Every chart is a native PowerPoint chart (select it > Edit Data to change the
numbers in Excel), the agenda links to each section, every slide has a link
back to the agenda, and each slide carries speaker notes.

Created by Shenuka Fernando. Copyright (c) 2026 Shenuka Fernando. All rights reserved.
"""

import base64
import threading
from datetime import date
from io import BytesIO
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_MARKER_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from consulting import INDUSTRY_NOTES, TIERS, USE_CASES
from roi import BENCHMARK, CURRENCIES, MINUTES_PER_ACTION, RoiResult

# ---------------------------------------------------------------------------
# Look and feel
# ---------------------------------------------------------------------------

NAVY = "0D2A52"      # dominant dark
BLUE = "2A78D6"      # primary accent (value)
SKY = "CFE3FA"       # light tint of the blue
ORANGE = "EB6834"    # cost only
GREEN = "0E8A5F"     # in place
AMBER = "C2410C"     # gap
INK = "0B0B0B"
MUTED = "5B6472"
GRID = "E3E7EE"
CARD = "F3F6FB"
WHITE = "FFFFFF"
GREY_BAR = "C9CED8"
FONT = "Calibri"

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.6)


def rgb(hex_: str) -> RGBColor:
    return RGBColor.from_string(hex_)


# ---------------------------------------------------------------------------
# Small drawing helpers
# ---------------------------------------------------------------------------

def text(slide, x, y, w, h, value, size=14, bold=False, color=INK, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, italic=False):
    """Add a text box. value can be a string or a list of (text, size, bold, color) paragraphs."""
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paras = value if isinstance(value, list) else [(value, size, bold, color)]
    for i, (t, s, b, c) in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if i:
            p.space_before = Pt(4)
        run = p.add_run()
        run.text = t
        run.font.size, run.font.bold, run.font.name = Pt(s), b, FONT
        run.font.italic = italic
        run.font.color.rgb = rgb(c)
    return box


def box(slide, x, y, w, h, fill=CARD, radius=0.08, shape=MSO_SHAPE.ROUNDED_RECTANGLE, line=None):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(1)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    s.text_frame.margin_left = s.text_frame.margin_right = Inches(0.12)
    return s


def badge(slide, x, y, d, label, fill, color=WHITE, size=16):
    """A filled circle with a character or number in it (the deck's visual motif)."""
    c = box(slide, x, y, d, d, fill=fill, shape=MSO_SHAPE.OVAL)
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size, r.font.bold, r.font.name = Pt(size), True, FONT
    r.font.color.rgb = rgb(color)
    return c


def picture(slide, data: bytes, x, y, max_w, max_h, align_right=False):
    """Add an image scaled to fit max_w x max_h, keeping its proportions."""
    pic = slide.shapes.add_picture(BytesIO(data), x, y, height=max_h)
    if pic.width > max_w:
        ratio = max_w / pic.width
        pic.width, pic.height = int(pic.width * ratio), int(pic.height * ratio)
    if align_right:
        pic.left = x + max_w - pic.width
    pic.top = y + (max_h - pic.height) // 2
    return pic


def notes(slide, value: str):
    slide.notes_slide.notes_text_frame.text = value


def money_format(currency: str, max_value: float) -> str:
    sym = CURRENCIES[currency]
    if abs(max_value) >= 1e6:
        return f'"{sym}"#,##0.0,,"M"'
    if abs(max_value) >= 1e3:
        return f'"{sym}"#,##0,"K"'
    return f'"{sym}"#,##0'


def money(v: float, currency: str) -> str:
    sym = CURRENCIES[currency]
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e6:
        return f"{sign}{sym}{a / 1e6:.2f}M"
    if a >= 1e4:
        return f"{sign}{sym}{a / 1e3:,.0f}K"
    return f"{sign}{sym}{a:,.0f}"


def style_chart(chart, legend=False, size=12):
    chart.font.size, chart.font.name = Pt(size), FONT
    chart.font.color.rgb = rgb(MUTED)
    chart.has_title = False          # single-series charts otherwise get an automatic title
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.TOP
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(size)


def quiet_axes(chart, value_visible=True):
    va = chart.value_axis
    va.has_major_gridlines = value_visible
    if value_visible:
        va.major_gridlines.format.line.color.rgb = rgb(GRID)
    va.format.line.fill.background()
    va.visible = value_visible
    ca = chart.category_axis
    ca.format.line.color.rgb = rgb(GREY_BAR)
    ca.has_major_gridlines = False


# ---------------------------------------------------------------------------
# Logos
# ---------------------------------------------------------------------------

RASTER = {".png", ".jpg", ".jpeg", ".gif"}


def logo_bytes(logo: str | None) -> tuple[bytes | None, str]:
    """Return (image bytes, note). PowerPoint needs PNG/JPG/GIF; SVG and WebP are skipped."""
    if not logo:
        return None, ""
    if logo.startswith("data:"):
        head, _, data = logo.partition(",")
        if any(t in head for t in ("png", "jpeg", "gif")):
            return base64.b64decode(data), ""
        return None, "logo format isn't supported in PowerPoint (use PNG or JPG)"
    if logo.startswith("https://"):
        from dashboard import _download_image
        return logo_bytes(_download_image(logo))
    path = Path(logo).expanduser()
    if path.suffix.lower() not in RASTER:
        return None, f"{path.name} isn't PNG/JPG/GIF, so it was left out of the deck"
    return path.read_bytes(), ""


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

WIDESCREEN = (Inches(13.333), Inches(7.5))
_style_lock = threading.Lock()


def _clear_slides(prs):
    """Remove the template's own slides but keep its masters, layouts and theme."""
    ids = prs.slides._sldIdLst
    for sld in list(ids):
        prs.part.drop_rel(sld.rId)
        ids.remove(sld)


def _theme_colours(prs) -> dict:
    """Read dark 2 and accent 1 from the template's theme, if present."""
    from lxml import etree
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    try:
        theme = prs.slide_master.part.part_related_by(RT.THEME)
        root = etree.fromstring(theme.blob)
    except (KeyError, etree.XMLSyntaxError):
        return {}
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    out = {}
    for name in ("dk2", "accent1", "accent2"):
        el = root.find(f".//a:clrScheme/a:{name}/a:srgbClr", ns)
        if el is not None:
            out[name] = el.get("val").upper()
    return out


def _pick_layout(prs, *names):
    for layout in prs.slide_layouts:
        if any(n in layout.name.lower() for n in names):
            return layout
    return None


def load_template(template: str | None) -> tuple[object | None, str]:
    """Open a .pptx/.potx template. Returns (Presentation or None, note)."""
    if not template:
        return None, ""
    path = Path(template).expanduser()
    if not path.is_file() or path.suffix.lower() not in (".pptx", ".potx"):
        raise ValueError(f"Template not found or not a .pptx/.potx file: {template}")
    if path.suffix.lower() == ".potx":
        # python-pptx opens .pptx; a .potx differs only in its main content type.
        import tempfile, zipfile
        tmp = Path(tempfile.mkdtemp()) / (path.stem + ".pptx")
        with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "[Content_Types].xml":
                    data = data.replace(b"presentationml.template.main+xml", b"presentationml.presentation.main+xml")
                zout.writestr(item, data)
        path = tmp
    prs = Presentation(str(path))
    size = (prs.slide_width, prs.slide_height)
    if abs(size[0] - WIDESCREEN[0]) > Inches(0.05) or abs(size[1] - WIDESCREEN[1]) > Inches(0.05):
        return None, (f"Template '{Path(template).name}' is {size[0] / 914400:.2f} x {size[1] / 914400:.2f} in; "
                      "only widescreen 13.33 x 7.5 in templates are supported, so the standard design was used.")
    _clear_slides(prs)
    return prs, f"Built on template '{Path(template).name}'."


# ---------------------------------------------------------------------------
# The deck
# ---------------------------------------------------------------------------

class Deck:
    def __init__(self, client, currency, partner_name, partner_logo, client_logo, prepared_by, fx,
                 template_prs=None):
        self.template = template_prs is not None
        if self.template:
            self.prs = template_prs
            self.blank_layout = (_pick_layout(self.prs, "blank") or
                                 min(self.prs.slide_layouts, key=lambda l: len(l.placeholders)))
            self.title_layout = _pick_layout(self.prs, "title slide") or self.prs.slide_layouts[0]
        else:
            self.prs = Presentation()
            self.prs.slide_width, self.prs.slide_height = W, H
            self.blank_layout = self.prs.slide_layouts[6]
            self.title_layout = None
        self.client, self.currency, self.fx = client, currency, fx
        self.partner_name, self.prepared_by = partner_name, prepared_by
        self.partner_img, n1 = logo_bytes(partner_logo)
        self.client_img, n2 = logo_bytes(client_logo)
        self.warnings = [n for n in (n1 and f"Partner {n1}", n2 and f"Customer {n2}") if n]
        self.agenda_slide = None
        self.sections = []           # (title, slide)
        self.back_buttons = []

    # -- page furniture ------------------------------------------------------
    def blank(self):
        s = self.prs.slides.add_slide(self.blank_layout)
        for ph in list(s.placeholders):          # template blank layouts sometimes carry placeholders
            ph._element.getparent().remove(ph._element)
        return s

    def dark(self, s):
        """Dark background for title/closing slides (the template's own title layout is used instead)."""
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = rgb(NAVY)

    def content_slide(self, title, subtitle="", section=None):
        s = self.blank()
        text(s, MARGIN, Inches(0.45), Inches(10.4), Inches(0.7), title, size=30, bold=True, color=NAVY)
        if subtitle:
            text(s, MARGIN, Inches(1.12), Inches(10.4), Inches(0.4), subtitle, size=14, color=MUTED)
        # "Agenda" link, wired up once the agenda slide exists
        btn = box(s, W - MARGIN - Inches(1.25), Inches(0.5), Inches(1.25), Inches(0.38), fill=CARD, radius=0.5)
        p = btn.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = "↩ Agenda"
        r.font.size, r.font.name, r.font.color.rgb = Pt(11), FONT, rgb(NAVY)
        self.back_buttons.append(btn)
        footer = f"{self.client} · Microsoft 365 Copilot readiness and business case"
        text(s, MARGIN, H - Inches(0.45), Inches(9), Inches(0.3), footer, size=10, color=MUTED)
        text(s, W - MARGIN - Inches(1), H - Inches(0.45), Inches(1), Inches(0.3),
             str(len(self.prs.slides)), size=10, color=MUTED, align=PP_ALIGN.RIGHT)
        if section:
            self.sections.append((section, s))
        return s

    def logo_plate(self, s, img, x, y, w, h):
        plate = box(s, x, y, w, h, fill=WHITE, radius=0.15)
        picture(s, img, x + Inches(0.15), y + Inches(0.12), w - Inches(0.3), h - Inches(0.24))
        return plate

    # -- slides ----------------------------------------------------------------
    def title(self):
        who = " · ".join(x for x in (f"Prepared by {self.partner_name}" if self.partner_name else "",
                                     self.prepared_by or "", f"{date.today():%d %B %Y}") if x)
        if self.template and self.title_layout is not None:
            s = self.prs.slides.add_slide(self.title_layout)
            filled = 0
            for ph in list(s.placeholders):
                kind = ph.placeholder_format.type
                name = str(kind)
                if "TITLE" in name and "SUB" not in name and filled < 1:
                    ph.text_frame.text = f"{self.client}: Copilot readiness and business case"
                    filled += 1
                elif "SUBTITLE" in name or (ph.placeholder_format.idx == 1 and "BODY" in name):
                    ph.text_frame.text = who
                else:
                    ph._element.getparent().remove(ph._element)
            logos = [img for img in (self.client_img, self.partner_img) if img]
            for i, img in enumerate(logos):
                self.logo_plate(s, img, W - MARGIN - Inches(2.2) - i * Inches(2.5), H - Inches(1.75),
                                Inches(2.2), Inches(1.2))
            notes(s, f"Welcome. Today we cover where {self.client} stands on Copilot readiness, "
                     "the recommended approach and the business case. Use the agenda to jump to any section.")
            return
        s = self.blank()
        self.dark(s)
        y = Inches(0.6)
        if self.client_img:
            self.logo_plate(s, self.client_img, MARGIN, y, Inches(2.6), Inches(1.2))
        if self.partner_img:
            self.logo_plate(s, self.partner_img, W - MARGIN - Inches(1.9), y, Inches(1.9), Inches(1.45))
        text(s, MARGIN, Inches(2.55), Inches(11), Inches(0.5), "MICROSOFT 365 COPILOT", size=14, bold=True, color="8FB8EE")
        text(s, MARGIN, Inches(3.0), Inches(11.5), Inches(1.6),
             f"Readiness and business case for {self.client}", size=40, bold=True, color=WHITE)
        text(s, MARGIN, Inches(5.2), Inches(11), Inches(0.4), who, size=16, color="C9D6EA")
        notes(s, f"Welcome. Today we cover where {self.client} stands on Copilot readiness, "
                 "the recommended approach and the business case. Use the agenda to jump to any section.")

    def agenda(self):
        s = self.blank()
        text(s, MARGIN, Inches(0.45), Inches(10), Inches(0.7), "Agenda", size=30, bold=True, color=NAVY)
        text(s, MARGIN, Inches(1.12), Inches(10), Inches(0.4), "Select a section to jump to it", size=14, color=MUTED)
        self.agenda_slide = s
        notes(s, "Each agenda item is a link. In slideshow mode, click one to jump there; "
                 "every slide has an Agenda button to come back.")

    def finish_agenda(self):
        s = self.agenda_slide
        n = len(self.sections)
        cols = 2 if n > 4 else 1
        per_col = -(-n // cols)
        col_w = (W - 2 * MARGIN - Inches(0.4) * (cols - 1)) / cols
        row_h = Inches(0.9)
        for i, (title, target) in enumerate(self.sections):
            c, r = divmod(i, per_col)
            x = MARGIN + c * (col_w + Inches(0.4))
            y = Inches(1.9) + r * (row_h + Inches(0.2))
            card = box(s, int(x), int(y), int(col_w), int(row_h), fill=CARD)
            card.click_action.target_slide = target
            badge(s, int(x + Inches(0.25)), int(y + Inches(0.2)), Inches(0.5), str(i + 1), BLUE)
            t = text(s, int(x + Inches(0.95)), int(y), int(col_w - Inches(1.1)), int(row_h), title,
                     size=18, bold=True, color=NAVY, anchor=MSO_ANCHOR.MIDDLE)
            t.click_action.target_slide = target
        for b in self.back_buttons:
            b.click_action.target_slide = s

    def readiness(self, r: dict):
        s = self.content_slide("Readiness: where you stand today",
                               f"{r['status']} · {sum(c['passed'] for c in r['criteria'])} of 5 criteria in place",
                               section="Readiness assessment")
        # Score gauge (native doughnut chart)
        box(s, MARGIN, Inches(1.75), Inches(4.2), Inches(4.9))
        cd = CategoryChartData()
        cd.categories = ["Score", "Remaining"]
        cd.add_series("Readiness", (r["score"], 100 - r["score"]))
        gf = s.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT, MARGIN + Inches(0.45), Inches(1.95),
                                Inches(3.3), Inches(3.3), cd)
        ch = gf.chart
        style_chart(ch)
        plot = ch.plots[0]
        hole = plot._element.find(qn("c:holeSize"))
        if hole is None:
            hole = plot._element.makeelement(qn("c:holeSize"), {})
            plot._element.append(hole)
        hole.set("val", "72")
        pts = plot.series[0].points
        for i, colour in enumerate((BLUE, "DDE3EC")):
            pts[i].format.fill.solid()
            pts[i].format.fill.fore_color.rgb = rgb(colour)
        text(s, MARGIN + Inches(0.45), Inches(3.05), Inches(3.3), Inches(1.1),
             [(str(r["score"]), 44, True, NAVY), ("out of 100", 12, False, MUTED)], align=PP_ALIGN.CENTER)
        pill = box(s, MARGIN + Inches(0.9), Inches(5.45), Inches(2.4), Inches(0.5), fill=BLUE, radius=0.5)
        p = pill.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = r["status"]
        run.font.size, run.font.bold, run.font.name, run.font.color.rgb = Pt(14), True, FONT, rgb(WHITE)
        text(s, MARGIN + Inches(0.3), Inches(6.05), Inches(3.6), Inches(0.5),
             "Weighted score: data governance and SharePoint permissions count most.", size=11, color=MUTED,
             align=PP_ALIGN.CENTER)

        # Criteria checklist
        x0 = MARGIN + Inches(4.6)
        wlist = W - MARGIN - x0
        for i, c in enumerate(r["criteria"]):
            y = Inches(1.75) + i * Inches(0.78)
            box(s, x0, y, wlist, Inches(0.64), fill=CARD if c["passed"] else "FDF1EA",
                line=None if c["passed"] else "F2B79B")
            badge(s, x0 + Inches(0.15), y + Inches(0.12), Inches(0.4), "✓" if c["passed"] else "!",
                  GREEN if c["passed"] else AMBER, size=14)
            text(s, x0 + Inches(0.7), y, wlist - Inches(2.2), Inches(0.64), c["label"], size=15, bold=True,
                 color=INK, anchor=MSO_ANCHOR.MIDDLE)
            text(s, x0 + wlist - Inches(1.5), y, Inches(1.35), Inches(0.64),
                 "In place" if c["passed"] else f"Gap · {c['weight']} pts", size=12, bold=True,
                 color=GREEN if c["passed"] else AMBER, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
        # Why it matters
        why_y = Inches(1.75) + 5 * Inches(0.78) + Inches(0.1)
        box(s, x0, why_y, wlist, Inches(0.9), fill=NAVY)
        data_gaps = [g for g in r["gaps"] if g["key"] in ("data_governance_in_place", "sharepoint_permissions_reviewed")]
        why = ("Copilot shows people anything they can already access. Unreviewed permissions without labels "
               "or DLP are the most common cause of oversharing in the first weeks of a rollout."
               if data_gaps else
               "The data foundations are in place, so the focus moves to adoption: sponsorship, training and champions.")
        text(s, x0 + Inches(0.3), why_y, wlist - Inches(0.6), Inches(0.9),
             [("Why this matters", 14, True, WHITE), (why, 12, False, "D6E2F3")], anchor=MSO_ANCHOR.MIDDLE)
        notes(s, f"Readiness score {r['score']}/100: {r['status']}. "
                 + ("Gaps: " + "; ".join(g["label"] for g in r["gaps"]) + ". " if r["gaps"] else "No gaps. ")
                 + "Scoring weights: licences 20, data governance 25, SharePoint permissions 25, sponsor 15, change plan 15.")

    def roadmap(self, r: dict):
        s = self.content_slide("Recommended path", "Start where it's safe, close the gaps, then scale",
                               section="Recommended path")
        cw = (W - 2 * MARGIN - Inches(0.4)) / 2
        go, hold = (("Scale the rollout", "Foundations are in place: expand in waves with adoption support.")
                    if r["score"] >= 80 else
                    ("Scoped pilot, 20-50 users", "Teams with well-understood content, so value is proven while the gaps close.")
                    if r["score"] >= 50 else
                    ("Close the foundations", "Fix the gaps below before putting Copilot in front of users."),
                    ("Tenant-wide rollout", "Hold until the gaps are closed and readiness is re-scored.")
                    if r["gaps"] else ("Nothing on hold", "All readiness criteria are in place."))
        for i, ((head, body), label, colour) in enumerate(((go, "GO NOW", BLUE), (hold, "HOLD", AMBER))):
            x = MARGIN + i * (cw + Inches(0.4))
            box(s, int(x), Inches(1.75), int(cw), Inches(1.45), fill=CARD)
            text(s, int(x + Inches(0.3)), Inches(1.9), int(cw - Inches(0.6)), Inches(1.2),
                 [(label, 11, True, colour), (head, 20, True, NAVY), (body, 13, False, MUTED)])
        steps = [(g["action"], g["detail"]) for g in r["gaps"]]
        steps.append(("Re-score readiness", "Re-run the assessment once the gaps are closed, then plan the wider rollout."))
        text(s, MARGIN, Inches(3.45), Inches(8), Inches(0.4), "Quick wins", size=18, bold=True, color=NAVY)
        per_row = 3 if len(steps) > 2 else len(steps)
        sw = (W - 2 * MARGIN - Inches(0.3) * (per_row - 1)) / per_row
        rows = -(-len(steps) // per_row)
        sh = Inches(1.45) if rows > 1 else Inches(2.0)
        for i, (head, body) in enumerate(steps):
            rr, cc = divmod(i, per_row)
            x = MARGIN + cc * (sw + Inches(0.3))
            y = Inches(3.95) + rr * (sh + Inches(0.2))
            box(s, int(x), int(y), int(sw), int(sh), fill=CARD)
            badge(s, int(x + Inches(0.2)), int(y + Inches(0.2)), Inches(0.45), str(i + 1), NAVY, size=14)
            text(s, int(x + Inches(0.8)), int(y + Inches(0.18)), int(sw - Inches(1.0)), int(sh - Inches(0.3)),
                 [(head, 15, True, INK), (body, 12, False, MUTED)])
        notes(s, "Recommended sequence: " + "; ".join(f"{i + 1}. {h}" for i, (h, _) in enumerate(steps)))

    def tier_and_use_cases(self, t: dict | None, industry: str | None, function: str | None):
        s = self.content_slide("Recommended approach",
                               "Build tier and first agent ideas" if t and function else
                               ("Recommended build tier" if t else "First agent ideas"),
                               section="Approach and use cases")
        left_w = Inches(5.4)
        if t:
            box(s, MARGIN, Inches(1.75), left_w, Inches(4.9), fill=NAVY)
            text(s, MARGIN + Inches(0.4), Inches(2.0), left_w - Inches(0.8), Inches(4.5),
                 [(t["tier"].upper(), 13, True, "8FB8EE"), (t["name"], 26, True, WHITE),
                  (f"{t['approach']} · {t['duration']} Build-Along", 14, False, "C9D6EA"),
                  ("Why", 13, True, "8FB8EE"), (t["reason"][0].upper() + t["reason"][1:] + ".", 15, False, WHITE),
                  ("Who builds it", 13, True, "8FB8EE"), (t["audience"], 15, False, WHITE)]
                 + ([("Note", 13, True, "FFC9A8"), (t["note"], 13, False, WHITE)] if t["note"] else []))
        if function:
            x0 = MARGIN + (left_w + Inches(0.4) if t else 0)
            wl = W - MARGIN - x0
            title = f"Agent ideas for {function}" + (f" in {industry}" if industry else "")
            text(s, x0, Inches(1.75), wl, Inches(0.45), title, size=18, bold=True, color=NAVY)
            for i, idea in enumerate(USE_CASES[function]):
                y = Inches(2.35) + i * Inches(1.0)
                box(s, x0, y, wl, Inches(0.82), fill=CARD)
                badge(s, x0 + Inches(0.2), y + Inches(0.16), Inches(0.5), str(i + 1), BLUE)
                text(s, x0 + Inches(0.9), y, wl - Inches(1.1), Inches(0.82), idea, size=16, bold=True,
                     color=INK, anchor=MSO_ANCHOR.MIDDLE)
            if industry:
                y = Inches(2.35) + 3 * Inches(1.0) + Inches(0.1)
                text(s, x0, y, wl, Inches(0.9), [("Industry tip", 13, True, BLUE),
                                                 (INDUSTRY_NOTES[industry], 14, False, INK)])
        notes(s, (f"Recommended {t['tier']} ({t['name']}) because {t['reason']}. " if t else "")
              + (f"Use cases for {function}: " + "; ".join(USE_CASES[function]) + "." if function else ""))

    def business_case(self, r: RoiResult):
        cur = self.currency
        s = self.content_slide("The business case",
                               "Year one, using Microsoft's Copilot assisted hours method", section="Business case")
        payback = ("Not reached" if r.payback_months is None else
                   "< 1 month" if r.payback_months < 1 else f"{r.payback_months:.1f} months")
        stats = [(money(r.net_benefit, cur), "Year-one net benefit", GREEN if r.net_benefit >= 0 else AMBER),
                 (f"{r.roi_pct:,.0f}%", "Year-one ROI", NAVY),
                 (payback, "Payback", NAVY),
                 (f"{r.assisted_hours:,.0f}", "Assisted hours a year", NAVY)]
        sw = (W - 2 * MARGIN - Inches(0.3) * 3) / 4
        for i, (v, label, colour) in enumerate(stats):
            x = MARGIN + i * (sw + Inches(0.3))
            box(s, int(x), Inches(1.75), int(sw), Inches(1.4), fill=CARD)
            text(s, int(x + Inches(0.25)), Inches(1.9), int(sw - Inches(0.5)), Inches(1.2),
                 [(v, 28, True, colour), (label, 13, False, MUTED)])
        # Native bar chart: potential -> realised vs cost
        cd = CategoryChartData()
        cats = ["Total cost", "Realised value", "Assisted value", "Full potential"]
        vals = [r.total_cost, r.realised_value, r.assisted_value, r.potential_value]
        cd.categories = cats
        cd.add_series("Year one", vals)
        gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, MARGIN, Inches(3.4), Inches(7.6), Inches(3.4), cd)
        ch = gf.chart
        style_chart(ch)
        quiet_axes(ch, value_visible=False)
        plot = ch.plots[0]
        plot.gap_width = 55
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.number_format, dl.number_format_is_linked = money_format(cur, max(vals)), False
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
        dl.font.size, dl.font.bold, dl.font.color.rgb = Pt(12), True, rgb(INK)
        for i, colour in enumerate((ORANGE, BLUE, GREY_BAR, GREY_BAR)):
            pt = plot.series[0].points[i]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = rgb(colour)
        ch.category_axis.tick_labels.font.size = Pt(13)
        # Assumptions card
        x0 = MARGIN + Inches(7.9)
        wl = W - MARGIN - x0
        box(s, x0, Inches(3.4), wl, Inches(3.4), fill=CARD)
        sym = CURRENCIES[cur]
        lines = [("Key assumptions", 14, True, NAVY),
                 (f"{r.users:,} licensed users, {r.adoption_rate:.0%} active", 12, False, INK),
                 (f"{r.assisted_hours_per_user_per_week:.1f} assisted hours per active user per week", 12, False, INK),
                 (f"{sym}{r.hourly_cost:,.2f} per hour · {sym}{r.licence_cost_per_user_per_month:,.2f} licence per month", 12, False, INK),
                 (f"One-off rollout costs {money(r.one_off_costs, cur)}", 12, False, INK),
                 (f"3-year ROI {r.roi_3yr_pct:,.0f}% · Forrester SMB projection {BENCHMARK['low']}-{BENCHMARK['high']}%", 12, True, BLUE)]
        if r.realisation_rate < 1:
            lines.insert(5, (f"{r.realisation_rate:.0%} of assisted time counted as realised value", 12, False, INK))
        text(s, x0 + Inches(0.25), Inches(3.55), wl - Inches(0.5), Inches(3.1), lines)
        notes(s, f"Assisted value {money(r.assisted_value, cur)} a year from {r.assisted_hours:,.0f} assisted hours. "
                 f"Total year-one cost {money(r.total_cost, cur)}. Net benefit {money(r.net_benefit, cur)}. "
                 "Select the chart and choose Edit Data to change the numbers.")

    def value_over_time(self, r: RoiResult):
        cur = self.currency
        s = self.content_slide("Value over time", "Cumulative value against cost, and where the time comes from",
                               section="Value over time")
        months = list(range(0, 37, 3))
        cd = CategoryChartData()
        cd.categories = ["Start" if m == 0 else f"M{m}" for m in months]
        cd.add_series("Realised value", [r.realised_value / 12 * m for m in months])
        cd.add_series("Cost", [r.one_off_costs + r.licence_cost / 12 * m for m in months])
        gf = s.shapes.add_chart(XL_CHART_TYPE.LINE, MARGIN, Inches(1.75), Inches(7.6), Inches(5.0), cd)
        ch = gf.chart
        style_chart(ch, legend=True)
        quiet_axes(ch)
        ch.value_axis.tick_labels.number_format = money_format(cur, r.realised_value * 3)
        ch.value_axis.tick_labels.number_format_is_linked = False
        for ser, colour in zip(ch.plots[0].series, (BLUE, ORANGE)):
            ser.format.line.color.rgb = rgb(colour)
            ser.format.line.width = Pt(2.5)
            ser.smooth = False
            ser.marker.style = XL_MARKER_STYLE.NONE
        # Hours by capability (native doughnut)
        x0 = MARGIN + Inches(7.9)
        wl = W - MARGIN - x0
        box(s, x0, Inches(1.75), wl, Inches(5.0), fill=CARD)
        text(s, x0 + Inches(0.25), Inches(1.9), wl - Inches(0.5), Inches(0.4),
             "Assisted hours by capability", size=14, bold=True, color=NAVY)
        cd2 = CategoryChartData()
        cats = ["Meeting summaries", "Search and summaries", "Creation"]
        cd2.categories = cats
        cd2.add_series("Hours a year", (round(r.hours_meetings), round(r.hours_search), round(r.hours_creation)))
        gf2 = s.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT, x0 + Inches(0.2), Inches(2.35), wl - Inches(0.4),
                                 Inches(2.9), cd2)
        ch2 = gf2.chart
        style_chart(ch2)
        plot = ch2.plots[0]
        plot.has_data_labels = True
        plot.data_labels.show_percentage, plot.data_labels.show_value = True, False
        plot.data_labels.number_format, plot.data_labels.number_format_is_linked = "0%", False
        plot.data_labels.font.size, plot.data_labels.font.bold = Pt(12), True
        plot.data_labels.font.color.rgb = rgb(WHITE)
        for i, colour in enumerate((BLUE, ORANGE, "1BAF7A")):
            pt = plot.series[0].points[i]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = rgb(colour)
        legend = [(f"■  {c}: {v:,.0f} h", 12, False, INK) for c, v in
                  zip(cats, (r.hours_meetings, r.hours_search, r.hours_creation))]
        box_legend = text(s, x0 + Inches(0.3), Inches(5.3), wl - Inches(0.6), Inches(1.3), legend)
        for para, colour in zip(box_legend.text_frame.paragraphs, (BLUE, ORANGE, "1BAF7A")):
            para.runs[0].font.color.rgb = rgb(colour)
            r2 = para.add_run()
            r2.text = ""
        # recolour: square in series colour, label in ink
        for para, (c, v) in zip(box_legend.text_frame.paragraphs,
                                zip(cats, (r.hours_meetings, r.hours_search, r.hours_creation))):
            run = para.runs[0]
            run.text = "■  "
            para.runs[1].text = f"{c}: {v:,.0f} h"
            para.runs[1].font.size, para.runs[1].font.name = Pt(12), FONT
            para.runs[1].font.color.rgb = rgb(INK)
        pay = ("Costs are covered " + ("in under a month" if (r.payback_months or 0) < 1 else
                                        f"after about {r.payback_months:.1f} months")
               if r.payback_months is not None else "Monthly value doesn't yet cover licence cost")
        notes(s, f"{pay}. Assisted hours follow Microsoft's method: meeting hours summarised, plus "
                 f"{MINUTES_PER_ACTION} minutes per search/summary action and per creation action.")

    def usage(self, u: dict):
        rows = u["rows"]
        weeks = u["weeks"][-12:]
        by_week = []
        for w in weeks:
            rs = [r for r in rows if r["w"] == w]
            act = sum(r.get("act", 0) for r in rs)
            lic = sum(r.get("lic", 0) for r in rs)
            hrs = sum(r.get("meet", 0) + (r.get("search", 0) + r.get("create", 0)) * MINUTES_PER_ACTION / 60 for r in rs)
            by_week.append((w, act, lic, hrs))
        last = by_week[-1]
        s = self.content_slide("Copilot usage today",
                               f"From the Copilot Dashboard export · last {len(weeks)} weeks",
                               section="Usage and adoption")
        stats = [(f"{last[1]:,.0f} / {last[2]:,.0f}", "Active of licensed users (latest week)"),
                 (f"{(last[1] / last[2] if last[2] else 0):.0%}", "Adoption rate"),
                 (f"{sum(b[3] for b in by_week):,.0f}", f"Assisted hours, {len(weeks)} weeks")]
        sw = (Inches(4.3))
        for i, (v, label) in enumerate(stats):
            y = Inches(1.75) + i * Inches(1.6)
            box(s, MARGIN, y, sw, Inches(1.4), fill=CARD)
            text(s, MARGIN + Inches(0.25), y + Inches(0.15), sw - Inches(0.5), Inches(1.2),
                 [(v, 30, True, NAVY), (label, 13, False, MUTED)])
        cd = CategoryChartData()
        from datetime import date as _d
        cd.categories = [_d.fromisoformat(b[0]).strftime("%d %b") for b in by_week]
        cd.add_series("Active users", [b[1] for b in by_week])
        x0 = MARGIN + sw + Inches(0.4)
        gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, x0, Inches(1.75), W - MARGIN - x0,
                                Inches(2.5), cd)
        ch = gf.chart
        style_chart(ch, size=11)
        quiet_axes(ch)
        ch.has_title = True
        ch.chart_title.text_frame.text = "Active Copilot users per week"
        ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(13)
        ch.chart_title.text_frame.paragraphs[0].runs[0].font.bold = True
        ch.plots[0].gap_width = 60
        ser = ch.plots[0].series[0]
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = rgb(BLUE)
        apps = {}
        for r in rows:
            if r["w"] in weeks:
                for k, v in r.items():
                    if k.startswith("app_"):
                        apps[k[4:]] = apps.get(k[4:], 0) + v
        top = sorted(((k, v) for k, v in apps.items() if v > 0), key=lambda kv: kv[1])[-6:]
        if top:
            cd2 = CategoryChartData()
            cd2.categories = [k for k, _ in top]
            cd2.add_series("Copilot actions", [v for _, v in top])
            gf2 = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, x0, Inches(4.45), W - MARGIN - x0,
                                     Inches(2.35), cd2)
            ch2 = gf2.chart
            style_chart(ch2, size=11)
            quiet_axes(ch2, value_visible=False)
            ch2.has_title = True
            ch2.chart_title.text_frame.text = f"Copilot actions by app, last {len(weeks)} weeks"
            ch2.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(13)
            ch2.chart_title.text_frame.paragraphs[0].runs[0].font.bold = True
            p2 = ch2.plots[0]
            p2.gap_width = 50
            p2.has_data_labels = True
            p2.data_labels.number_format, p2.data_labels.number_format_is_linked = "#,##0", False
            p2.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
            p2.data_labels.font.size = Pt(11)
            p2.series[0].format.fill.solid()
            p2.series[0].format.fill.fore_color.rgb = rgb(BLUE)
        notes(s, f"Source: {u['source']}. Latest week: {last[1]:,.0f} active of {last[2]:,.0f} licensed users.")

        # Adoption by organisation (table)
        latest = u["weeks"][-1]
        groups = {}
        for r in rows:
            if r["w"] == latest:
                g = groups.setdefault(r["org"], [0, 0])
                g[0] += r.get("lic", 0)
                g[1] += r.get("act", 0)
        if len(groups) > 1:
            s2 = self.content_slide("Adoption by organisation", f"Week of {date.fromisoformat(latest):%d %B %Y}",
                                    section="Adoption by organisation")
            items = sorted(groups.items(), key=lambda kv: -(kv[1][1] / kv[1][0] if kv[1][0] else 0))[:10]
            tbl = s2.shapes.add_table(len(items) + 1, 4, MARGIN, Inches(1.75), Inches(7.4),
                                      Inches(0.45) * (len(items) + 1)).table
            for j, (hname, width) in enumerate((("Organisation", 3.4), ("Licensed", 1.3), ("Active", 1.3), ("Adoption", 1.4))):
                tbl.columns[j].width = Inches(width)
                cell = tbl.cell(0, j)
                cell.text = hname
                cell.fill.solid()
                cell.fill.fore_color.rgb = rgb(NAVY)
                run = cell.text_frame.paragraphs[0].runs[0]
                run.font.size, run.font.bold, run.font.name, run.font.color.rgb = Pt(13), True, FONT, rgb(WHITE)
            for i, (org, (lic, act)) in enumerate(items, start=1):
                vals = (org, f"{lic:,.0f}", f"{act:,.0f}", f"{(act / lic if lic else 0):.0%}")
                for j, v in enumerate(vals):
                    cell = tbl.cell(i, j)
                    cell.text = v
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = rgb(CARD if i % 2 else WHITE)
                    para = cell.text_frame.paragraphs[0]
                    para.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT
                    run = para.runs[0]
                    run.font.size, run.font.name, run.font.color.rgb = Pt(13), FONT, rgb(INK)
            cd3 = CategoryChartData()
            cd3.categories = [k for k, _ in reversed(items)]
            cd3.add_series("Adoption", [(v[1] / v[0] if v[0] else 0) for _, v in reversed(items)])
            x0 = MARGIN + Inches(7.8)
            gf3 = s2.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, x0, Inches(1.75), W - MARGIN - x0,
                                      Inches(4.9), cd3)
            ch3 = gf3.chart
            style_chart(ch3, size=11)
            quiet_axes(ch3, value_visible=False)
            ch3.value_axis.maximum_scale, ch3.value_axis.minimum_scale = 1.0, 0
            p3 = ch3.plots[0]
            p3.gap_width = 50
            p3.has_data_labels = True
            p3.data_labels.number_format, p3.data_labels.number_format_is_linked = "0%", False
            p3.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
            p3.data_labels.font.size = Pt(11)
            p3.series[0].format.fill.solid()
            p3.series[0].format.fill.fore_color.rgb = rgb(BLUE)
            notes(s2, "Share of licensed users with any Copilot activity in the latest week, by organisation. "
                      "Target the lowest groups with champions and role-based training.")

    def build_along(self, tier: str, industry: str, function: str):
        info = TIERS[tier]
        s = self.content_slide("Hands-on: Agent Build-Along",
                               f"{info['name']} · {info['approach']} · {info['duration']}",
                               section="Build-Along plan")
        scenario = USE_CASES[function][0]
        box(s, MARGIN, Inches(1.75), W - 2 * MARGIN, Inches(1.0), fill=NAVY)
        text(s, MARGIN + Inches(0.35), Inches(1.75), W - 2 * MARGIN - Inches(0.7), Inches(1.0),
             [("SCENARIO", 11, True, "8FB8EE"), (f"{scenario} for {function} in {industry}", 20, True, WHITE)],
             anchor=MSO_ANCHOR.MIDDLE)
        steps = info["flow"]
        sw = (W - 2 * MARGIN - Inches(0.3) * (len(steps) - 1)) / len(steps)
        for i, step in enumerate(steps):
            x = MARGIN + i * (sw + Inches(0.3))
            shp = box(s, int(x), Inches(3.05), int(sw), Inches(1.1),
                      shape=MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON, fill=BLUE if i % 2 == 0 else "1C5CAB")
            p = shp.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            run = p.add_run()
            run.text = f"{i + 1}. {step}"
            run.font.size, run.font.bold, run.font.name, run.font.color.rgb = Pt(18), True, FONT, rgb(WHITE)
        box(s, MARGIN, Inches(4.45), W - 2 * MARGIN, Inches(2.25), fill=CARD)
        text(s, MARGIN + Inches(0.35), Inches(4.6), Inches(5.5), Inches(2.0),
             [("Prerequisites", 15, True, NAVY)] + [(f"•  {p}", 13, False, INK) for p in info["prerequisites"]])
        text(s, MARGIN + Inches(6.4), Inches(4.6), W - 2 * MARGIN - Inches(6.8), Inches(2.0),
             [("Facilitator tip", 15, True, NAVY), (INDUSTRY_NOTES[industry], 13, False, INK),
              ("Audience", 15, True, NAVY), (info["audience"], 13, False, INK)])
        notes(s, f"Session flow: {' > '.join(steps)}. Build the '{scenario}' scenario together.")

    def closing(self):
        s = self.blank()
        self.dark(s)
        text(s, MARGIN, Inches(0.8), Inches(10), Inches(0.8), "Next steps", size=36, bold=True, color=WHITE)
        steps = [("Agree the pilot group", "Pick 20-50 users in teams with well-understood content."),
                 ("Close the priority gaps", "Start the governance quick wins in parallel with the pilot."),
                 ("Measure and re-score", "Track Copilot Dashboard usage and re-run readiness and ROI in 6-8 weeks.")]
        for i, (h_, b_) in enumerate(steps):
            y = Inches(2.0) + i * Inches(1.35)
            badge(s, MARGIN, y, Inches(0.7), str(i + 1), BLUE, size=20)
            text(s, MARGIN + Inches(1.0), y - Inches(0.05), Inches(10), Inches(1.1),
                 [(h_, 22, True, WHITE), (b_, 15, False, "C9D6EA")])
        if self.partner_img:
            self.logo_plate(s, self.partner_img, W - MARGIN - Inches(1.9), H - Inches(2.3), Inches(1.9), Inches(1.45))
        who = " · ".join(x for x in (self.partner_name, self.prepared_by) if x)
        if who:
            text(s, MARGIN, H - Inches(1.0), Inches(9), Inches(0.4), who, size=14, color="C9D6EA")
        notes(s, "Close by agreeing the pilot group, owners for each gap and a date to re-score.")
        self.sections.append(("Next steps", s))

    def sources(self, has_roi: bool, has_usage: bool):
        s = self.content_slide("Method and sources", "How the numbers in this deck were calculated")
        items = []
        if has_roi:
            items += [("Copilot assisted hours",
                       "Meeting hours summarised or recapped + 6 minutes per search/summary action + 6 minutes per "
                       "creation action (Microsoft Copilot Dashboard method).",
                       "https://learn.microsoft.com/viva/insights/org-team-insights/copilot-dashboard#impact"),
                      ("Business case",
                       "Assisted value = assisted hours x hourly rate. Costs = licences for all licensed users + "
                       "one-off rollout costs. ROI = (value - cost) / cost. 46 working weeks a year.", None),
                      ("Benchmark",
                       f"Forrester projected Total Economic Impact of Microsoft 365 Copilot for SMB (commissioned "
                       f"by Microsoft): 3-year ROI {BENCHMARK['low']}-{BENCHMARK['high']}%.",
                       "https://www.microsoft.com/en-us/microsoft-365/blog/2024/10/17/microsoft-365-copilot-drove-up-to-353-roi-for-small-and-medium-businesses-new-study/")]
        if has_usage:
            items.append(("Usage data", "Copilot Dashboard (Viva Insights) data export, weekly, anonymised.",
                          "https://learn.microsoft.com/viva/insights/org-team-insights/export-copilot-metrics"))
        items.append(("Readiness score", "Licences 20, data governance 25, SharePoint permissions 25, "
                                         "executive sponsor 15, change plan 15 points.", None))
        if self.currency == "SGD":
            items.append(("Currency", f"Singapore dollars; 1 USD = {self.fx} SGD.", None))
        y = Inches(1.6)
        for head, body, url in items:
            box_ = text(s, MARGIN, y, W - 2 * MARGIN, Inches(0.8), [(head, 13, True, NAVY), (body, 11, False, INK)])
            if url:
                p = box_.text_frame.add_paragraph()
                r = p.add_run()
                r.text = url
                r.font.size, r.font.name, r.font.color.rgb = Pt(10), FONT, rgb(BLUE)
                r.hyperlink.address = url
            y += Inches(0.86)
        notes(s, "Estimates are directional. Validate activity assumptions with Copilot Dashboard data or a pilot.")

    def save(self, path: Path):
        self.finish_agenda()
        self.prs.save(str(path))


def build_deck(path: Path, client_name: str, currency: str = "USD", sgd_per_usd: float = 1.28,
               client_logo: str | None = None, partner_name: str | None = None,
               partner_logo: str | None = None, prepared_by: str | None = None,
               readiness: dict | None = None, tier: dict | None = None,
               industry: str | None = None, function: str | None = None,
               roi: RoiResult | None = None, usage: dict | None = None,
               template: str | None = None) -> dict:
    """Build the deck and return {"slides": [...section titles], "warnings": [...]}.

    template: optional path to a widescreen .pptx/.potx. Its masters, layouts and theme colours are used.
    """
    template_prs, template_note = load_template(template)
    with _style_lock:
        global NAVY, BLUE
        saved = NAVY, BLUE
        if template_prs is not None:
            theme = _theme_colours(template_prs)
            NAVY = theme.get("dk2", NAVY)
            BLUE = theme.get("accent1", BLUE)
        try:
            return _build(path, client_name, currency, sgd_per_usd, client_logo, partner_name, partner_logo,
                          prepared_by, readiness, tier, industry, function, roi, usage, template_prs, template_note)
        finally:
            NAVY, BLUE = saved


def _build(path, client_name, currency, sgd_per_usd, client_logo, partner_name, partner_logo, prepared_by,
           readiness, tier, industry, function, roi, usage, template_prs, template_note):
    d = Deck(client_name, currency, partner_name, partner_logo, client_logo, prepared_by, sgd_per_usd,
             template_prs)
    if template_note:
        d.warnings.insert(0, template_note)
    d.title()
    d.agenda()
    if readiness:
        d.readiness(readiness)
        d.roadmap(readiness)
    if tier or function:
        d.tier_and_use_cases(tier, industry, function)
    if roi:
        d.business_case(roi)
        d.value_over_time(roi)
    if usage:
        d.usage(usage)
    if tier and industry and function:
        d.build_along(tier["tier"], industry, function)
    d.closing()
    d.sources(has_roi=roi is not None, has_usage=usage is not None)
    d.save(path)
    return {"slides": [t for t, _ in d.sections], "count": len(d.prs.slides), "warnings": d.warnings}
