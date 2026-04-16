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
    start_page = 1
    max_pages = 1# 538

    service = HEMISStudentUpdate(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
        save_images=False
    )

    result = service.run(start_page=start_page, max_pages=max_pages)

    return Response({
        "message": "Yangilash muvaffaqiyatli yakunlandi",
        "created": result["created"],
        "updated": result["updated"],
        "last_page": result["last_page"]
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

class CreateUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all().prefetch_related('tutor_groups').select_related('role')
    serializer_class = CreateUserSerializer
    permission_classes = [AllowAny]

class TutorApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if not user or not user.role_id:
            return Response({
                'success': False,
                'message': "Foydalanuvchi yoki role mavjud emas",
                'data': None
            }, status=status.HTTP_400_BAD_REQUEST)

        pagination = StudentPagination()

        if user.role_id == ROLE_TUTOR_ID:
            groups = Group.objects.filter(tutor=user)
            result = pagination.paginate_queryset(groups, request)
            serializer = TutorGroupSerializer(result, many=True)

            return pagination.get_paginated_response({
                'success': True,
                'username': user.username,
                'message': "Tyutor guruhlari",
                'count': groups.count(),
                'data': serializer.data,
            })

        elif user.role_id in [ROLE_ADMIN_ID, ROLE_DEKAN_ID, ROLE_ZAM_DEKAN_ID]:
            groups = Group.objects.all()
            result = pagination.paginate_queryset(groups, request)
            serializer = GroupSerializer(result, many=True)

            return pagination.get_paginated_response({
                'success': True,
                'username': user.username,
                'message': "Barcha guruhlar",
                'count': groups.count(),
                'data': serializer.data,
            })

        return Response({
            'success': False,
            'message': "Ruxsat yo'q",
            'data': None
        }, status=status.HTTP_403_FORBIDDEN)
class StudentGetApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        group_id = request.query_params.get('group_id')
        group_name = request.query_params.get('group_name')  # ← nom bo'yicha ham
        pagination = StudentPagination()

        if group_id or group_name:
            try:
                if group_id:
                    group = Group.objects.get(id=group_id)
                else:
                    group = Group.objects.get(name__icontains=group_name)  # ← icontains - katta/kichik harf farq qilmaydi
            except Group.DoesNotExist:
                return Response({
                    'success': False,
                    'message': "Guruh topilmadi",
                    'data': None
                }, status=status.HTTP_404_NOT_FOUND)

            if request.user.role_id == ROLE_TUTOR_ID:
                if group.tutor != request.user:
                    return Response({
                        'success': False,
                        'message': "Bu guruhga ruxsatingiz yo'q",
                        'data': None
                    }, status=status.HTTP_403_FORBIDDEN)

            students = group.students.all()
            message = f"'{group.name}' guruh studentlari"

        else:
            if request.user.role_id == ROLE_TUTOR_ID:
                students = Student.objects.filter(group__tutor=request.user)
            else:
                students = Student.objects.all()
            message = "Barcha studentlar"

        result = pagination.paginate_queryset(students, request)
        serializer = StudentSerializer(result, many=True)

        return pagination.get_paginated_response({
            'success': True,
            'message': message,
            'data': serializer.data,
        })
@api_view(['GET'])
@permission_classes([AllowAny])
def role_get(request):
    if request.method == 'GET':
        role = Role.objects.all()
        ser = Roleserializer(role, many=True)
        return Response({
            'success': True,
            'message': "role mavjud ",
            'data': ser.data,
        }, status=status.HTTP_200_OK)
    return Response({
        'success': False,
        'message': "role mavjud ",
        'data': None
    },status=status.HTTP_400_BAD_REQUEST)

class DekanFacultyView(APIView):
    permission_classes = [IsAuthenticated]

    def get_faculty(self, request):
        if request.user.role_id not in DEKAN_ROLE_IDS:
            return None, Response({
                'success': False,
                'message': "Sizda dekan yoki zam dekan roli yo'q",
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)

        if not request.user.faculty_id:
            return None, Response({
                'success': False,
                'message': "Sizga fakultet biriktirilmagan",
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)

        return request.user.faculty, None

    def get(self, request):
        faculty, error = self.get_faculty(request)
        if error:
            return error

        directions = faculty.directions.all()

        pagination = StudentPagination()
        result = pagination.paginate_queryset(directions, request)
        serializer = DirectionDekanSerializer(result, many=True)

        return pagination.get_paginated_response({
            'success': True,
            'message': "Fakultet ma'lumotlari",
            'faculty': {
                'id': faculty.id,
                'name': faculty.name,
                'code': faculty.code,
            },
            'data': serializer.data
        })

class DekanStudentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role_id not in DEKAN_ROLE_IDS:
            return Response({
                'success': False,
                'message': "Sizda dekan yoki zam dekan roli yo'q",
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)

        if not request.user.faculty_id:
            return Response({
                'success': False,
                'message': "Sizga fakultet biriktirilmagan",
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)

        faculty = request.user.faculty

        students = Student.objects.filter(
            group__direction__faculty=faculty
        ).select_related('group__direction')

        direction_id = request.query_params.get('direction_id')
        group_id = request.query_params.get('group_id')
        course = request.query_params.get('course')
        gender = request.query_params.get('gender')

        if direction_id:
            students = students.filter(group__direction_id=direction_id)
        if group_id:
            students = students.filter(group_id=group_id)
        if course:
            students = students.filter(course=course)
        if gender:
            students = students.filter(gender=gender)

        pagination = StudentPagination()
        result = pagination.paginate_queryset(students, request)
        serializer = StudentDekanSerializer(result, many=True)

        return pagination.get_paginated_response({
            'success': True,
            'message': "Fakultet studentlari",
            'data': serializer.data
        })

class FacultyApiview(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):

        factulty = Faculty.objects.all()
        ser = Facultyserializer(factulty, many=True)
        return Response({
            'success': True,
            'message': "Fakultet mavjud ",
            'data': ser.data

        },status=status.HTTP_200_OK)

class DirectionGroups(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        try:
            direction = Direction.objects.get(id=id)
        except Direction.DoesNotExist:
            return Response({
                'success': False,
                'message': "Yo'nalish topilmadi",
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)

        # Dekan / Zam dekan — faqat o'z fakultetidagi yo'nalishni ko'radi
        if request.user.role_id in DEKAN_ROLE_IDS:
            if not request.user.faculty_id:
                return Response({
                    'success': False,
                    'message': "Sizga fakultet biriktirilmagan",
                    'data': None
                }, status=status.HTTP_403_FORBIDDEN)

            if direction.faculty_id != request.user.faculty_id:
                return Response({
                    'success': False,
                    'message': "Bu yo'nalish sizning fakultetingizga tegishli emas",
                    'data': None
                }, status=status.HTTP_403_FORBIDDEN)

            groups = Group.objects.filter(direction=direction)

        # Tutor — faqat o'ziga biriktirilgan guruhlarni ko'radi
        elif request.user.role_id == ROLE_TUTOR_ID:
            groups = Group.objects.filter(direction=direction, tutor=request.user)

        # Admin — hammasini ko'radi
        elif request.user.role_id == ROLE_ADMIN_ID:
            groups = Group.objects.filter(direction=direction)

        else:
            return Response({
                'success': False,
                'message': "Ruxsat yo'q",
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = GroupSerializer(groups, many=True)
        return Response({
            'success': True,
            'message': "Yo'nalish guruhlari",
            'direction': {
                'id': direction.id,
                'name': direction.name,
                'code': direction.code,
            },
            'data': serializer.data
        })



























