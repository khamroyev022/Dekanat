from .export_pdf import *
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets, status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db.models import Count
from config.settings import HEMIS_TOKEN
from .hemis_update_db import HEMISStudentUpdate
from .hemis_get_student import HEMISStudentImportService
from .models import *
from .pagination import StudentPagination
from .serializers import *
from .persmission import *
from .filters import *
from audit.utils import log_action



ROLE_ADMIN_ID    = 1
ROLE_TUTOR_ID    = 2
ROLE_DEKAN_ID    = 3
ROLE_ZAM_DEKAN_ID = 4
STAFF_ROLE_IDS   = [2, 3, 4]

PREFETCH_FIELDS = [
    'achievements', 'health_info', 'language_info',
    'social_links', 'reprimands', 'family_social_status',
    'family_members', 'interests', 'social_registries',
    'dormitory', 'gifteds', 'protection_orders',
]



def ok(message, data, code=status.HTTP_200_OK):
    return Response({'success': True, 'message': message, 'data': data}, status=code)

def fail(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({'success': False, 'message': message, 'data': None}, status=code)

def get_student(student_id):
    try:
        return Student.objects.get(id=student_id), None
    except Student.DoesNotExist:
        return None, fail("Student topilmadi", status.HTTP_404_NOT_FOUND)

def faculty_students(user):
    return Student.objects.filter(group__direction__faculty=user.faculty)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return fail("username yoki password majburiy")

    user = authenticate(request, username=username, password=password)
    if user is None:
        log_action(request, action='LOGIN',
                   description=f"Muvaffaqiyatsiz login urinishi: '{username}'",
                   status_code=400)
        return fail("username yoki password noto'g'ri")

    refresh = RefreshToken.for_user(user)

    log_action(request, action='LOGIN', model_name='CustomUser', object_id=user.id,
               description=f"{user.username} tizimga kirdi", status_code=200)

    return Response({
        'success' : True,
        'message' : "Login muvaffaqiyatli",
        'data'    : LoginSerializer(user).data,
        'access'  : str(refresh.access_token),
        'username': user.username,
    })

class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh"))
            token.blacklist()

            log_action(request, action='LOGOUT', model_name='CustomUser',
                       description="Foydalanuvchi tizimdan chiqdi", status_code=200)
            return ok("Muvaffaqiyatli chiqildi", None)
        except Exception as e:
            return fail(str(e))

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_students(request):
    service = HEMISStudentImportService(
        base_url=request.data.get("base_url") or "https://student.bsmi.uz/rest/v1/data/student-list",
        headers={"Authorization": f"Bearer {request.data.get('token') or HEMIS_TOKEN}"},
        timeout=20, save_images=False,
    )
    result = service.run(
        start_page=request.data.get("start_page", 1),
        max_pages=request.data.get("max_pages", 584),
    )

    log_action(request, action='CREATE', model_name='Student',
               description=f"HEMIS import: {result}", status_code=200)

    return Response({"message": "Import muvaffaqiyatli yakunlandi", **result})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_students(request):
    service = HEMISStudentUpdate(
        base_url="https://student.bsmi.uz/rest/v1/data/student-list",
        headers={"Authorization": f"Bearer {HEMIS_TOKEN}"},
        timeout=20, save_images=False,
    )
    result = service.run(
        start_page=request.data.get("start_page", 1),
        max_pages=request.data.get("max_pages", 584),
    )

    log_action(request, action='UPDATE', model_name='Student',
               description=f"HEMIS yangilash: {result}", status_code=200)

    return Response({"message": "Yangilash muvaffaqiyatli yakunlandi", **result})

class CreateUserViewSet(viewsets.ModelViewSet):
    serializer_class   = CreateUserSerializer
    permission_classes = [UserCRUDPermission]

    def get_queryset(self):
        user      = self.request.user
        role_name = getattr(user.role, 'name', '').lower().strip()
        base_qs   = CustomUser.objects.prefetch_related('tutor_groups').select_related('role', 'faculty')

        if user.is_superuser or role_name == ROLE_ADMIN:
            return base_qs.all()
        if role_name == ROLE_DEKAN:
            return base_qs.filter(
                Q(id=user.id) |
                Q(faculty_id=user.faculty_id, role_id__in=[ROLE_TUTOR_ID, ROLE_ZAM_DEKAN_ID])
            )
        if role_name == ROLE_ZAM_DEKAN and user.faculty_id:
            return base_qs.filter(faculty_id=user.faculty_id, role__name__iexact='tutor')
        return CustomUser.objects.none()

    # ─── Yangi helper: fakultet cheklovlarini tekshiradi ───────────────────────
    def _check_faculty_constraints(self, faculty_id, new_role_id, exclude_user_id=None):
        """
        - Dekan:     bitta fakultetda faqat 1 ta bo'lishi mumkin
        - Zam dekan: bitta fakultetda maksimum 5 ta bo'lishi mumkin
        - Ikkalasi ham boshqa fakultetga o'tkazib bo'lmaydi
        """
        if not faculty_id:
            return None

        try:
            role_obj  = Role.objects.get(id=new_role_id)
            role_name = role_obj.name.lower().strip()
        except Role.DoesNotExist:
            return None

        # Faqat dekan / zam_dekan uchun tekshiruv
        if role_name not in (ROLE_DEKAN, ROLE_ZAM_DEKAN):
            return None

        qs = CustomUser.objects.filter(faculty_id=faculty_id, role_id=new_role_id)
        if exclude_user_id:
            qs = qs.exclude(id=exclude_user_id)

        if role_name == ROLE_DEKAN:
            if qs.exists():
                return Response(
                    {'success': False,
                     'message': "Bu fakultetda allaqachon dekan mavjud. "
                                "Bitta fakultetga faqat bitta dekan tayinlanishi mumkin."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        elif role_name == ROLE_ZAM_DEKAN:
            if qs.count() >= 5:
                return Response(
                    {'success': False,
                     'message': "Bu fakultetda allaqachon 5 ta zam dekan mavjud. "
                                "Bitta fakultetga ko'pi bilan 5 ta zam dekan tayinlanishi mumkin."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return None

    def _check_faculty_reassignment(self, user_obj, new_faculty_id, new_role_id):
        """
        Dekan yoki zam dekan allaqachon boshqa fakultetga biriktirilgan bo'lsa,
        uni yangi fakultetga o'tkazishga ruxsat bermaydi.
        """
        try:
            role_obj  = Role.objects.get(id=new_role_id)
            role_name = role_obj.name.lower().strip()
        except Role.DoesNotExist:
            return None

        if role_name not in (ROLE_DEKAN, ROLE_ZAM_DEKAN):
            return None

        current_faculty_id = user_obj.faculty_id
        if current_faculty_id and current_faculty_id != new_faculty_id:
            role_display = "Dekan" if role_name == ROLE_DEKAN else "Zam dekan"
            return Response(
                {'success': False,
                 'message': f"Bu {role_display} allaqachon boshqa fakultetga biriktirilgan. "
                            f"Avval uni joriy fakultetdan olib tashlang."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return None
    # ───────────────────────────────────────────────────────────────────────────

    def _check_role_permission(self, user, new_role_id, allowed_ids, err_msg):
        if new_role_id not in allowed_ids:
            return Response({'success': False, 'message': err_msg}, status=status.HTTP_403_FORBIDDEN)
        return None

    def create(self, request, *args, **kwargs):
        user      = request.user
        role_name = getattr(user.role, 'name', '').lower().strip()

        try:
            new_role_id = int(request.data.get('role'))
        except (TypeError, ValueError):
            return Response({'success': False, 'message': "Role kiritilmagan"}, status=400)

        if role_name == ROLE_DEKAN:
            err = self._check_role_permission(user, new_role_id, [ROLE_TUTOR_ID, ROLE_ZAM_DEKAN_ID],
                                              "Siz faqat tutor yoki zam dekan yarata olasiz")
            if err:
                return err

            # Zam dekan yaratilayotganda fakultet cheklovini tekshir
            faculty_id = user.faculty_id
            err = self._check_faculty_constraints(faculty_id, new_role_id)
            if err:
                return err

        elif role_name == ROLE_ZAM_DEKAN:
            err = self._check_role_permission(user, new_role_id, [ROLE_TUTOR_ID],
                                              "Siz faqat tutor yarata olasiz")
            if err:
                return err

        else:
            # Admin / superuser tomonidan yaratish
            faculty_id  = request.data.get('faculty')
            err = self._check_faculty_constraints(faculty_id, new_role_id)
            if err:
                return err

            result = super().create(request, *args, **kwargs)
            if result.status_code == 201:
                log_action(request, model_name='CustomUser',
                           description="Yangi foydalanuvchi yaratildi", status_code=201)
            return result

        data = request.data.copy()
        data['faculty'] = user.faculty_id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        new_user = serializer.instance
        log_action(request, model_name='CustomUser', object_id=new_user.id,
                   description=f"Yangi foydalanuvchi yaratildi: {new_user.username}",
                   status_code=201)

        return Response({'success': True, 'message': "Yaratildi", 'data': serializer.data},
                        status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial    = kwargs.pop('partial', False)
        obj        = self.get_object()

        # Yangilanayotgan role va fakultetni aniqlaymiz
        try:
            new_role_id = int(request.data.get('role', obj.role_id))
        except (TypeError, ValueError):
            new_role_id = obj.role_id

        try:
            new_faculty_id = int(request.data.get('faculty', obj.faculty_id))
        except (TypeError, ValueError):
            new_faculty_id = obj.faculty_id

        # 1) Boshqa fakultetga o'tkazishga urinayaptimi?
        err = self._check_faculty_reassignment(obj, new_faculty_id, new_role_id)
        if err:
            return err

        # 2) Fakultet cheklovlarini tekshir (o'zini exclude qilamiz)
        err = self._check_faculty_constraints(new_faculty_id, new_role_id, exclude_user_id=obj.id)
        if err:
            return err

        serializer = self.get_serializer(obj, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        log_action(request, model_name='CustomUser', object_id=obj.id,
                   description=f"Foydalanuvchi yangilandi: {obj.username}", status_code=200)

        return Response({'success': True, 'message': "Yangilandi", 'data': serializer.data})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        log_action(request, action='DELETE', model_name='CustomUser', object_id=obj.id,
                   description=f"Foydalanuvchi o'chirildi: {obj.username}", status_code=200)
        self.perform_destroy(obj)
        return Response({'success': True, 'message': "O'chirildi"})

    def list(self, request, *args, **kwargs):
        return Response({'success': True, 'data': self.get_serializer(self.get_queryset(), many=True).data})

    def retrieve(self, request, *args, **kwargs):
        return Response({'success': True, 'data': self.get_serializer(self.get_object()).data})

class FacultyGEtApipview(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role.id == ROLE_ADMIN_ID:
            qs, msg = Faculty.objects.all(), "Hamma fakultetlar ro'yxati"
        elif user.role.id in STAFF_ROLE_IDS:
            qs, msg = Faculty.objects.filter(dekans=user), "Sizning fakultetingiz"
        else:
            return fail("Xatolik yuz berdi")
        return ok(msg, Facultyserializer(qs, many=True).data)

class DirectionGETApiview(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user       = request.user
        faculty_id = request.query_params.get('faculty_id')

        if not faculty_id:
            return fail("faculty_id parametri kiritilmadi")
        try:
            faculty = Faculty.objects.get(id=faculty_id)
        except Faculty.DoesNotExist:
            return fail("Fakultet topilmadi", status.HTTP_404_NOT_FOUND)

        if user.role.id == ROLE_ADMIN_ID:
            qs = Direction.objects.filter(faculty=faculty)
        elif user.role.id in STAFF_ROLE_IDS:
            if not user.faculty:
                return fail("Sizga biriktirilgan fakultet yo'q", status.HTTP_404_NOT_FOUND)
            qs = Direction.objects.filter(faculty=user.faculty)
            faculty = user.faculty
        else:
            return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

        return ok("Yo'nalishlar", {
            'faculty'   : faculty.name,
            'directions': DirectionSerializer(qs, many=True).data,
        })

class GroupsGetApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user               = request.user
        search             = request.query_params.get('search')
        education_language = request.query_params.get('education_language')
        sort_reprimand     = request.query_params.get('sort_reprimand')
        direction_id       = request.query_params.get('direction_id')

        def apply_filters(qs):
            if search:
                qs = qs.filter(name__icontains=search)
            if education_language:
                qs = qs.filter(education_language__icontains=education_language)
            return qs

        if user.role.id == ROLE_ADMIN_ID:
            if not direction_id:
                return fail("direction_id parametri kiritilmadi")
            try:
                direction = Direction.objects.get(id=direction_id)
            except Direction.DoesNotExist:
                return fail("Yo'nalish topilmadi", status.HTTP_404_NOT_FOUND)
            qs  = apply_filters(Group.objects.filter(direction=direction))
            msg = "Guruhlar ro'yxati"

        elif user.role.id in [ROLE_DEKAN_ID, ROLE_ZAM_DEKAN_ID]:
            if not user.faculty:
                return fail("Sizga biriktirilgan fakultet yo'q", status.HTTP_404_NOT_FOUND)

            if direction_id:
                # direction_id berilsa — faqat shu yo'nalish guruhlari
                try:
                    direction = Direction.objects.get(id=direction_id, faculty=user.faculty)
                except Direction.DoesNotExist:
                    return fail("Yo'nalish topilmadi yoki sizning fakultetingizga tegishli emas",
                                status.HTTP_404_NOT_FOUND)
                qs  = apply_filters(Group.objects.filter(direction=direction))
                msg = f"{direction.name} yo'nalishi guruhlari"
            else:
                # direction_id berilmasa — butun fakultet guruhlari
                qs  = apply_filters(Group.objects.filter(direction__faculty=user.faculty))
                msg = "Sizning fakultetingiz guruhlari"

        elif user.role.id == ROLE_TUTOR_ID:
            qs  = apply_filters(Group.objects.filter(tutor=user))
            msg = "Sizga biriktirilgan guruhlar"

        else:
            return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

        qs  = qs.select_related('tutor')
        ser = GroupSerializer(
            qs, many=True,
            context={'request': request, 'sort_reprimand': sort_reprimand}
        )
        return ok(msg, ser.data)

class StudentCRUD(APIView):
    permission_classes = [IsAuthenticated]

    def _get_base_qs(self, user, group_id=None):
        if group_id:
            try:
                group = Group.objects.get(id=group_id)
            except Group.DoesNotExist:
                return None, fail("Guruh topilmadi", status.HTTP_404_NOT_FOUND)

            if user.role.id in STAFF_ROLE_IDS:
                if not user.faculty:
                    return None, fail("Sizga biriktirilgan fakultet yo'q", status.HTTP_404_NOT_FOUND)
                if group.direction.faculty != user.faculty:
                    return None, fail("Bu guruh sizning fakultetingizga tegishli emas", status.HTTP_403_FORBIDDEN)
            elif user.role.id != ROLE_ADMIN_ID:
                return None, fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

            return Student.objects.filter(group=group), None

        if user.role.id == ROLE_ADMIN_ID:
            return Student.objects.all(), None

        if user.role.id in STAFF_ROLE_IDS:
            if not user.faculty:
                return None, fail("Sizga biriktirilgan fakultet yo'q", status.HTTP_404_NOT_FOUND)
            return faculty_students(user), None

        return None, fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

    def get(self, request):
        user       = request.user
        student_id = request.query_params.get('student_id')
        group_id   = request.query_params.get('group_id')
        faculty_id = request.query_params.get('faculty_id')

        if student_id:
            try:
                student = Student.objects.prefetch_related(*PREFETCH_FIELDS).get(id=student_id)
            except Student.DoesNotExist:
                return fail("Student topilmadi", status.HTTP_404_NOT_FOUND)

            if user.role.id in STAFF_ROLE_IDS:
                if not user.faculty or student.group.direction.faculty != user.faculty:
                    return fail("Bu student sizning fakultetingizga tegishli emas", status.HTTP_403_FORBIDDEN)
            elif user.role.id != ROLE_ADMIN_ID:
                return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

            log_action(request, action='READ', model_name='Student', object_id=student_id,
                       description=f"Student ma'lumoti ko'rildi: {student.first_name} {student.last_name}",
                       status_code=200)

            return ok("Student ma'lumoti", StudentFullSerializer(student).data)

        if faculty_id:
            if user.role.id != ROLE_ADMIN_ID:
                return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)
            try:
                faculty = Faculty.objects.get(id=faculty_id)
            except Faculty.DoesNotExist:
                return fail("Fakultet topilmadi", status.HTTP_404_NOT_FOUND)
            students = Student.objects.filter(group__direction__faculty=faculty)
        else:
            students, err = self._get_base_qs(user, group_id)
            if err:
                return err

        students = students.annotate(
            reprimand_count=Count('reprimands')
        ).prefetch_related(*PREFETCH_FIELDS)

        f = StudentFilter(request.query_params, queryset=students)
        if not f.is_valid():
            return fail(f.errors)
        students = f.qs

        sort_reprimand = request.query_params.get('sort_reprimand')
        min_reprimand  = request.query_params.get('min_reprimand')
        max_reprimand  = request.query_params.get('max_reprimand')
        has_reprimand  = request.query_params.get('has_reprimand')

        if has_reprimand is not None:
            if has_reprimand.lower() == 'true':
                students = students.filter(reprimand_count__gt=0)
            elif has_reprimand.lower() == 'false':
                students = students.filter(reprimand_count=0)

        if min_reprimand is not None:
            try:
                students = students.filter(reprimand_count__gte=int(min_reprimand))
            except ValueError:
                return fail("min_reprimand butun son bo'lishi kerak")

        if max_reprimand is not None:
            try:
                students = students.filter(reprimand_count__lte=int(max_reprimand))
            except ValueError:
                return fail("max_reprimand butun son bo'lishi kerak")

        if sort_reprimand == 'most':
            students = students.order_by('-reprimand_count')
        elif sort_reprimand == 'least':
            students = students.order_by('reprimand_count')

        if request.query_params.get("export") == "pdf":
            return generate_student_pdf(students, request)

        paginator = StudentPagination()
        page = paginator.paginate_queryset(students, request)
        if page is not None:
            return paginator.get_paginated_response(
                StudentSerializer(page, many=True).data
            )

        return ok("Studentlar ro'yxati", StudentSerializer(students, many=True).data)

    def post(self, request):
        user = request.user
        if user.role.id not in [ROLE_ADMIN_ID, *STAFF_ROLE_IDS]:
            return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

        if user.role.id in STAFF_ROLE_IDS:
            group_id = request.data.get('group')
            if not group_id:
                return fail("group kiritilmadi")
            try:
                group = Group.objects.get(id=group_id)
            except Group.DoesNotExist:
                return fail("Guruh topilmadi", status.HTTP_404_NOT_FOUND)
            if not user.faculty or group.direction.faculty != user.faculty:
                return fail("Bu guruh sizning fakultetingizga tegishli emas", status.HTTP_403_FORBIDDEN)

        ser = StudentSerializer(data=request.data)
        if ser.is_valid():
            student = ser.save()

            log_action(request, model_name='Student', object_id=student.id,
                       description=f"Yangi student qo'shildi: {student.first_name} {student.last_name}",
                       status_code=201)

            return ok("Student qo'shildi", StudentSerializer(student).data, status.HTTP_201_CREATED)
        return fail(ser.errors)

    def patch(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id:
            return fail("student_id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err: return err

        ser = StudentSerializer(student, data=request.data, partial=True)
        if ser.is_valid():
            ser.save()

            log_action(request, model_name='Student', object_id=student.id,
                       description=f"Student yangilandi: {student.first_name} {student.last_name}",
                       status_code=200)

            return ok("Student yangilandi", ser.data)
        return fail(ser.errors)

    def delete(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id:
            return fail("student_id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err: return err

        name = f"{student.first_name} {student.last_name}"
        student.delete()

        log_action(request, action='DELETE', model_name='Student', object_id=student_id,
                   description=f"Student o'chirildi: {name}", status_code=200)

        return ok("Student o'chirildi", None)

class BaseCRUD(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class   = None
    related_name       = None
    is_one_to_one      = False

    def get_serializer(self, *args, **kwargs):
        return self.serializer_class(*args, **kwargs, context={'request': self.request})

    def _get_obj(self, student, record_id=None):
        if self.is_one_to_one:
            return getattr(student, self.related_name)
        return getattr(student, self.related_name).get(id=record_id)

    def _model_name(self):
        return self.serializer_class.Meta.model.__name__

    def get(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id: return fail("student_id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err: return err

        try:
            obj = self._get_obj(student) if self.is_one_to_one else getattr(student, self.related_name).all()
        except Exception:
            return fail("Ma'lumot topilmadi", status.HTTP_404_NOT_FOUND)

        ser = self.get_serializer(obj) if self.is_one_to_one else self.get_serializer(obj, many=True)
        return ok("Ma'lumot", ser.data)

    def post(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id: return fail("student_id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err: return err

        if self.is_one_to_one:
            try:
                self._get_obj(student)
                return fail("Ma'lumot allaqachon mavjud")
            except Exception:
                pass

        ser = self.get_serializer(data=request.data)
        if ser.is_valid():
            obj = ser.save(student=student)

            log_action(request, model_name=self._model_name(), object_id=getattr(obj, 'id', ''),
                       description=f"{self._model_name()} yaratildi (student_id={student_id})",
                       status_code=201)

            return ok("Yaratildi", ser.data, status.HTTP_201_CREATED)
        return fail(ser.errors)

    def patch(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id: return fail("student_id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err: return err

        try:
            record_id = request.query_params.get('id') if not self.is_one_to_one else None
            obj = self._get_obj(student, record_id)
        except Exception:
            return fail("Topilmadi", status.HTTP_404_NOT_FOUND)

        ser = self.get_serializer(obj, data=request.data, partial=True)
        if ser.is_valid():
            ser.save()

            log_action(request, model_name=self._model_name(), object_id=record_id or '',
                       description=f"{self._model_name()} yangilandi (student_id={student_id})",
                       status_code=200)

            return ok("Yangilandi", ser.data)
        return fail(ser.errors)

    def delete(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id: return fail("student_id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err: return err

        try:
            record_id = request.query_params.get('id') if not self.is_one_to_one else None
            obj = self._get_obj(student, record_id)
        except Exception:
            return fail("Topilmadi", status.HTTP_404_NOT_FOUND)

        obj.delete()

        log_action(request, action='DELETE', model_name=self._model_name(), object_id=record_id or '',
                   description=f"{self._model_name()} o'chirildi (student_id={student_id})",
                   status_code=200)

        return ok("O'chirildi", None)

class StudentDetailCRUD(BaseCRUD):
    serializer_class = StudentDetailSerializer
    related_name     = 'details'

class AchievementCRUD(BaseCRUD):
    serializer_class = AchievementSerializer
    related_name     = 'achievements'

class HealthInfoCRUD(BaseCRUD):
    serializer_class = HealthInfoSerializer
    related_name     = 'health_info'
    is_one_to_one    = True

class LanguageInfoCRUD(BaseCRUD):
    serializer_class = LanguageInfoSerializer
    related_name     = 'language_info'

class SocialLinkCRUD(BaseCRUD):
    serializer_class = SocialLinkSerializer
    related_name     = 'social_links'

class ReprimandCRUD(BaseCRUD):
    serializer_class = ReprimandSerializer
    related_name     = 'reprimands'

class FamilySocialStatusCRUD(BaseCRUD):
    serializer_class = FamilySocialStatusSerializer
    related_name     = 'family_social_status'
    is_one_to_one    = True

class FamilyMemberCRUD(BaseCRUD):
    serializer_class = FamilyMemberSerializer
    related_name     = 'family_members'

class InterestCRUD(BaseCRUD):
    serializer_class = InterestSerializer
    related_name     = 'interests'

class SocialRegistryCRUD(BaseCRUD):
    serializer_class = SocialRegistrySerializer
    related_name     = 'social_registries'

class DormitoryCRUD(BaseCRUD):
    serializer_class = DormitorySerializer
    related_name     = 'dormitory'
    is_one_to_one    = True

class GiftedCRUD(BaseCRUD):
    serializer_class = GiftedSerializer
    related_name     = 'gifteds'

class ProtectionOrderCRUD(BaseCRUD):
    serializer_class = ProtectionOrderSerializer
    related_name     = 'protection_orders'

def student_completion(student) -> float:
    total  = 0
    filled = 0

    def check(val):
        return bool(val and str(val).strip())

    for field in ['image', 'image_hemis', 'phone', 'email', 'country']:
        total += 1
        if field == 'image':
            filled += 1 if (student.image or student.image_hemis) else 0
        else:
            filled += 1 if check(getattr(student, field, None)) else 0

    detail = student.details.first()
    detail_fields = [
        'p_country', 'p_region', 'p_district',   # doimiy manzil
        't_country', 't_region', 't_district',   # vaqtincha manzil
        't_latitude', 't_longitude',              # geolokatsiya
        'education_type', 'pnfl',
    ]
    for field in detail_fields:
        total += 1
        filled += 1 if (detail and check(getattr(detail, field, None))) else 0

    # passport PDF
    total += 1
    filled += 1 if (detail and detail.passport_pdf) else 0

    # 3. Sog'liq holati (HealthInfo)
    total += 1
    filled += 1 if hasattr(student, 'health_info') and student.health_info else 0

    # 4. Til bilish (kamida 1 ta LanguageInfo)
    total += 1
    filled += 1 if student.language_info.exists() else 0

    # 5. Oilaviy holat (FamilySocialStatus)
    total += 1
    filled += 1 if hasattr(student, 'family_social_status') and student.family_social_status else 0

    # 6. Oila a'zolari (kamida 1 ta FamilyMember)
    total += 1
    filled += 1 if student.family_members.exists() else 0

    # 7. Turar joy (Dormitory)
    total += 1
    filled += 1 if hasattr(student, 'dormitory') and student.dormitory else 0

    # 8. Ijtimoiy tarmoq (kamida 1 ta SocialLink)
    total += 1
    filled += 1 if student.social_links.exists() else 0

    return round((filled / total) * 100, 1) if total else 0.0

def group_completion_rate(group) -> float:
    """Guruh bo'yicha o'rtacha to'ldirilganlik %"""
    students = group.students.prefetch_related(
        'details', 'health_info', 'language_info',
        'family_social_status', 'family_members',
        'dormitory', 'social_links',
    )
    if not students.exists():
        return 0.0
    total = sum(student_completion(s) for s in students)
    return round(total / students.count(), 1)

def faculty_completion_rate(faculty) -> float:
    groups = Group.objects.filter(direction__faculty=faculty)
    if not groups.exists():
        return 0.0
    rates = [group_completion_rate(g) for g in groups]
    return round(sum(rates) / len(rates), 1)

class Statistika(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # ── ADMIN ──────────────────────────────
        if user.role.id == ROLE_ADMIN_ID:
            return ok("Admin statistikasi", {
                'faculty'   : Faculty.objects.count(),
                'direction' : Direction.objects.count(),
                'group'     : Group.objects.count(),
                'student'   : Student.objects.count(),
                'reprimand' : Reprimand.objects.count(),          # umumiy hayfisandlar
            })

        # ── DEKAN / ZAM_DEKAN ──────────────────
        if user.role.id in [ROLE_DEKAN_ID, ROLE_ZAM_DEKAN_ID]:
            if not user.faculty:
                return fail("Sizga biriktirilgan fakultet yo'q")

            faculty  = user.faculty
            groups   = Group.objects.filter(direction__faculty=faculty)
            students = Student.objects.filter(group__in=groups)

            # Guruhlar bo'yicha to'ldirilganlik + hayfisand (TT 7.3, 10.2)
            groups_stat = []
            for g in groups.prefetch_related(
                'students__details',
                'students__health_info',
                'students__language_info',
                'students__family_social_status',
                'students__family_members',
                'students__dormitory',
                'students__social_links',
                'students__reprimands',
            ):
                groups_stat.append({
                    'group_id'        : g.id,
                    'group_name'      : g.name,
                    'student_count'   : g.students.count(),
                    'reprimand_count' : Reprimand.objects.filter(student__group=g).count(),
                    'completion_rate' : group_completion_rate(g),   # to'ldirilganlik %
                })

            # To'liq to'ldirilmagan talabalar ro'yxati (TT 10.1)
            incomplete = []
            for s in students.prefetch_related(
                'details', 'health_info', 'language_info',
                'family_social_status', 'family_members',
                'dormitory', 'social_links',
            ):
                rate = student_completion(s)
                if rate < 100:
                    incomplete.append({
                        'student_id'      : s.id,
                        'full_name'       : f"{s.last_name} {s.first_name} {s.third_name}",
                        'group'           : s.group.name,
                        'completion_rate' : rate,
                    })

            role_label = 'Dekan' if user.role.id == ROLE_DEKAN_ID else 'Zam dekan'
            return ok(f"{role_label} statistikasi", {
                'faculty_name'      : faculty.name,
                'direction_count'   : Direction.objects.filter(faculty=faculty).count(),
                'group_count'       : groups.count(),
                'student_count'     : students.count(),
                'reprimand_count'   : Reprimand.objects.filter(student__in=students).count(),
                'faculty_completion': faculty_completion_rate(faculty),  # fakultet o'rtacha %
                'groups_stat'       : groups_stat,                       # guruhlar kesimida
                'incomplete_students': sorted(
                    incomplete, key=lambda x: x['completion_rate']
                ),                                                        # to'ldirilmaganlar
            })

        # ── TUTOR ──────────────────────────────
        if user.role.id == ROLE_TUTOR_ID:
            groups   = Group.objects.filter(tutor=user)
            students = Student.objects.filter(group__in=groups)

            # Guruhlar bo'yicha statistika (TT 7.2, 7.3)
            groups_stat = []
            for g in groups.prefetch_related(
                'students__details',
                'students__health_info',
                'students__language_info',
                'students__family_social_status',
                'students__family_members',
                'students__dormitory',
                'students__social_links',
                'students__reprimands',
            ):
                groups_stat.append({
                    'group_id'        : g.id,
                    'group_name'      : g.name,
                    'student_count'   : g.students.count(),
                    'reprimand_count' : Reprimand.objects.filter(student__group=g).count(),
                    'completion_rate' : group_completion_rate(g),
                })

            # To'ldirilmagan profillar ro'yxati (TT 7.2 — ixtiyoriy)
            incomplete = []
            for s in students.prefetch_related(
                'details', 'health_info', 'language_info',
                'family_social_status', 'family_members',
                'dormitory', 'social_links',
            ):
                rate = student_completion(s)
                if rate < 100:
                    incomplete.append({
                        'student_id'      : s.id,
                        'full_name'       : f"{s.last_name} {s.first_name} {s.third_name}",
                        'group'           : s.group.name,
                        'completion_rate' : rate,
                    })

            # Eng ko'p hayfisand olgan talabalar (TT 7.2 — ixtiyoriy)
            top_reprimanded = (
                students
                .annotate(rep_count=Count('reprimands'))
                .filter(rep_count__gt=0)
                .order_by('-rep_count')
                .values('id', 'first_name', 'last_name', 'third_name', 'group__name', 'rep_count')
                [:10]
            )

            return ok("Tutor statistikasi", {
                'group_count'       : groups.count(),
                'student_count'     : students.count(),
                'reprimand_count'   : Reprimand.objects.filter(student__in=students).count(),
                'avg_completion'    : round(
                    sum(g['completion_rate'] for g in groups_stat) / len(groups_stat), 1
                ) if groups_stat else 0.0,                               # o'rtacha to'ldirilganlik %
                'groups_stat'       : groups_stat,
                'incomplete_students': sorted(
                    incomplete, key=lambda x: x['completion_rate']
                ),
                'top_reprimanded'   : list(top_reprimanded),             # eng ko'p hayfisandlilar
            })

        return fail("Sizning rolingiz uchun statistika mavjud emas")

class ReprimandStudentGet(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role.id == ROLE_ADMIN_ID:
            students = Student.objects.all()
        elif user.role.id in STAFF_ROLE_IDS:
            if not user.faculty:
                return fail("Sizga biriktirilgan fakultet yo'q", status.HTTP_404_NOT_FOUND)
            students = faculty_students(user)
        else:
            return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

        students = (
            students
            .annotate(reprimand_count=Count('reprimands'))
            .filter(reprimand_count__gt=0)
            .select_related('group')
            .order_by('-reprimand_count')
        )

        data = [
            {
                'id'             : s.id,
                'first_name'     : s.first_name,
                'last_name'      : s.last_name,
                'third_name'     : s.third_name,
                'hemis_id'       : s.hemis_id,
                'group'          : s.group.name,
                'course'         : s.course,
                'reprimand_count': s.reprimand_count,
            }
            for s in students
        ]

        return ok("Hayfnoma olgan talabalar", {
            'total_students': students.count(),
            'students'      : data,
        })

class RoleApiview(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return ok("Rollar ro'yxati", Roleserializer(Role.objects.all(), many=True).data)

class categoryInterstView(viewsets.ModelViewSet):
    serializer_class   = CategoryInterestSerializer
    queryset           = CategoryInterest.objects.all()
    permission_classes = [IsAuthenticated]










