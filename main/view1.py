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

# ─────────────────────────────── konstantalar ────────────────────────────────
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

# ─────────────────────────────── yordamchi funksiyalar ───────────────────────
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
    """Userning fakultetiga tegishli studentlar queryset."""
    return Student.objects.filter(group__direction__faculty=user.faculty)


# ─────────────────────────────── Auth ────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return fail("username yoki password majburiy")

    user = authenticate(request, username=username, password=password)
    if user is None:
        return fail("username yoki password noto'g'ri")

    refresh = RefreshToken.for_user(user)
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
            return ok("Muvaffaqiyatli chiqildi", None)
        except Exception as e:
            return fail(str(e))


# ─────────────────────────────── HEMIS import ────────────────────────────────
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
        max_pages=request.data.get("max_pages", 5),
    )
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
        max_pages=request.data.get("max_pages", 5),
    )
    return Response({"message": "Yangilash muvaffaqiyatli yakunlandi", **result})


# ─────────────────────────────── User CRUD ───────────────────────────────────
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
            if err: return err
        elif role_name == ROLE_ZAM_DEKAN:
            err = self._check_role_permission(user, new_role_id, [ROLE_TUTOR_ID],
                                              "Siz faqat tutor yarata olasiz")
            if err: return err
        else:
            return super().create(request, *args, **kwargs)

        data = request.data.copy()
        data['faculty'] = user.faculty_id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({'success': True, 'message': "Yaratildi", 'data': serializer.data},
                        status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        self.perform_destroy(self.get_object())
        return Response({'success': True, 'message': "O'chirildi"})

    def update(self, request, *args, **kwargs):
        partial    = kwargs.pop('partial', False)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({'success': True, 'message': "Yangilandi", 'data': serializer.data})

    def list(self, request, *args, **kwargs):
        return Response({'success': True, 'data': self.get_serializer(self.get_queryset(), many=True).data})

    def retrieve(self, request, *args, **kwargs):
        return Response({'success': True, 'data': self.get_serializer(self.get_object()).data})


# ─────────────────────────────── Faculty / Direction ─────────────────────────
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


# ─────────────────────────────── Groups ──────────────────────────────────────
class GroupsGetApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        search             = request.query_params.get('search')
        education_language = request.query_params.get('education_language')
        sort_reprimand     = request.query_params.get('sort_reprimand')

        def apply_filters(qs):
            if search:
                qs = qs.filter(name__icontains=search)
            if education_language:
                qs = qs.filter(education_language__icontains=education_language)
            return qs

        if user.role.id == ROLE_ADMIN_ID:
            direction_id = request.query_params.get('direction_id')
            if not direction_id:
                return fail("direction_id parametri kiritilmadi")
            try:
                direction = Direction.objects.get(id=direction_id)
            except Direction.DoesNotExist:
                return fail("Yo'nalish topilmadi", status.HTTP_404_NOT_FOUND)
            qs  = apply_filters(Group.objects.filter(direction=direction))
            msg = "Guruhlar ro'yxati"

        elif user.role.id in STAFF_ROLE_IDS:
            if not user.faculty:
                return fail("Sizga biriktirilgan fakultet yo'q", status.HTTP_404_NOT_FOUND)
            qs  = apply_filters(Group.objects.filter(direction__faculty=user.faculty))
            msg = "Sizning fakultetingiz guruhlari"

        else:
            return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

        qs  = qs.select_related('tutor')
        ser = GroupSerializer(qs, many=True, context={'request': request, 'sort_reprimand': sort_reprimand})
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
        faculty_id = request.query_params.get('faculty_id')
        group_id   = request.query_params.get('group_id')

        if faculty_id:
            try:
                faculty = Faculty.objects.get(id=faculty_id)
            except Faculty.DoesNotExist:
                return fail("Fakultet topilmadi", status.HTTP_404_NOT_FOUND)

        if student_id:
            try:
                student = Student.objects.prefetch_related('details', *PREFETCH_FIELDS).get(id=student_id)
            except Student.DoesNotExist:
                return fail("Student topilmadi", status.HTTP_404_NOT_FOUND)

            if user.role.id == ROLE_ADMIN_ID:
                students = Student.objects.filter(group__direction__faculty=faculty)
            elif user.role.id in STAFF_ROLE_IDS:
                if not user.faculty or user.faculty != faculty:
                    return fail("Bu fakultet sizga tegishli emas", status.HTTP_403_FORBIDDEN)
                students = faculty_students(user)
            else:
                return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

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

        if request.query_params.get("export") == "pdf":
            return generate_student_pdf(students, request)

        paginator = StudentPagination()
        page = paginator.paginate_queryset(students, request)
        if page is not None:
            return paginator.get_paginated_response(StudentSerializer(page, many=True).data)

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
            return ok("Student yangilandi", ser.data)
        return fail(ser.errors)

    def delete(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id:
            return fail("student_id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err: return err
        student.delete()
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
            ser.save(student=student)
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


# ─────────────────────────────── Statistika ──────────────────────────────────
class Statistika(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role.id == ROLE_ADMIN_ID:
            return ok("Admin statistikasi", {
                'faculty'  : Faculty.objects.count(),
                'direction': Direction.objects.count(),
                'group'    : Group.objects.count(),
                'student'  : Student.objects.count(),
            })

        if user.role.id in [ROLE_DEKAN_ID, ROLE_ZAM_DEKAN_ID]:
            if not user.faculty:
                return fail("Sizga biriktirilgan fakultet yo'q")
            return ok(f"{'Dekan' if user.role.id == ROLE_DEKAN_ID else 'Zam dekan'} statistikasi", {
                'faculty'  : user.faculty.name,
                'direction': Direction.objects.filter(faculty=user.faculty).count(),
                'group'    : Group.objects.filter(direction__faculty=user.faculty).count(),
                'student'  : Student.objects.filter(group__direction__faculty=user.faculty).count(),
            })

        if user.role.id == ROLE_TUTOR_ID:
            groups = Group.objects.filter(tutor=user)
            return ok("Tutor statistikasi", {
                'group'  : groups.count(),
                'student': Student.objects.filter(group__in=groups).count(),
            })

        return fail("Sizning rolingiz uchun statistika mavjud emas")


# ─────────────────────────────── Reprimand ───────────────────────────────────
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


# ─────────────────────────────── Boshqalar ───────────────────────────────────
class RoleApiview(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return ok("Rollar ro'yxati", Roleserializer(Role.objects.all(), many=True).data)


class categoryInterstView(viewsets.ModelViewSet):
    serializer_class   = CategoryInterestSerializer
    queryset           = CategoryInterest.objects.all()
    permission_classes = [IsAuthenticated]