

import io
from datetime import datetime
from reportlab.pdfgen.canvas import Canvas

from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

import os, sys

if sys.platform == "win32":
    _FONT_REG  = "C:/Windows/Fonts/arial.ttf"
    _FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"
else:
    _FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    _FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

pdfmetrics.registerFont(TTFont("DejaVu",     _FONT_REG))
pdfmetrics.registerFont(TTFont("DejaVuBold", _FONT_BOLD))

# ── Mapping lug'atlar ─────────────────────────────────────────────────────────
INSTITUTE_NAME = "Buxoro davlat tibbiyot instituti"

GENDER_MAP     = {"erkak": "Erkak", "ayol": "Ayol", "boshqa": "Boshqa"}
EDUCATION_MAP  = {"grant": "Grant", "kontrakt": "Kontrakt", "nomalum": "Nomalum"}
MARITAL_MAP    = {
    "single": "Bo'ydoq", "married": "Turmush qurgan",
    "divorced": "Ajrashgan", "widowed": "Beva",
}
ORPHAN_MAP     = {"none": "Yo'q", "orphan": "Yetim", "full_orphan": "Chin yetim"}
DISABILITY_MAP = {"1": "1-guruh", "2": "2-guruh", "3": "3-guruh"}
RESIDENCE_MAP  = {
    "own_house": "O'z uyida", "relative": "Qarindoshinikida", "rented": "Ijarada",
}
FILTER_LABELS  = {
    "search": "Qidiruv", "gender": "Jinsi", "course": "Kurs",
    "country": "Mamlakat", "group": "Guruh", "direction": "Yo'nalish",
    "faculty": "Fakultet", "gpa_min": "GPA (min)", "gpa_max": "GPA (max)",
    "education_type": "Ta'lim turi", "is_orphanage_student": "Bolalar uyi",
    "is_military_family": "Harbiy oila", "is_pregnant": "Homilador",
    "behavior_issues": "Xulq muammosi", "is_adult": "Voyaga yetgan",
    "disability": "Nogironlik", "health_status": "Sog'liq",
    "disability_status": "Nogironlik guruhi", "has_dormitory": "Yotoqxona",
    "residence_type": "Turar joy", "marital_status": "Oilaviy holat",
    "is_orphan": "Yetimlik", "is_crime_prone": "Jinoyatga moyil",
    "language_level": "Til darajasi", "language_status": "Til sertifikati",
    "has_achievement": "Yutuqlar", "has_reprimand": "Tanbehlar",
    "reprimand_status": "Tanbeh holati", "social_registry_status": "Ijtimoiy ro'yxat",
    "is_gifted": "Istedodli", "has_protection_order": "Homiylik buyrug'i",
}


# ── Ma'lumot yordamchilari ────────────────────────────────────────────────────
def _detail(s, field, mapping=None):
    try:
        val = getattr(s.details.all()[0], field, "") or ""
        return mapping.get(val, val) if mapping else ("Ha" if val else "Yo'q")
    except (IndexError, AttributeError):
        return ""

def _family(s, field, mapping=None):
    try:
        val = getattr(s.family_social_status, field, "") or ""
        return mapping.get(val, val) if mapping else ("Ha" if val else "Yo'q")
    except Exception:
        return ""

def _health(s, field, mapping=None):
    try:
        val = getattr(s.health_info, field, "")
        if mapping:
            return mapping.get(val or "", val or "")
        return "Ha" if val else "Yo'q"
    except Exception:
        return ""

def _dormitory(s):
    try:
        d = s.dormitory
        if d.status:
            parts = filter(None, [
                d.dormitory_name, d.building,
                f"{d.floor}-qavat" if d.floor else None,
                f"{d.room}-xona"   if d.room  else None,
            ])
            return "Yotoqxona: " + ", ".join(parts)
        label = RESIDENCE_MAP.get(d.residence_type, "")
        return f"{label} | {d.address}" if d.address else label
    except Exception:
        return ""

def _gifted(s):
    try:
        return "Ha" if any(g.status for g in s.gifteds.all()) else "Yo'q"
    except Exception:
        return ""

def _social_reg(s):
    try:
        return "Faol" if any(r.status for r in s.social_registries.all()) else "Nofaol"
    except Exception:
        return ""


# ── Ustunlar (nom, kenglik, qiymat_funksiya) ──────────────────────────────────
SHORT_COLS = [
    ("№",        6*mm, lambda i, s: str(i)),
    ("Hemis ID", 22*mm, lambda i, s: s.hemis_id or ""),
    ("F.I.SH.",  46*mm, lambda i, s: f"{s.last_name} {s.first_name} {s.third_name}".strip()),
    ("Kurs",     10*mm, lambda i, s: s.course or ""),
    ("Jinsi",    14*mm, lambda i, s: GENDER_MAP.get(s.gender, s.gender)),
    ("Guruh",    28*mm, lambda i, s: s.group.name if s.group_id else ""),
    ("GPA",      12*mm, lambda i, s: str(s.avg_gpa) if s.avg_gpa is not None else ""),
    ("Telefon",  24*mm, lambda i, s: s.phone or ""),
]

FULL_COLS = SHORT_COLS + [
    ("Ta'lim turi",      18*mm, lambda i, s: _detail(s, "education_type", EDUCATION_MAP)),
    ("Yotoqxona/Manzil", 42*mm, lambda i, s: _dormitory(s)),
    ("Oilaviy holat",    22*mm, lambda i, s: _family(s, "marital_status", MARITAL_MAP)),
    ("Yetimlik",         18*mm, lambda i, s: _family(s, "is_orphan",      ORPHAN_MAP)),
    ("Nogironlik",       18*mm, lambda i, s: _health(s, "disability")),
    ("Nog. guruhi",      16*mm, lambda i, s: _health(s, "disability_status", DISABILITY_MAP)),
    ("Homilador",        16*mm, lambda i, s: _detail(s, "is_pregnant")),
    ("Harbiy oila",      16*mm, lambda i, s: _detail(s, "is_military_family")),
    ("Xulq",             14*mm, lambda i, s: _detail(s, "behavior_issues")),
    ("Istedodli",        16*mm, lambda i, s: _gifted(s)),
    ("Ij. ro'yxat",      18*mm, lambda i, s: _social_reg(s)),
]


# ── Sahifa raqami canvas ──────────────────────────────────────────────────────
class _NumberedCanvas(Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for i, snap in enumerate(self._saved_pages):
            self.__dict__.update(snap)
            w, _ = self._pagesize
            self.setFont("DejaVu", 7)
            self.setFillColor(colors.grey)
            self.drawCentredString(w / 2, 7 * mm, f"{i + 1} / {total}")
            Canvas.showPage(self)
        Canvas.save(self)
# ── Stillar ───────────────────────────────────────────────────────────────────
def _styles():
    return {
        "title":  ParagraphStyle("t",  fontName="DejaVuBold", fontSize=13,
                      alignment=TA_CENTER, spaceAfter=3,
                      textColor=colors.HexColor("#1a237e")),
        "sub":    ParagraphStyle("s",  fontName="DejaVu", fontSize=8,
                      alignment=TA_CENTER, spaceAfter=2,
                      textColor=colors.HexColor("#37474f")),
        "meta_l": ParagraphStyle("ml", fontName="DejaVu", fontSize=7,
                      alignment=TA_LEFT,  textColor=colors.HexColor("#546e7a")),
        "meta_r": ParagraphStyle("mr", fontName="DejaVu", fontSize=7,
                      alignment=TA_RIGHT, textColor=colors.HexColor("#546e7a")),
        "filter": ParagraphStyle("f",  fontName="DejaVu", fontSize=7,
                      textColor=colors.HexColor("#01579b"), spaceAfter=4),
        "count":  ParagraphStyle("c",  fontName="DejaVuBold", fontSize=8,
                      textColor=colors.HexColor("#1a237e"), spaceAfter=5),
        "cell":   ParagraphStyle("cl", fontName="DejaVu",     fontSize=7, leading=9),
        "cell_b": ParagraphStyle("cb", fontName="DejaVuBold", fontSize=7, leading=9),
    }


# ── Asosiy funksiya ───────────────────────────────────────────────────────────
def generate_student_pdf(students, request):
    """
    StudentCRUD.get() dan to'g'ridan-to'g'ri chaqiriladi.

    Params:
        students  — filterlangan queryset (prefetch_related allaqachon bo'lishi kerak)
        request   — DRF Request ob'ekti (user, query_params)

    Returns:
        HttpResponse — Content-Type: application/pdf
    """
    mode      = request.query_params.get("mode", "short").lower()
    cols      = FULL_COLS if mode == "full" else SHORT_COLS
    page_size = landscape(A4) if mode == "full" else A4
    students  = list(students)          # queryset bir marta bajariladi
    st        = _styles()
    margin    = 14 * mm
    buf       = io.BytesIO()

    doc = SimpleDocTemplate(
        buf, pagesize=page_size,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=18 * mm,
    )
    story = _build_story(students, cols, mode, page_size, margin, st, request)
    doc.build(story, canvasmaker=_NumberedCanvas)

    filename = f"students_{mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def _build_story(students, cols, mode, page_size, margin, st, request):
    story = []
    user  = request.user

    # ─ Sarlavha ─
    story.append(Paragraph(INSTITUTE_NAME, st["title"]))
    story.append(Spacer(1, 1 * mm))
    story.append(Paragraph(
        f"Studentlar ro'yxati — {'To\'liq' if mode == 'full' else 'Qisqa'} hisobot",
        st["sub"],
    ))
    story.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor("#1a237e"), spaceAfter=3))

    # ─ Meta (sana / kim eksport qildi) ─
    user_full    = " ".join(filter(None, [
        user.last_name, user.first_name, getattr(user, "third_name", "")
    ])) or user.username
    role_display = getattr(user.role, "name", "") if user.role else ""

    meta = Table([[
        Paragraph(f"Sana: {datetime.now().strftime('%d.%m.%Y  %H:%M')}", st["meta_l"]),
        Paragraph(f"Eksport qildi: {user_full}  ({role_display})", st["meta_r"]),
    ]], colWidths=["50%", "50%"])
    meta.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
    story.append(meta)
    story.append(Spacer(1, 1 * mm))

    # ─ Filtr va son ─
    story.append(Paragraph(f"Filtrlar: {_filter_text(request.query_params)}", st["filter"]))
    story.append(Paragraph(f"Jami: {len(students)} ta student", st["count"]))

    # ─ Jadval ─
    page_w    = page_size[0] - 2 * margin
    col_w     = [c[1] for c in cols]
    surplus   = page_w - sum(col_w)
    if surplus > 0:
        # Ortiq bo'shliqni F.I.SH. ustuniga berish
        idx = next((i for i, c in enumerate(cols) if c[0] == "F.I.SH."), None)
        if idx is not None:
            col_w[idx] += surplus

    header = [Paragraph(c[0], st["cell_b"]) for c in cols]
    rows   = [header] + [
        [Paragraph(c[2](idx + 1, s), st["cell"]) for c in cols]
        for idx, s in enumerate(students)
    ]

    tbl = Table(rows, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  colors.HexColor("#1a237e")),
        ("TEXTCOLOR",      (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",       (0, 0), (-1, 0),  "DejaVuBold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#e8eaf6")]),
        ("GRID",           (0, 0), (-1, -1), 0.3, colors.HexColor("#b0bec5")),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",     (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 2),
        ("LEFTPADDING",    (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 3),
    ]))
    story.append(tbl)
    return story


def _filter_text(params):
    skip  = {"export", "mode", "page", "page_size"}
    parts = [
        f"{FILTER_LABELS.get(k, k)}: {v}"
        for k, v in params.items()
        if k not in skip and v
    ]
    return " | ".join(parts) if parts else "Filtrlar yo'q"