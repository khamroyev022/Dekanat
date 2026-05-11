def calculate_student_completion(obj):
    from .models import (
        StudentDetail, HealthInfo, FamilySocialStatus,
        Dormitory, LanguageInfo, Achievement, Reprimand,
        FamilyMember, Interest, SocialRegistry, Gifted,
        ProtectionOrder, SocialLink
    )

    sid = obj.id

    def exists_only(model, **kwargs):
        """
        Record bor → True
        Record yo'q → None  (belgilanmagan)
        """
        return True if model.objects.filter(student_id=sid, **kwargs).exists() else None

    def exists_with_status(model):
        """
        Record yo'q         → None  (belgilanmagan)
        Record bor, True    → True  (bor)
        Record bor, False   → False (belgilangan, lekin yo'q)
        """
        record = model.objects.filter(student_id=sid).first()
        if record is None:
            return None
        return bool(record.status)

    sections = {
        # Status maydoni yo'q — bor/yo'q
        "asosiy_malumot"    : exists_only(StudentDetail),
        "soglik"            : exists_only(HealthInfo),
        "oilaviy_holat"     : exists_only(FamilySocialStatus),
        "turar_joy"         : exists_only(Dormitory),
        "til_bilimi"        : exists_only(LanguageInfo),
        "yutuqlar"          : exists_only(Achievement),
        "hayfnoma"          : exists_only(Reprimand),
        "oila_azolari"      : exists_only(FamilyMember),
        "qiziqishlar"       : exists_only(Interest),
        "ijtimoiy_havolalar": exists_only(SocialLink),

        "ijtimoiy_reyestr"  : exists_with_status(SocialRegistry),
        "iqtidorli"         : exists_with_status(Gifted),
        "himoya_orderi"     : exists_with_status(ProtectionOrder),
    }

    filled  = sum(1 for v in sections.values() if v is not None)
    total   = len(sections)
    percent = round(filled / total * 100) if total > 0 else 0

    return {
        "percent" : percent,
        "filled"  : filled,
        "total"   : total,
        "sections": sections,
    }

def calculate_sections(student) -> dict:
    def pct(f, t):
        return round((f / t) * 100, 1) if t else 0.0

    detail = student.details.first()

    basic = ['first_name', 'last_name', 'birthday', 'gender', 'country', 'phone', 'email']
    bf = sum(1 for x in basic if getattr(student, x, None))
    bf += 1 if (student.image or student.image_hemis) else 0
    bt  = len(basic) + 1 + 2
    if detail:
        bf += 1 if detail.pnfl else 0
        bf += 1 if detail.passport_pdf else 0

    # 2. Sog'liq
    h = getattr(student, 'health_info', None)
    hf = (1 + (1 if h.health_status is not None else 0) + (1 if h.file else 0)) if h else 0

    # 3. Oilaviy holat
    fss = getattr(student, 'family_social_status', None)
    ff  = (1 + (1 if fss.marital_status else 0) +
               (1 if fss.is_orphan else 0) +
               (1 if fss.official_employment else 0)) if fss else 0

    # 4. Turar joy
    dorm = getattr(student, 'dormitory', None)
    df   = 0
    if dorm:
        df = 1
        if dorm.status:
            df += sum([1 if dorm.dormitory_name else 0,
                       1 if dorm.building else 0,
                       1 if dorm.room else 0])
        else:
            df += sum([1 if dorm.residence_type else 0,
                       1 if dorm.address else 0, 1])

    # 5. Til bilimi
    langs = list(student.language_info.all())
    lf = sum([(1 if l.name else 0) + (1 if l.level else 0) + (1 if l.file else 0) for l in langs])

    # 6. Yutuqlar
    ach = list(student.achievements.all())
    af  = sum([(1 if a.name else 0) + (1 if a.date else 0) + (1 if a.file else 0) for a in ach])

    # 7. Hayfnoma
    reps = list(student.reprimands.all())
    rf   = sum([(1 if r.date else 0) + (1 if r.title else 0) + (1 if r.file else 0) for r in reps])

    members = list(student.family_members.all())
    mf = sum([(1 if m.first_name else 0) + (1 if m.last_name else 0) +
              (1 if m.address else 0) + (1 if m.work_place else 0) for m in members])

    interests_ok = student.interests.exists()

    regs = list(student.social_registries.all())
    regf = sum([1 + (1 if r.file else 0) for r in regs])

    gifts = list(student.gifteds.all())
    gf    = sum([(1 if g.name else 0) + (1 if g.file else 0) for g in gifts])

    orders = list(student.protection_orders.all())
    of_    = sum([1 + (1 if o.file else 0) for o in orders])

    links = list(student.social_links.all())
    slf   = sum([(1 if sl.name else 0) + (1 if sl.urls else 0) for sl in links])

    return {
        'asosiy_malumot'    : pct(bf,   bt),
        'soglik'            : pct(hf,   3),
        'oilaviy_holat'     : pct(ff,   4),
        'turar_joy'         : pct(df,   4),
        'til_bilimi'        : pct(lf,   max(len(langs), 1) * 3),
        'yutuqlar'          : pct(af,   max(len(ach),   1) * 3),
        'hayfnoma'          : pct(rf,   max(len(reps),  1) * 3),
        'oila_azolari'      : pct(mf,   max(len(members), 1) * 4),
        'qiziqishlar'       : 100.0 if interests_ok else 0.0,
        'ijtimoiy_reyestr'  : pct(regf, max(len(regs),  1) * 2),
        'iqtidorli'         : pct(gf,   max(len(gifts), 1) * 2),
        'himoya_orderi'     : pct(of_,  max(len(orders),1) * 2),
        'ijtimoiy_havolalar': pct(slf,  max(len(links), 1) * 2),
    }