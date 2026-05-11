from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

# Logoning manzilini belgilang
LOGO_PATH = "path_to_logo.png"  # Buni logoning to‘g‘ri manzili bilan almashtiring


def generate_student_pdf(students, request):
    """
    Student CRUD get() metodidan chaqiriladi.

    Parametrlar:
        students: Filtrlangan queryset (prefetch_related ishlatilgan bo‘lishi kerak)
        request: DRF Request obyekti (user, query_params)

    Natija:
        HttpResponse — Content-Type: application/pdf
    """
    # Stil va layout sozlamalari
    styles = get_styles()  # Sizda mavjud bo‘lgan `get_styles()` metodi bilan stilni sozlash

    # PDF fayli uchun nomni sozlash
    filename = f"students_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    buffer = io.BytesIO()

    # Oddiy hujjat shablonini yaratish
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=50,
        bottomMargin=50
    )

    # PDF uchun hikoya (content)
    story = []

    # Logoni hujjatga qo‘shish (yuqori chap burchak)
    story.append(Spacer(1, 20))  # Joylashuvni sozlash uchun bo‘shliq
    story.append(Paragraph("<img src='{}' width=200 height=50 />".format(LOGO_PATH), styles['title']))

    # Institut nomi
    story.append(Paragraph("Buxoro Davlat Tibbiyot Instituti", styles['title']))

    # Joriy sana va foydalanuvchi ma'lumotlari
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}", styles['meta_l']))
    user = request.user
    story.append(Paragraph(f"Export qildi: {user.first_name} {user.last_name}", styles['meta_r']))

    # Filtr parametrlarini qo‘shish (agar mavjud bo‘lsa)
    filter_text = get_filter_text(request.query_params)
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Filtrlar: {filter_text}", styles['filter']))

    # Jadval yaratish (talabalar ro‘yxati)
    table_data = [["№", "F.I.SH.", "Guruh", "GPA", "Telefon"]]
    for idx, student in enumerate(students):
        table_data.append([
            idx + 1,  # Raqam
            f"{student.last_name} {student.first_name} {student.third_name}",  # F.I.SH.
            student.group.name if student.group else "",  # Guruh
            student.avg_gpa if student.avg_gpa is not None else "",  # GPA
            student.phone or ""  # Telefon
        ])

    table = Table(table_data, colWidths=[40, 100, 60, 40, 50])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(table)

    # Hujjatni qurish va javobni qaytarish
    doc.build(story)

    # PDF faylini javob sifatida qaytarish
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response