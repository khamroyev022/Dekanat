from lib2to3.pgen2.tokenize import group

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
from rest_framework import  status
from  .hemis_get_student import HEMISStudentImportService
from rest_framework_simplejwt.tokens import RefreshToken
from .persmission import *

ROLE_TUTOR_ID = 2
ROLE_ADMIN_ID = 1
ROLE_DEKAN_ID = 3
ROLE_ZAM_DEKAN_ID = 4

DEKAN_ROLE_IDS = [3, 4]  # dekan va zam_dekan

@api_view(['POST'])
@permission_classes([AllowAny])
def import_students(request):
    base_url = request.data.get("base_url") or "https://student.bsmi.uz/rest/v1/data/student-list"
    token = request.data.get("token") or HEMIS_TOKEN
    start_page = request.data.get("start_page", 1)
    max_pages = request.data.get("max_pages", 583) #583

    service = HEMISStudentImportService(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
        save_images=False
    )

    result = service.run(start_page=start_page, max_pages=max_pages)

    return Response({
        "message": "Import muvaffaqiyatli yakunlandi",
        "created": result["created"],
        "updated": result["updated"],
        "last_page": result["last_page"],
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
def update_students(request):
    base_url = "https://student.bsmi.uz/rest/v1/data/student-list"
    token = HEMIS_TOKEN
    start_page = request.data.get("start_page", 1)
    max_pages = request.data.get("max_pages", 583)  # ← 583 ga o'zgartiring

    service = HEMISStudentUpdate(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
        save_images=False
    )

    result = service.run(start_page=start_page, max_pages=max_pages)

    return Response({
        "message": "Yangilash muvaffaqiyatli yakunlandi",
        "updated": result["updated"],
        "skipped": result["skipped"],
        "last_page": result["last_page"],
        "failed_pages": result["failed_pages"],
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def login(request):
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response({
            'success': False,
            'message': "username yoki password majburiy",
            'data': None
        }, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(request, username=username, password=password)

    if user is None:
        return Response({
            'success': False,
            'message': "username yoki password noto‘g‘ri",
            'data': None
        }, status=status.HTTP_400_BAD_REQUEST)

    refresh = RefreshToken.for_user(user)
    serializer = LoginSerializer(user)

    return Response({
        'success': True,
        'message': "Login muvaffaqiyatli",
        'data': serializer.data,
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'username': user.username,
    }, status=status.HTTP_200_OK)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()  # tokenni blacklistga qo'shadi
            return Response({
                'success': True,
                'message': "Muvaffaqiyatli chiqildi"
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class CreateUserViewSet(viewsets.ModelViewSet):
    serializer_class = CreateUserSerializer
    permission_classes = [UserCRUDPermission]

    def get_queryset(self):
        user = self.request.user
        role_name = getattr(user.role, 'name', '').lower().strip()

        if user.is_superuser or role_name == ROLE_ADMIN:
            return CustomUser.objects.all() \
                .prefetch_related('tutor_groups') \
                .select_related('role', 'faculty')

        # Dekan — o'zi + o'z fakultetidagi tutor va zam dekan
        if role_name == ROLE_DEKAN:
            from django.db.models import Q
            return CustomUser.objects.filter(
                Q(id=user.id) |  # o'zi
                Q(faculty=user.faculty, role__name__iregex=r'^(tutor|zam dekan)$')
            ).prefetch_related('tutor_groups').select_related('role', 'faculty')

        # Zam dekan — faqat o'z fakultetidagi tutorlar
        if role_name == ROLE_ZAM_DEKAN:
            return CustomUser.objects.filter(
                faculty=user.faculty,
                role__name__iregex=r'^tutor$'
            ).prefetch_related('tutor_groups').select_related('role', 'faculty')

        return CustomUser.objects.none()

    def _resolve_role(self, role_id):
        try:
            return Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return None

    def create(self, request, *args, **kwargs):
        user = request.user
        role_name = getattr(user.role, 'name', '').lower().strip()

        # Dekan — faqat tutor(id=2) va zam dekan(id=4) yarata oladi
        if role_name == ROLE_DEKAN:
            try:
                new_role_id = int(request.data.get('role'))
            except (TypeError, ValueError):
                return Response({
                    'success': False,
                    'message': "Role kiritilmagan"
                }, status=status.HTTP_400_BAD_REQUEST)

            if new_role_id not in [ROLE_TUTOR_ID, ROLE_ZAM_DEKAN_ID]:
                return Response({
                    'success': False,
                    'message': "Siz faqat tutor yoki zam dekan yarata olasiz"
                }, status=status.HTTP_403_FORBIDDEN)

            data = request.data.copy()
            data['faculty'] = user.faculty_id
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response({
                'success': True,
                'message': "Foydalanuvchi yaratildi",
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)

        # Zam dekan — faqat tutor(id=2) yarata oladi
        if role_name == ROLE_ZAM_DEKAN:
            try:
                new_role_id = int(request.data.get('role'))
            except (TypeError, ValueError):
                return Response({
                    'success': False,
                    'message': "Role kiritilmagan"
                }, status=status.HTTP_400_BAD_REQUEST)

            if new_role_id != ROLE_TUTOR_ID:
                return Response({
                    'success': False,
                    'message': "Siz faqat tutor yarata olasiz"
                }, status=status.HTTP_403_FORBIDDEN)

            data = request.data.copy()
            data['faculty'] = user.faculty_id
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response({
                'success': True,
                'message': "Tutor yaratildi",
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)

        # Admin — cheklovsiz
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self.perform_destroy(self.get_object())
        return Response({
            'success': True,
            'message': "Foydalanuvchi o'chirildi"
        }, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'success': True,
            'message': "Yangilandi",
            'data': serializer.data
        })

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return Response({
            'success': True,
            'data': serializer.data
        })

class FacultyGEtApipview(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        if user.role.id == 1:
            faculty = Faculty.objects.all()
            ser = Facultyserializer(faculty, many=True)
            return Response({
                'success': True,
                'user':user.username,
                'message':"Hamma fakultetlar ro'yxati",
                'data': ser.data
            },status=status.HTTP_200_OK)
        elif user.role.id == 2 or 3 or 4:
            faculty = Faculty.objects.filter(dekans=user)
            ser = Facultyserializer(faculty, many=True)
            return Response({
                'success': True,
                'user':user.username,
                'message':"Sizning fakultetingiz",
                'data':ser.data
            },status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message':"Xatolik yuz berdi",
                'data':{},
            },status=status.HTTP_400_BAD_REQUEST)

class DirectionGETApiview(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        user = request.user
        faculty_id = request.query_params.get('faculty_id')

        if not faculty_id:
            return Response({
                'success': False,
                'message': 'faculty_id parametri kiritilmadi',
                'data': None,
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            faculty_id = Faculty.objects.get(id=faculty_id)
        except Faculty.DoesNotExist:
            return Response({
                'success': False,
                'message': "Fakultet topilmadi",
                'data': None
            }, status=status.HTTP_400_BAD_REQUEST)

        if user.role.id == 1:
            direction = Direction.objects.filter(faculty_id = faculty_id)
            ser = Directionserializer(direction, many=True)

            return Response({
                'success': True,
                'message':"Yo'naishlar",
                'faculty':faculty_id.name,
                'data': ser.data
            },status.HTTP_200_OK)


        elif user.role.id in [2, 3, 4]:
            if not user.faculty:
                return Response({
                    'success': False,
                    'message': "Sizga biriktirilgan fakultet yo'q",
                    'data': None
                }, status=status.HTTP_404_NOT_FOUND)

            directions = Direction.objects.filter(faculty=user.faculty)
            ser = DirectionSerializer(directions, many=True)

            return Response({
                'success': True,
                'message': "Sizning fakultetingiz yo'nalishlari",
                'faculty': user.faculty.name,
                'data': ser.data
            }, status=status.HTTP_200_OK)

        else:
            return Response({
                'success': False,
                'message': "Ruxsat yo'q",
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)

class GroupsGetApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role.id == 1:
            direction_id = request.query_params.get('direction_id')
            if not direction_id:
                return Response({
                    'success': False,
                    'message': 'direction_id parametri kiritilmadi',
                    'data': None,
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                direction = Direction.objects.get(id=direction_id)
            except Direction.DoesNotExist:
                return Response({
                    'success': False,
                    'message': "Yo'nalish topilmadi",
                    'data': None,
                }, status=status.HTTP_404_NOT_FOUND)

            groups = Group.objects.filter(direction=direction)
            ser = GroupSerializer(groups, many=True)

            return Response({
                'success': True,
                'message': "Guruhlar ro'yxati",
                'direction': direction.name,
                'data': ser.data
            }, status=status.HTTP_200_OK)

        elif user.role.id in [2, 3, 4]:
            if not user.faculty:
                return Response({
                    'success': False,
                    'message': "Sizga biriktirilgan fakultet yo'q",
                    'data': None
                }, status=status.HTTP_404_NOT_FOUND)

            groups = Group.objects.filter(direction__faculty=user.faculty)
            ser = GroupSerializer(groups, many=True)

            return Response({
                'success': True,
                'message': "Sizning fakultetingiz guruhlari",
                'faculty': user.faculty.name,
                'data': ser.data
            }, status=status.HTTP_200_OK)

        else:
            return Response({
                'success': False,
                'message': "Ruxsat yo'q",
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)
PREFETCH_FIELDS = [
    'achievements', 'health_info', 'language_info',
    'social_links', 'reprimands', 'family_social_status',
    'family_members', 'interests', 'social_registries',
    'dormitories', 'gifteds', 'protection_orders',
]


class StudentCRUD(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        student_id = request.query_params.get('student_id')
        group_id = request.query_params.get('group_id')

        # --- Bitta student ---
        if student_id:
            try:
                student = Student.objects.prefetch_related(
                    'details', *PREFETCH_FIELDS
                ).get(id=student_id)
            except Student.DoesNotExist:
                return fail("Student topilmadi", status.HTTP_404_NOT_FOUND)

            # Rol tekshiruvi (2,3,4 uchun fakultet cheki)
            if user.role.id in [2, 3, 4]:
                if not user.faculty:
                    return fail("Sizga biriktirilgan fakultet yo'q", status.HTTP_404_NOT_FOUND)
                if student.group.direction.faculty != user.faculty:
                    return fail("Bu student sizning fakultetingizga tegishli emas", status.HTTP_403_FORBIDDEN)
            elif user.role.id != 1:
                return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

            ser = StudentFullSerializer(student)
            return ok("Student ma'lumoti", ser.data)

        # --- Guruh bo'yicha studentlar ---
        if group_id:
            try:
                group = Group.objects.get(id=group_id)
            except Group.DoesNotExist:
                return fail("Guruh topilmadi", status.HTTP_404_NOT_FOUND)

            if user.role.id in [2, 3, 4]:
                if not user.faculty:
                    return fail("Sizga biriktirilgan fakultet yo'q", status.HTTP_404_NOT_FOUND)
                if group.direction.faculty != user.faculty:
                    return fail("Bu guruh sizning fakultetingizga tegishli emas", status.HTTP_403_FORBIDDEN)
            elif user.role.id != 1:
                return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

            students = Student.objects.filter(
                group=group
            ).prefetch_related(*PREFETCH_FIELDS)

            paginator = StudentPagination()
            page = paginator.paginate_queryset(students, request)
            if page is not None:
                ser = StudentSerializer(page, many=True)
                return paginator.get_paginated_response(ser.data)

            ser = StudentSerializer(students, many=True)
            return ok(f"Studentlar ro'yxati ({group.name})", ser.data)

        # --- Barcha studentlar (faqat admin) ---
        if user.role.id != 1:
            return fail("Ruxsat yo'q", status.HTTP_403_FORBIDDEN)

        students = Student.objects.all().prefetch_related(*PREFETCH_FIELDS)

        paginator = StudentPagination()
        page = paginator.paginate_queryset(students, request)
        if page is not None:
            ser = StudentSerializer(page, many=True)
            return paginator.get_paginated_response(ser.data)

        ser = StudentSerializer(students, many=True)
        return ok("Studentlar ro'yxati", ser.data)

    def post(self, request):
        ser = StudentSerializer(data=request.data)
        if ser.is_valid():
            ser.save()
            return ok("Student yaratildi", ser.data, status.HTTP_201_CREATED)
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


# --- Helper funksiyalar ---

def ok(message, data, code=status.HTTP_200_OK):
    return Response({'success': True, 'message': message, 'data': data}, status=code)

def fail(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({'success': False, 'message': message, 'data': None}, status=code)

def get_student(student_id):
    try:
        return Student.objects.get(id=student_id), None
    except Student.DoesNotExist:
        return None, fail("Student topilmadi", status.HTTP_404_NOT_FOUND)

class BaseCRUD(APIView):
    permission_classes = [AllowAny]
    serializer_class   = None
    related_name       = None

    def get(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id:
            return fail("student_id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err:
            return err
        qs  = getattr(student, self.related_name).all()
        ser = self.serializer_class(qs, many=True)
        return ok("Ma'lumotlar", ser.data)

    def post(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id:
            return fail("student_id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err:
            return err
        data = request.data.copy()
        data['student'] = student.id
        ser = self.serializer_class(data=data)
        if ser.is_valid():
            ser.save()
            return ok("Yaratildi", ser.data, status.HTTP_201_CREATED)
        return fail(ser.errors)

    def patch(self, request):
        student_id = request.query_params.get('student_id')
        record_id  = request.query_params.get('id')
        if not student_id:
            return fail("student_id parametri kiritilmadi")
        if not record_id:
            return fail("id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err:
            return err
        try:
            obj = getattr(student, self.related_name).get(id=record_id)
        except Exception:
            return fail("Topilmadi", status.HTTP_404_NOT_FOUND)
        ser = self.serializer_class(obj, data=request.data, partial=True)
        if ser.is_valid():
            ser.save()
            return ok("Yangilandi", ser.data)
        return fail(ser.errors)

    def delete(self, request):
        student_id = request.query_params.get('student_id')
        record_id  = request.query_params.get('id')
        if not student_id:
            return fail("student_id parametri kiritilmadi")
        if not record_id:
            return fail("id parametri kiritilmadi")
        student, err = get_student(student_id)
        if err:
            return err
        try:
            obj = getattr(student, self.related_name).get(id=record_id)
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
    related_name     = 'dormitories'

class GiftedCRUD(BaseCRUD):
    serializer_class = GiftedSerializer
    related_name     = 'gifteds'

class ProtectionOrderCRUD(BaseCRUD):
    serializer_class = ProtectionOrderSerializer
    related_name     = 'protection_orders'



class RoleApiview(APIView):
    permission_classes(IsAuthenticated)
    def get(self, request):
        role = Role.objects.all()
        ser = Roleserializer(role, many=True)
        return Response({
            'success': True,
            'message':"Rollar ro'yxati",
            'data': ser.data,
        })





















