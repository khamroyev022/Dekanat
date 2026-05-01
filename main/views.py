from lib2to3.pgen2.tokenize import group
from .export_pdf import *
from django.contrib.admin.templatetags.admin_list import pagination
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
import requests
from config.settings import HEMIS_TOKEN
from .hemis_update_db import HEMISStudentUpdate
from .models import *
from django.contrib.auth import authenticate

from .pagination import StudentPagination
from .serializers import *
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets
from rest_framework import status
from .hemis_get_student import HEMISStudentImportService
from rest_framework_simplejwt.tokens import RefreshToken
from .persmission import *
from .filters import *
from django.db.models import Count, Exists, OuterRef

ROLE_TUTOR_ID = 2
ROLE_ADMIN_ID = 1
ROLE_DEKAN_ID = 3
ROLE_ZAM_DEKAN_ID = 4

DEKAN_ROLE_IDS = [3, 4]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_students(request):
    base_url   = request.data.get("base_url") or "https://student.bsmi.uz/rest/v1/data/student-list"
    token      = request.data.get("token") or HEMIS_TOKEN
    start_page = request.data.get("start_page", 1)
    max_pages  = request.data.get("max_pages", 5)

    service = HEMISStudentImportService(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
        save_images=False,
    )
    result = service.run(start_page=start_page, max_pages=max_pages)

    return Response({
        "message":    "Import muvaffaqiyatli yakunlandi",
        "created":    result["created"],
        "updated":    result["updated"],
        "last_page":  result["last_page"],
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_students(request):
    base_url   = "https://student.bsmi.uz/rest/v1/data/student-list"
    token      = HEMIS_TOKEN
    start_page = request.data.get("start_page", 1)
    max_pages  = request.data.get("max_pages", 583)

    service = HEMISStudentUpdate(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
        save_images=False,
    )
    result = service.run(start_page=start_page, max_pages=max_pages)

    return Response({
        "message":      "Yangilash muvaffaqiyatli yakunlandi",
        "updated":      result["updated"],
        "skipped":      result["skipped"],
        "last_page":    result["last_page"],
        "failed_pages": result["failed_pages"],
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response({
            'success': False,
            'message': "username yoki password majburiy",
            'data':    None,
        }, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(request, username=username, password=password)

    if user is None:
        return Response({
            'success': False,
            'message': "username yoki password noto'g'ri",
            'data':    None,
        }, status=status.HTTP_400_BAD_REQUEST)

    refresh    = RefreshToken.for_user(user)
    serializer = LoginSerializer(user)

    return Response({
        'success':  True,
        'message':  "Login muvaffaqiyatli",
        'data':     serializer.data,
        'access':   str(refresh.access_token),
        'username': user.username,
    }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({
                'success': True,
                'message': "Muvaffaqiyatli chiqildi",
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'message': str(e),
            }, status=status.HTTP_400_BAD_REQUEST)


class CreateUserViewSet(viewsets.ModelViewSet):
    serializer_class   = CreateUserSerializer
    permission_classes = [UserCRUDPermission]

    def get_queryset(self):
        user      = self.request.user
        role_name = getattr(user.role, 'name', '').lower().strip()

        if user.is_superuser or role_name == ROLE_ADMIN:
            return (
                CustomUser.objects.all()
                .prefetch_related('tutor_groups')
                .select_related('role', 'faculty')
            )

        if role_name == ROLE_DEKAN:
            return (
                CustomUser.objects.filter(
                    Q(id=user.id) |
                    Q(faculty_id=user.faculty_id, role_id=ROLE_TUTOR_ID) |
                    Q(faculty_id=user.faculty_id, role_id=ROLE_ZAM_DEKAN_ID)
                )
                .prefetch_related('tutor_groups')
                .select_related('role', 'faculty')
            )

        if role_name == ROLE_ZAM_DEKAN:
            if not user.faculty_id:
                return CustomUser.objects.none()
            return (
                CustomUser.objects.filter(
                    faculty_id=user.faculty_id,
                    role__name__iexact='tutor',
                )
                .prefetch_related('tutor_groups')
                .select_related('role', 'faculty')
            )

        return CustomUser.objects.none()

    def _resolve_role(self, role_id):
        try:
            return Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return None

    def create(self, request, *args, **kwargs):
        user      = request.user
        role_name = getattr(user.role, 'name', '').lower().strip()

        if role_name == ROLE_DEKAN:
            try:
                new_role_id = int(request.data.get('role'))
            except (TypeError, ValueError):
                return Response({'success': False, 'message': "Role kiritilmagan"},
                                status=status.HTTP_400_BAD_REQUEST)

            if new_role_id not in [ROLE_TUTOR_ID, ROLE_ZAM_DEKAN_ID]:
                return Response({'success': False,
                                 'message': "Siz faqat tutor yoki zam dekan yarata olasiz"},
                                status=status.HTTP_403_FORBIDDEN)

            data = request.data.copy()
            data['faculty'] = user.faculty_id
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response({'success': True, 'message': "Foydalanuvchi yaratildi",
                             'data': serializer.data}, status=status.HTTP_201_CREATED)

        if role_name == ROLE_ZAM_DEKAN:
            try:
                new_role_id = int(request.data.get('role'))
            except (TypeError, ValueError):
                return Response({'success': False, 'message': "Role kiritilmagan"},
                                status=status.HTTP_400_BAD_REQUEST)

            if new_role_id != ROLE_TUTOR_ID:
                return Response({'success': False, 'message': "Siz faqat tutor yarata olasiz"},
                                status=status.HTTP_403_FORBIDDEN)

            data = request.data.copy()
            data['faculty'] = user.faculty_id
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response({'success': True, 'message': "Tutor yaratildi",
                             'data': serializer.data}, status=status.HTTP_201_CREATED)

        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self.perform_destroy(self.get_object())
        return Response({'success': True, 'message': "Foydalanuvchi o'chirildi"},
                        status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        partial    = kwargs.pop('partial', False)
        instance   = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({'success': True, 'message': "Yangilandi", 'data': serializer.data})

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response({'success': True, 'data': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return Response({'success': True, 'data': serializer.data})


class FacultyGEtApipview(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role.id == 1:
            faculty = Faculty.objects.all()
            ser = Facultyserializer(faculty, many=True)
            return Response({
                'success': True,
                'user':    user.username,
                'message': "Hamma fakultetlar ro'yxati",
                'data':    ser.data,
            }, status=status.HTTP_200_OK)
        elif user.role.id == 2 or 3 or 4:
            faculty = Faculty.objects.filter(dekans=user)
            ser = Facultyserializer(faculty, many=True)
            return Response({
                'success': True,
                'user':    user.username,
                'message': "Sizning fakultetingiz",
                'data':    ser.data,
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message': "Xatolik yuz berdi",
                'data':    {},
            }, status=status.HTTP_400_BAD_REQUEST)


class DirectionGETApiview(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user       = request.user
        faculty_id = request.query_params.get('faculty_id')

        if not faculty_id:
            return Response({
                'success': False,
                'message': 'faculty_id parametri kiritilmadi',
                'data':    None,
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            faculty_id = Faculty.objects.get(id=faculty_id)
        except Faculty.DoesNotExist:
            return Response({
                'success': False,
                'message': "Fakultet topilmadi",
                'data':    None,
            }, status=status.HTTP_400_BAD_REQUEST)

        if user.role.id == 1:
            direction = Direction.objects.filter(faculty_id=faculty_id)
            ser = Directionserializer(direction, many=True)
            return Response({
                'success': True,
                'message': "Yo'naishlar",
                'faculty': faculty_id.name,
                'data':    ser.data,
            }, status.HTTP_200_OK)

        elif user.role.id in [2, 3, 4]:
            if not user.faculty:
                return Response({
                    'success': False,
                    'message': "Sizga biriktirilgan fakultet yo'q",
                    'data':    None,
                }, status=status.HTTP_404_NOT_FOUND)

            directions = Direction.objects.filter(faculty=user.faculty)
            ser = DirectionSerializer(directions, many=True)
            return Response({
                'success': True,
                'message': "Sizning fakultetingiz yo'nalishlari",
                'faculty': user.faculty.name,
                'data':    ser.data,
            }, status=status.HTTP_200_OK)

        else:
            return Response({
                'success': False,
                'message': "Ruxsat yo'q",
                'data':    None,
            }, status=status.HTTP_403_FORBIDDEN)


class GroupsGetApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user               = request.user
        search             = request.query_params.get('search')
        education_language = request.query_params.get('education_language')
        sort_reprimand     = request.query_params.get('sort_reprimand')

        def apply_filters(queryset):
            if search:
                queryset = queryset.filter(name__icontains=search)
            if education_language:
                queryset = queryset.filter(education_language__icontains=education_language)
            return queryset

        if user.role.id == 1:
            direction_id = request.query_params.get('direction_id')
            if not direction_id:
                return fail("direction_id parametri kiritilmadi")

            try:
                direction = Direction.objects.get(id=direction_id)
            except Direction.DoesNotExist:
                return fail("Yo'nalish topilmadi", status.HTTP_404_NOT_FOUND)

            groups = apply_filters(
                Group.objects.filter(direction=direction).select_related('tutor')
            )
            ser = GroupSerializer(
                groups, many=True,
                context={'request': request, 'sort_reprimand': sort_reprimand}  # ← context
            )
            return ok("Guruhlar ro'yxati", ser.data)

        elif user.role.id in [2, 3, 4]:
            if not user.faculty:
                return fail("Sizga biriktirilgan fakultet yo'q", status.HTTP_404_NOT_FOUND)

            groups = apply_filters(
                Group.objects.filter(direction__faculty=user.faculty).select_related('tutor')
            )
            ser = GroupSerializer(
                groups, many=True,
                context={'request': request, 'sort_reprimand': sort_reprimand}
            )
            return ok("Sizning fakultetingiz guruhlari", ser.data)

        return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)


PREFETCH_FIELDS = [
    'achievements', 'health_info', 'language_info',
    'social_links', 'reprimands', 'family_social_status',
    'family_members', 'interests', 'social_registries',
    'dormitory', 'gifteds', 'protection_orders',
]


class StudentCRUD(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user       = request.user
        student_id = request.query_params.get('student_id')
        group_id   = request.query_params.get('group_id')

        # ── Bitta student ──────────────────────────────────────────────────────
        if student_id:
            try:
                student = Student.objects.prefetch_related(
                    'details', *PREFETCH_FIELDS
                ).get(id=student_id)
            except Student.DoesNotExist:
                return fail("Student topilmadi", status.HTTP_404_NOT_FOUND)

            if user.role.id in [2, 3, 4]:
                if not user.faculty:
                    return fail("Sizga biriktirilgan fakultet yo'q", status.HTTP_404_NOT_FOUND)
                if student.group.direction.faculty != user.faculty:
                    return fail("Bu student sizning fakultetingizga tegishli emas",
                                status.HTTP_403_FORBIDDEN)
            elif user.role.id != 1:
                return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

            ser = StudentFullSerializer(student)
            return ok("Student ma'lumoti", ser.data)

        # ── Queryset ───────────────────────────────────────────────────────────
        if group_id:
            try:
                group = Group.objects.get(id=group_id)
            except Group.DoesNotExist:
                return fail("Guruh topilmadi", status.HTTP_404_NOT_FOUND)

            if user.role.id in [2, 3, 4]:
                if not user.faculty:
                    return fail("Sizga biriktirilgan fakultet yo'q", status.HTTP_404_NOT_FOUND)
                if group.direction.faculty != user.faculty:
                    return fail("Bu guruh sizning fakultetingizga tegishli emas",
                                status.HTTP_403_FORBIDDEN)
            elif user.role.id != 1:
                return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

            students = Student.objects.filter(group=group).prefetch_related(*PREFETCH_FIELDS)

        elif user.role.id == 1:
            students = Student.objects.all().prefetch_related(*PREFETCH_FIELDS)

        elif user.role.id in [2, 3, 4]:
            if not user.faculty:
                return fail("Sizga biriktirilgan fakultet yo'q", status.HTTP_404_NOT_FOUND)
            students = Student.objects.filter(
                group__direction__faculty=user.faculty
            ).prefetch_related(*PREFETCH_FIELDS)

        else:
            return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

        # ── Filter ─────────────────────────────────────────────────────────────
        f = StudentFilter(request.query_params, queryset=students)
        if not f.is_valid():
            return fail(f.errors)
        students = f.qs


        if request.query_params.get("export") == "pdf":
            return generate_student_pdf(students, request)

        # ── Sahifalash ─────────────────────────────────────────────────────────
        paginator = StudentPagination()
        page = paginator.paginate_queryset(students, request)
        if page is not None:
            ser = StudentSerializer(page, many=True)
            return paginator.get_paginated_response(ser.data)

        ser = StudentSerializer(students, many=True)
        return ok("Studentlar ro'yxati", ser.data)

    def post(self, request):
        user = request.user

        if user.role.id not in [1, 2, 3, 4]:
            return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

        if user.role.id in [2, 3, 4]:
            group_id = request.data.get('group')
            if not group_id:
                return fail("group kiritilmadi")
            try:
                group = Group.objects.get(id=group_id)
            except Group.DoesNotExist:
                return fail("Guruh topilmadi", status.HTTP_404_NOT_FOUND)

            if not user.faculty:
                return fail("Sizga biriktirilgan fakultet yo'q", status.HTTP_404_NOT_FOUND)
            if group.direction.faculty != user.faculty:
                return fail("Bu guruh sizning fakultetingizga tegishli emas",
                            status.HTTP_403_FORBIDDEN)

        ser = StudentSerializer(data=request.data)
        if ser.is_valid():
            student = ser.save()
            return ok("Student qo'shildi", StudentSerializer(student).data,
                      status.HTTP_201_CREATED)
        return fail(ser.errors)

    def patch(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id:
            return fail("student_id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err:
            return err
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
        if err:
            return err
        student.delete()
        return ok("Student o'chirildi", None)


# ─────────────────────────────────────────────────────────────────────────────
def ok(message, data, code=status.HTTP_200_OK):
    return Response({'success': True, 'message': message, 'data': data}, status=code)


def fail(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({'success': False, 'message': message, 'data': None}, status=code)


def get_student(student_id):
    try:
        return Student.objects.get(id=student_id), None
    except Student.DoesNotExist:
        return None, fail("Student topilmadi", status.HTTP_404_NOT_FOUND)


# ─────────────────────────────────────────────────────────────────────────────
class BaseCRUD(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class   = None
    related_name       = None
    is_one_to_one      = False

    def get_serializer(self, *args, **kwargs):
        kwargs['context'] = {'request': self.request}
        return self.serializer_class(*args, **kwargs)

    def get_object(self, student):
        if self.is_one_to_one:
            return getattr(student, self.related_name)
        return None

    def get(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id:
            return fail("student_id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err:
            return err

        if self.is_one_to_one:
            try:
                obj = self.get_object(student)
            except Exception:
                return fail("Ma'lumot topilmadi", status.HTTP_404_NOT_FOUND)
            ser = self.get_serializer(obj)
            return ok("Ma'lumot", ser.data)

        qs  = getattr(student, self.related_name).all()
        ser = self.get_serializer(qs, many=True)
        return ok("Ma'lumotlar", ser.data)

    def post(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id:
            return fail("student_id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err:
            return err

        if self.is_one_to_one:
            try:
                self.get_object(student)
                return fail("Ma'lumot allaqachon mavjud", status.HTTP_400_BAD_REQUEST)
            except Exception:
                pass

        ser = self.get_serializer(data=request.data)
        if ser.is_valid():
            ser.save(student=student)
            return ok("Yaratildi", ser.data, status.HTTP_201_CREATED)
        return fail(ser.errors)

    def patch(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id:
            return fail("student_id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err:
            return err

        if self.is_one_to_one:
            try:
                obj = self.get_object(student)
            except Exception:
                return fail("Ma'lumot topilmadi", status.HTTP_404_NOT_FOUND)
        else:
            record_id = request.query_params.get('id')
            if not record_id:
                return fail("id parametri kiritilmadi")
            try:
                obj = getattr(student, self.related_name).get(id=record_id)
            except Exception:
                return fail("Topilmadi", status.HTTP_404_NOT_FOUND)

        ser = self.get_serializer(obj, data=request.data, partial=True)
        if ser.is_valid():
            ser.save()
            return ok("Yangilandi", ser.data)
        return fail(ser.errors)

    def delete(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id:
            return fail("student_id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err:
            return err

        if self.is_one_to_one:
            try:
                obj = self.get_object(student)
            except Exception:
                return fail("Ma'lumot topilmadi", status.HTTP_404_NOT_FOUND)
        else:
            record_id = request.query_params.get('id')
            if not record_id:
                return fail("id parametri kiritilmadi")
            try:
                obj = getattr(student, self.related_name).get(id=record_id)
            except Exception:
                return fail("Topilmadi", status.HTTP_404_NOT_FOUND)

        obj.delete()
        return ok("O'chirildi", None)


# ─────────────────────────────────────────────────────────────────────────────
class StudentDetailCRUD(BaseCRUD):
    serializer_class   = StudentDetailSerializer
    related_name       = 'details'
    permission_classes = [IsAuthenticated]

class AchievementCRUD(BaseCRUD):
    serializer_class   = AchievementSerializer
    related_name       = 'achievements'
    permission_classes = [IsAuthenticated]

class HealthInfoCRUD(BaseCRUD):
    serializer_class   = HealthInfoSerializer
    related_name       = 'health_info'
    is_one_to_one      = True
    permission_classes = [IsAuthenticated]

class LanguageInfoCRUD(BaseCRUD):
    serializer_class   = LanguageInfoSerializer
    related_name       = 'language_info'
    permission_classes = [IsAuthenticated]

class SocialLinkCRUD(BaseCRUD):
    serializer_class   = SocialLinkSerializer
    related_name       = 'social_links'
    permission_classes = [IsAuthenticated]

class ReprimandCRUD(BaseCRUD):
    serializer_class   = ReprimandSerializer
    related_name       = 'reprimands'
    permission_classes = [IsAuthenticated]

class FamilySocialStatusCRUD(BaseCRUD):
    serializer_class   = FamilySocialStatusSerializer
    related_name       = 'family_social_status'
    is_one_to_one      = True
    permission_classes = [IsAuthenticated]

class FamilyMemberCRUD(BaseCRUD):
    serializer_class   = FamilyMemberSerializer
    related_name       = 'family_members'
    permission_classes = [IsAuthenticated]

class InterestCRUD(BaseCRUD):
    serializer_class   = InterestSerializer
    related_name       = 'interests'
    permission_classes = [IsAuthenticated]

class SocialRegistryCRUD(BaseCRUD):
    serializer_class   = SocialRegistrySerializer
    related_name       = 'social_registries'
    permission_classes = [IsAuthenticated]

class DormitoryCRUD(BaseCRUD):
    serializer_class   = DormitorySerializer
    related_name       = 'dormitory'
    is_one_to_one      = True
    permission_classes = [IsAuthenticated]

class GiftedCRUD(BaseCRUD):
    serializer_class   = GiftedSerializer
    related_name       = 'gifteds'
    permission_classes = [IsAuthenticated]

class ProtectionOrderCRUD(BaseCRUD):
    serializer_class   = ProtectionOrderSerializer
    related_name       = 'protection_orders'
    permission_classes = [IsAuthenticated]

class RoleApiview(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = Role.objects.all()
        ser  = Roleserializer(role, many=True)
        return Response({
            'success': True,
            'message': "Rollar ro'yxati",
            'data':    ser.data,
        })

class Statistika(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        try:
            user = CustomUser.objects.get(id=user.id)
        except CustomUser.DoesNotExist:
            return Response({
                'success': False,
                'message':"user mavjud emas"
            })
        if user.role.id == 1:
            faculty = Faculty.objects.count()
            direction = Direction.objects.count()
            group = Group.objects.count()
            student = Student.objects.count()
            return Response({
                'success': True,
                'message':'fakultet, yo"nalishlar, guruhlar va studentlar soni admin uchun',
                'faculty': faculty,
                'direction': direction,
                'group': group,
                'student': student,
            })

        elif user.role.id == 2 or 3:
            if not user.faculty:
                return Response({
                    'success': False,
                    'message': "Sizga biriktirilgan fakultet yo'q"
                })

            faculty = user.faculty
            directions = Direction.objects.filter(faculty=faculty)
            groups = Group.objects.filter(direction__faculty=faculty)
            students = Student.objects.filter(group__direction__faculty=faculty)

            role_label = "Dekan" if user.role.id == 3 else "Zam dekan"
            return Response({
                'success': True,
                'message': f"{role_label} uchun statistika",
                'faculty': faculty.name,
                'direction': directions.count(),
                'group': groups.count(),
                'student': students.count(),
            })

        elif role.id == 2:
            groups = Group.objects.filter(tutor=user)
            students = Student.objects.filter(group__in=groups)

            return Response({
                'success': True,
                'message': "Tutor uchun statistika",
                'group': groups.count(),
                'student': students.count(),
            })

        return Response({
            'success': False,
            'message': "Sizning rolingiz uchun statistika mavjud emas"
        })

class ReprimandStudentGet(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role.id == 1:
            students = Student.objects.all()

        elif user.role.id in [2, 3, 4]:
            if not user.faculty:
                return fail("Sizga biriktirilgan fakultet yo'q", status.HTTP_404_NOT_FOUND)
            students = Student.objects.filter(group__direction__faculty=user.faculty)

        elif user.role.id == 2:  # tutor
            students = Student.objects.filter(group__tutor=user)

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

        return Response({
            'success'         : True,
            'message'         : "Hayfisand olgan talabalar",
            'total_students'  : students.count(),   # nechta talaba hayfisand olgan
            'data'            : data,
        })

class categoryInterstView(viewsets.ModelViewSet):
    serializer_class   = CategoryInterestSerializer
    queryset           = CategoryInterest.objects.all()
    permission_classes = [IsAuthenticated]