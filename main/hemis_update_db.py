

import os
import time
from datetime import datetime
from decimal import Decimal
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from django.core.files.base import ContentFile
from django.db import transaction
from .models import Faculty, Direction, Group, Student, StudentDetail


FOREIGN_FACULTY_KEYWORDS = [
    'xorijiy talabalar',
    'xalqaro talabalar',
    'xalqaro tibbiyot',
    "qo'shma ta'lim",
    'international',
]

MERGED_FACULTY_NAME = "Xalqaro tibbiyot fakulteti (Xorijiy talabalar)"
MERGED_FACULTY_CODE = "362-113"


class HEMISStudentUpdate:

    def __init__(self, base_url, headers=None, timeout=50, save_images=False, update_only=True):
        self.base_url = base_url
        self.headers = headers or {}
        self.timeout = timeout
        self.save_images = save_images
        self.update_only = update_only
        self.session = self._create_session()

    def _create_session(self):
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _normalize_faculty(self, faculty_name, faculty_code):
        """Xorijiy talabalar fakultetlarini bitta nom bilan birlashtiradi"""
        name_lower = faculty_name.lower()
        for keyword in FOREIGN_FACULTY_KEYWORDS:
            if keyword in name_lower:
                return MERGED_FACULTY_NAME, MERGED_FACULTY_CODE
        return faculty_name, faculty_code

    def fetch_page(self, page=1):
        try:
            response = self.session.get(
                self.base_url,
                headers=self.headers,
                params={"page": page},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectTimeout:
            print(f"Timeout xatosi: server javob bermadi (page={page})")
            return None
        except requests.exceptions.ConnectionError:
            print(f"Ulanish xatosi: internet yoki server muammosi (page={page})")
            return None
        except requests.exceptions.RequestException as e:
            print(f"So'rov xatosi (page={page}): {e}")
            return None

    def run(self, start_page=1, max_pages=None):
        page = start_page
        updated_count = 0
        skipped_count = 0
        failed_pages = []

        while True:
            if max_pages and page > max_pages:
                break

            data = self.fetch_page(page=page)

            if data is None:
                print(f"Page {page} o'tkazib yuborildi, 10 sekund kutilmoqda...")
                failed_pages.append(page)
                time.sleep(10)
                page += 1
                continue

            if not data.get("success"):
                print(f"API xatolik qaytardi. page={page}, error={data.get('error')}")
                break

            items = data.get("data", {}).get("items", [])
            if not items:
                print(f"Page {page} da item yo'q. Tugadi.")
                break

            print(f"Page {page}: {len(items)} ta student topildi")

            for item in items:
                updated, skipped = self.save_student(item)
                if updated:
                    updated_count += 1
                elif skipped:
                    skipped_count += 1

            page += 1
            time.sleep(1)

        print(f"Yakunlandi: {updated_count} ta yangilandi, {skipped_count} ta topilmadi (o'tkazildi).")
        if failed_pages:
            print(f"Muvaffaqiyatsiz sahifalar: {failed_pages}")

        return {
            "updated": updated_count,
            "skipped": skipped_count,
            "last_page": page - 1,
            "failed_pages": failed_pages,
        }

    @transaction.atomic
    def save_student(self, item):
        department = item.get("department") or {}
        specialty = item.get("specialty") or {}
        group_data = item.get("group") or {}
        education_lang = group_data.get("educationLang") or {}
        gender_data = item.get("gender") or {}
        country_data = item.get("country") or {}
        province_data = item.get("province") or {}
        district_data = item.get("district") or {}
        current_province_data = item.get("currentProvince") or {}
        current_district_data = item.get("currentDistrict") or {}
        education_type_data = item.get("educationType") or {}
        level_data = item.get("level") or {}

        hemis_id = str(item.get("student_id_number") or item.get("id") or "")

        faculty_name = department.get("name", "").strip() or "Noma'lum fakultet"
        faculty_code = department.get("code", "").strip() or "unknown"
        faculty_name, faculty_code = self._normalize_faculty(faculty_name, faculty_code)

        direction_name = specialty.get("name", "").strip() or "Noma'lum yo'nalish"
        direction_code = specialty.get("code", "").strip() or f"dir-{specialty.get('id', '0')}"

        group_name = group_data.get("name", "").strip() or f"group-{item.get('id')}"
        education_language = education_lang.get("name", "").strip() or "Noma'lum"
        education_code = education_lang.get("code", "").strip() or "unknown"

        # ── Faculty ───────────────────────────────────────────────────────────────
        faculty, _ = Faculty.objects.get_or_create(
            code=faculty_code,
            defaults={"name": faculty_name}
        )
        if faculty.name != faculty_name:
            faculty.name = faculty_name
            faculty.save(update_fields=["name"])

        # ── Direction (TUZATILDI: filter().first() bilan) ─────────────────────────
        direction = Direction.objects.filter(code=direction_code).first()

        if direction is None:
            # Yangi direction yaratish
            direction = Direction.objects.create(
                code=direction_code,
                name=direction_name,
                faculty=faculty,
            )
        else:
            # Mavjudini yangilash
            direction_changed = False
            if direction.name != direction_name:
                direction.name = direction_name
                direction_changed = True
            if direction.faculty_id != faculty.id:
                direction.faculty = faculty
                direction_changed = True
            if direction_changed:
                direction.save()

            # ⚠️ Dublikatlarni tozalash (agar bir xil code li ko'p yozuv bo'lsa)
            Direction.objects.filter(code=direction_code).exclude(id=direction.id).delete()

        # ── Group ─────────────────────────────────────────────────────────────────
        group_obj = Group.objects.filter(name=group_name).first()

        if group_obj is None:
            group_obj = Group.objects.create(
                name=group_name,
                education_code=education_code,
                education_language=education_language,
                direction=direction,
            )
        else:
            group_changed = False
            if group_obj.education_code != education_code:
                group_obj.education_code = education_code
                group_changed = True
            if group_obj.education_language != education_language:
                group_obj.education_language = education_language
                group_changed = True
            if group_obj.direction_id != direction.id:
                group_obj.direction = direction
                group_changed = True
            if group_changed:
                group_obj.save()

        # ── Student ───────────────────────────────────────────────────────────────
        if self.update_only:
            try:
                student = Student.objects.get(hemis_id=hemis_id)
            except Student.DoesNotExist:
                print(f"Student topilmadi, o'tkazildi: hemis_id={hemis_id}")
                return False, True

            student.first_name = (item.get("first_name") or "").strip()
            student.last_name = (item.get("second_name") or "").strip()
            student.third_name = (item.get("third_name") or "").strip()
            student.birthday = self._parse_unix_date(item.get("birth_date"))
            student.gender = self._map_gender(gender_data.get("name"))
            student.country = country_data.get("name")
            student.avg_gpa = self._parse_decimal(item.get("avg_gpa"))
            student.course = level_data.get("name", "").strip() or "Noma'lum"
            student.group = group_obj
            student.image_hemis = item.get("image")
            student.save()
        else:
            student, _ = Student.objects.update_or_create(
                hemis_id=hemis_id,
                defaults={
                    "first_name": (item.get("first_name") or "").strip(),
                    "last_name": (item.get("second_name") or "").strip(),
                    "third_name": (item.get("third_name") or "").strip(),
                    "birthday": self._parse_unix_date(item.get("birth_date")),
                    "gender": self._map_gender(gender_data.get("name")),
                    "country": country_data.get("name"),
                    "avg_gpa": self._parse_decimal(item.get("avg_gpa")),
                    "course": level_data.get("name", "").strip() or "Noma'lum",
                    "group": group_obj,
                    "image_hemis": item.get("image"),
                }
            )

        if self.save_images:
            self._save_student_images(student, item)

        StudentDetail.objects.update_or_create(
            student=student,
            defaults={
                "p_country": country_data.get("name"),
                "p_region": province_data.get("name"),
                "p_district": district_data.get("name"),
                "t_country": country_data.get("name"),
                "t_region": current_province_data.get("name"),
                "t_district": current_district_data.get("name"),
                "education_type": self._map_education_type(education_type_data.get("name")),
            }
        )

        return True, False

    def _parse_unix_date(self, timestamp):
        if not timestamp:
            return None
        try:
            return datetime.fromtimestamp(int(timestamp)).date()
        except Exception:
            return None

    def _parse_decimal(self, value):
        if value in [None, ""]:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    def _map_gender(self, gender_name):
        if not gender_name:
            return "erkak"
        gender_name = gender_name.lower()
        if "erkak" in gender_name:
            return "erkak"
        if "ayol" in gender_name:
            return "ayol"
        return "erkak"

    def _map_education_type(self, education_type_name):
        if not education_type_name:
            return "nomalum"
        val = education_type_name.lower()
        if "bakalavr" in val:
            return "bakalavr"
        if "magistr" in val:
            return "magistr"
        return "nomalum"

    def _save_student_images(self, student, item):
        image_url = item.get("image")
        changed = False
        if image_url and not student.image:
            content = self._download_file(image_url)
            if content:
                filename = self._build_filename(student.hemis_id, image_url)
                student.image.save(filename, content, save=False)
                changed = True
        if changed:
            student.save()

    def _download_file(self, url):
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return ContentFile(response.content)
        except Exception as e:
            print(f"Rasm yuklashda xatolik: {url} -> {e}")
            return None

    def _build_filename(self, base_name, url):
        ext = os.path.splitext(url)[1]
        if not ext:
            ext = ".jpg"
        return f"{base_name}{ext}"


