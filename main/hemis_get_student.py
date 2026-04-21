#
#
# import requests
# from datetime import date
#
# from django.db import transaction
#
# from .models import (   # <── o'z app nomingizga qarab to'g'rilang
#     Student, StudentDetail,
#     Faculty, Direction, Group,
# )
#
# EDUCATION_TYPE_BAKALAVR = "11"
# CITIZENSHIP_FOREIGN     = "12"
#
# GENDER_MAP = {
#     "11": "erkak",
#     "12": "ayol",
# }
#
# PAYMENT_MAP = {
#     "11": "grant",
#     "12": "kontrakt",
# }
#
#
# class HEMISStudentImportService:
#
#     def __init__(
#         self,
#         base_url: str,
#         headers: dict,
#         timeout: int = 20,
#         save_images: bool = False,
#     ):
#         self.base_url    = base_url.rstrip("/")
#         self.timeout     = timeout
#         self.save_images = save_images
#
#         self.session = requests.Session()
#         self.session.headers.update(headers)
#         self.session.headers.update({"Accept": "application/json"})
#
#
#
#     def run(self, start_page: int = 1, max_pages: int = 583) -> dict:
#         """
#         Barcha sahifalarni aylanib chiqib talabalarni saqlaydi.
#
#         Qaytaradi:
#             {
#                 "created":   <int>,
#                 "updated":   <int>,
#                 "last_page": <int>,
#             }
#         """
#         created   = 0
#         updated   = 0
#         last_page = start_page
#
#         for page in range(start_page, max_pages + 1):
#             items, real_page_count = self._fetch_page(page)
#
#             if items is None:
#                 # API xatosi — bu sahifani o'tkazib, davom et
#                 continue
#
#             for item in items:
#                 # Faqat Bakalavr
#                 edu_code = (item.get("educationType") or {}).get("code", "")
#                 if edu_code != EDUCATION_TYPE_BAKALAVR:
#                     continue
#
#                 result = self._save_student(item)
#                 if result == "created":
#                     created += 1
#                 elif result == "updated":
#                     updated += 1
#
#             last_page = page
#
#             # Agar real sahifalar soni max_pages dan kam bo'lsa — to'xtat
#             if real_page_count and page >= real_page_count:
#                 break
#
#         return {
#             "created":   created,
#             "updated":   updated,
#             "last_page": last_page,
#         }
#
#     # ──────────────────────────────────────────────────
#     #  PRIVATE: API so'rov
#     # ──────────────────────────────────────────────────
#
#     def _fetch_page(self, page: int):
#         """
#         Bir sahifa ma'lumotini API dan oladi.
#
#         Qaytaradi: (items_list, total_page_count)
#         Xatolikda:  (None, None)
#         """
#         params = {"page": page, "limit": 20}
#         try:
#             resp = self.session.get(self.base_url, params=params, timeout=self.timeout)
#             resp.raise_for_status()
#             body = resp.json()
#         except Exception:
#             return None, None
#
#         if not body.get("success"):
#             return None, None
#
#         pagination  = (body.get("data") or {}).get("pagination", {})
#         page_count  = pagination.get("pageCount")
#         items       = (body.get("data") or {}).get("items", [])
#         return items, page_count
#
#     # ──────────────────────────────────────────────────
#     #  PRIVATE: bazaga saqlash
#     # ──────────────────────────────────────────────────
#
#     @transaction.atomic
#     def _save_student(self, item: dict) -> str:
#         hemis_id = (item.get("student_id_number") or "").strip()
#         if not hemis_id:
#             return "skip"
#
#         # Bog'liq jadvallar
#         faculty   = self._get_or_create_faculty(item)
#         direction = self._get_or_create_direction(item, faculty)
#         group     = self._get_or_create_group(item, direction)
#
#         # Tug'ilgan sana (unix timestamp → date)
#         birthday = None
#         bd_ts = item.get("birth_date")
#         if bd_ts:
#             try:
#                 birthday = date.fromtimestamp(int(bd_ts))
#             except Exception:
#                 pass
#
#         gender  = GENDER_MAP.get((item.get("gender") or {}).get("code", ""), "boshqa")
#         country = (item.get("country") or {}).get("name", "")
#         course  = (item.get("level")   or {}).get("name", "")
#         avg_gpa = item.get("avg_gpa") or None
#         image_hemis = item.get("image_full") or item.get("image") or ""
#         email   = (item.get("email") or "").strip()
#
#         student, is_created = Student.objects.update_or_create(
#             hemis_id=hemis_id,
#             defaults=dict(
#                 first_name  = (item.get("first_name")  or "").strip(),
#                 last_name   = (item.get("second_name") or "").strip(),
#                 third_name  = (item.get("third_name")  or "").strip(),
#                 birthday    = birthday,
#                 gender      = gender,
#                 country     = country,
#                 image_hemis = image_hemis,
#                 avg_gpa     = avg_gpa,
#                 course      = course,
#                 email       = email,
#                 group       = group,
#             ),
#         )
#
#         # StudentDetail — yashash manzili
#         self._save_detail(student, item)
#
#         return "created" if is_created else "updated"
#
#     def _save_detail(self, student: Student, item: dict):
#         pay_code = (item.get("paymentForm") or {}).get("code", "")
#
#         StudentDetail.objects.update_or_create(
#             student=student,
#             defaults=dict(
#                 # Doimiy (ro'yxatdagi) manzil
#                 p_country  = (item.get("country")   or {}).get("name", ""),
#                 p_region   = (item.get("province")  or {}).get("name", ""),
#                 p_district = (item.get("district")  or {}).get("name", ""),
#                 # Hozirgi (faktik) manzil
#                 t_country  = (item.get("country")          or {}).get("name", ""),
#                 t_region   = (item.get("currentProvince")  or {}).get("name", ""),
#                 t_district = (item.get("currentDistrict")  or {}).get("name", ""),
#                 # To'lov turi
#                 education_type = PAYMENT_MAP.get(pay_code, "nomalum"),
#             ),
#         )
#
#     # ──────────────────────────────────────────────────
#     #  PRIVATE: Faculty / Direction / Group
#     # ──────────────────────────────────────────────────
#
#     def _get_or_create_faculty(self, item: dict) -> Faculty:
#         dept = item.get("department") or {}
#         name = (dept.get("name") or "Noma'lum fakultet")[:150]
#         code = (dept.get("code") or "")[:30]
#         faculty, _ = Faculty.objects.get_or_create(
#             name=name,
#             defaults={"code": code},
#         )
#         return faculty
#
#     def _get_or_create_direction(self, item: dict, faculty: Faculty) -> Direction:
#         spec = item.get("specialty") or {}
#         name = (spec.get("name") or "Noma'lum yo'nalish")[:150]
#         code = str(spec.get("code") or "")[:10]
#         direction, _ = Direction.objects.get_or_create(
#             name=name,
#             faculty=faculty,
#             defaults={"code": code},
#         )
#         return direction
#
#     def _get_or_create_group(self, item: dict, direction: Direction) -> Group:
#         grp  = item.get("group") or {}
#         name = (grp.get("name") or "Noma'lum guruh")[:250]
#         lang = (grp.get("educationLang") or {}).get("name", "")
#         edu_code = str(grp.get("id") or "")[:20]
#
#         # Xorijiy talabalar + mahalliy talabalar bir xil guruh nomi bo'lsa
#         # get_or_create avtomatik "bitta qiladi"
#         group, _ = Group.objects.get_or_create(
#             name=name,
#             defaults={
#                 "education_code":     edu_code,
#                 "education_language": lang,
#                 "direction":          direction,
#             },
#         )
#         return group




















import requests
from datetime import date

from django.db import transaction

from .models import (
    Student, StudentDetail,
    Faculty, Direction, Group,
)

EDUCATION_TYPE_BAKALAVR = "11"

GENDER_MAP = {
    "11": "erkak",
    "12": "ayol",
}

# ✅ 3 xil to'lov turi — API dan kelgan code ni tekshiring
PAYMENT_MAP = {
    "11": "grant",
    "12": "kontrakt",
    "13": "superkontrakt",  # ← API dan kelgan real codeni tekshiring
}


class HEMISStudentImportService:

    def __init__(
        self,
        base_url: str,
        headers: dict,
        timeout: int = 20,
        save_images: bool = False,
    ):
        self.base_url    = base_url.rstrip("/")
        self.timeout     = timeout
        self.save_images = save_images

        self.session = requests.Session()
        self.session.headers.update(headers)
        self.session.headers.update({"Accept": "application/json"})

    def run(self, start_page: int = 1, max_pages: int = 583) -> dict:
        created   = 0
        updated   = 0
        last_page = start_page

        for page in range(start_page, max_pages + 1):
            items, real_page_count = self._fetch_page(page)

            if items is None:
                continue

            for item in items:
                edu_code = (item.get("educationType") or {}).get("code", "")
                if edu_code != EDUCATION_TYPE_BAKALAVR:
                    continue

                result = self._save_student(item)
                if result == "created":
                    created += 1
                elif result == "updated":
                    updated += 1

            last_page = page

            if real_page_count and page >= real_page_count:
                break

        return {
            "created":   created,
            "updated":   updated,
            "last_page": last_page,
        }

    def _fetch_page(self, page: int):
        params = {"page": page, "limit": 20}
        try:
            resp = self.session.get(self.base_url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            body = resp.json()
        except Exception:
            return None, None

        if not body.get("success"):
            return None, None

        pagination = (body.get("data") or {}).get("pagination", {})
        page_count = pagination.get("pageCount")
        items      = (body.get("data") or {}).get("items", [])
        return items, page_count

    @transaction.atomic
    def _save_student(self, item: dict) -> str:
        hemis_id = (item.get("student_id_number") or "").strip()
        if not hemis_id:
            return "skip"

        faculty   = self._get_or_create_faculty(item)
        direction = self._get_or_create_direction(item, faculty)
        group     = self._get_or_create_group(item, direction)

        birthday = None
        bd_ts = item.get("birth_date")
        if bd_ts:
            try:
                birthday = date.fromtimestamp(int(bd_ts))
            except Exception:
                pass

        gender      = GENDER_MAP.get((item.get("gender") or {}).get("code", ""), "boshqa")
        country     = (item.get("country") or {}).get("name", "")
        course      = (item.get("level")   or {}).get("name", "")
        avg_gpa     = item.get("avg_gpa") or None
        image_hemis = item.get("image_full") or item.get("image") or ""
        email       = (item.get("email") or "").strip()

        student, is_created = Student.objects.update_or_create(
            hemis_id=hemis_id,
            defaults=dict(
                first_name  = (item.get("first_name")  or "").strip(),
                last_name   = (item.get("second_name") or "").strip(),
                third_name  = (item.get("third_name")  or "").strip(),
                birthday    = birthday,
                gender      = gender,
                country     = country,
                image_hemis = image_hemis,
                avg_gpa     = avg_gpa,
                course      = course,
                email       = email,
                group       = group,
            ),
        )

        self._save_detail(student, item)
        return "created" if is_created else "updated"

    def _save_detail(self, student: Student, item: dict):
        # ✅ API dan kelgan raw codeni log qilib tekshirish mumkin
        pay_form = item.get("paymentForm") or {}
        pay_code = pay_form.get("code", "")
        pay_name = pay_form.get("name", "")  # ← debug uchun

        # MAP da topilmasa — API dan kelgan nomni ishlatadi
        education_type = PAYMENT_MAP.get(pay_code, pay_name or "nomalum")

        StudentDetail.objects.update_or_create(
            student=student,
            defaults=dict(
                p_country      = (item.get("country")          or {}).get("name", ""),
                p_region       = (item.get("province")         or {}).get("name", ""),
                p_district     = (item.get("district")         or {}).get("name", ""),
                t_country      = (item.get("country")          or {}).get("name", ""),
                t_region       = (item.get("currentProvince")  or {}).get("name", ""),
                t_district     = (item.get("currentDistrict")  or {}).get("name", ""),
                education_type = education_type,  # ✅
            ),
        )

    # ✅ code bo'yicha lookup — takroriy yaratilmaydi
    def _get_or_create_faculty(self, item: dict) -> Faculty:
        dept = item.get("department") or {}
        name = (dept.get("name") or "Noma'lum fakultet")[:150]
        code = (dept.get("code") or "")[:30]

        faculty, _ = Faculty.objects.get_or_create(
            code=code,       # ← asosiy kalit
            defaults={"name": name},
        )
        return faculty

    # ✅ code bo'yicha lookup — takroriy yaratilmaydi
    def _get_or_create_direction(self, item: dict, faculty: Faculty) -> Direction:
        spec = item.get("specialty") or {}
        name = (spec.get("name") or "Noma'lum yo'nalish")[:150]
        code = str(spec.get("code") or "")[:10]

        direction, _ = Direction.objects.get_or_create(
            code=code,       # ← asosiy kalit
            faculty=faculty,
            defaults={"name": name},
        )
        return direction

    def _get_or_create_group(self, item: dict, direction: Direction) -> Group:
        grp      = item.get("group") or {}
        name     = (grp.get("name") or "Noma'lum guruh")[:250]
        lang     = (grp.get("educationLang") or {}).get("name", "")
        edu_code = str(grp.get("id") or "")[:20]

        group, _ = Group.objects.get_or_create(
            name=name,
            defaults={
                "education_code":     edu_code,
                "education_language": lang,
                "direction":          direction,
            },
        )
        return group