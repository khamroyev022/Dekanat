import os
from datetime import datetime
from decimal import Decimal
import requests
from django.core.files.base import ContentFile
from django.db import transaction
from .models import Faculty, Direction, Group, Student, StudentDetail


class HEMISStudentImportService:

    def __init__(self, base_url, headers=None, timeout=20, save_images=False):
        self.base_url = base_url
        self.headers = headers or {}
        self.timeout = timeout
        self.save_images = save_images

    def fetch_page(self, page=1):

        response = requests.get(
            self.base_url,
            headers=self.headers,
            params={"page": page},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def run(self, start_page=1, max_pages=None):

        page = start_page
        created_count = 0
        updated_count = 0

        while True:
            if max_pages and page > max_pages:
                break

            data = self.fetch_page(page=page)

            if not data.get("success"):
                print(f"API xatolik qaytardi. page={page}, error={data.get('error')}")
                break

            items = data.get("data", {}).get("items", [])
            if not items:
                print(f"Page {page} da item yo'q. Import tugadi.")
                break

            print(f"Page {page}: {len(items)} ta student topildi")

            for item in items:
                created, updated = self.save_student(item)
                if created:
                    created_count += 1
                elif updated:
                    updated_count += 1

            page += 1

        return {
            "created": created_count,
            "updated": updated_count,
            "last_page": page - 1
        }

    @transaction.atomic
    def save_student(self, item):

        university = item.get("university") or {}
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

        faculty_name = department.get("name", "").strip() or "Noma'lum fakultet"
        faculty_code = department.get("code", "").strip() or "unknown"

        direction_name = specialty.get("name", "").strip() or "Noma'lum yo'nalish"
        direction_code = specialty.get("code", "").strip() or f"dir-{specialty.get('id', '0')}"

        group_name = group_data.get("name", "").strip() or f"group-{item.get('id')}"
        education_language = education_lang.get("name", "").strip() or "Noma'lum"
        education_code = education_lang.get("code", "").strip() or "unknown"

        first_name = (item.get("first_name") or "").strip()
        last_name = (item.get("second_name") or "").strip()
        third_name = (item.get("third_name") or "").strip()

        gender = self._map_gender(gender_data.get("name"))
        birthday = self._parse_unix_date(item.get("birth_date"))
        avg_gpa = self._parse_decimal(item.get("avg_gpa"))
        course = level_data.get("name", "").strip() or "Noma'lum"


        hemis_id = str(item.get("student_id_number") or item.get("id") or "")

        email = (item.get("email") or "").strip() or None

        faculty, _ = Faculty.objects.get_or_create(
            code=faculty_code,
            defaults={
                "name": faculty_name,
            }
        )

        if faculty.name != faculty_name:
            faculty.name = faculty_name
            faculty.save(update_fields=["name"])

        direction, _ = Direction.objects.get_or_create(
            code=direction_code,
            defaults={
                "name": direction_name,
                "faculty": faculty,
            }
        )

        changed = False
        if direction.name != direction_name:
            direction.name = direction_name
            changed = True
        if direction.faculty_id != faculty.id:
            direction.faculty = faculty
            changed = True
        if changed:
            direction.save()

        group_obj, _ = Group.objects.get_or_create(
            name=group_name,
            defaults={
                "education_code": education_code,
                "education_language": education_language,
                "direction": direction,
            }
        )

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

        student_defaults = {
            "first_name": first_name,
            "last_name": last_name,
            "third_name": third_name,
            "birthday": birthday,
            "gender": gender,
            "country": country_data.get("name"),
            "avg_gpa": avg_gpa,
            "course": course,
            "email": email,
            "group": group_obj,
        }

        student, created = Student.objects.update_or_create(
            hemis_id=hemis_id,
            defaults=student_defaults
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

        return created, not created

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
        image_full_url = item.get("image_full")

        if image_url and not student.image_none:
            content = self._download_file(image_url)
            if content:
                filename = self._build_filename(student.hemis_id, image_url)
                student.image_none.save(filename, content, save=False)

        if image_full_url and not student.image_full_none:
            content = self._download_file(image_full_url)
            if content:
                filename = self._build_filename(f"{student.hemis_id}_full", image_full_url)
                student.image_full_none.save(filename, content, save=False)

        if student.image_none or student.image_full_none:
            student.save()

    def _download_file(self, url):
        try:
            response = requests.get(url, timeout=self.timeout)
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