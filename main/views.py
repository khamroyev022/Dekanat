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

        if not user or not user.role:
            return Response({
                'success': False,
                'message': "Foydalanuvchi yoki role mavjud emas",
                'data': None
            }, status=status.HTTP_400_BAD_REQUEST)

        pagination = StudentPagination()

        if user.role.id == 2:
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

        elif user.role.id in [1, 3]:
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
            'message': "Ruxsat yo‘q",
            'data': None
        }, status=status.HTTP_403_FORBIDDEN)

class StudentGEtApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        try:
            group = Group.objects.get(id=id)
        except Group.DoesNotExist:
            return Response({
                'success': False,
                'message': "Guruh topilmadi",
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)

        # Tutor faqat o'zining guruhini ko'ra oladi
        if getattr(request.user.role, 'name', None) == 'tutor':
            if group.tutor != request.user:
                return Response({
                    'success': False,
                    'message': "Bu guruhga ruxsatingiz yo'q",
                    'data': None
                }, status=status.HTTP_403_FORBIDDEN)

        students = group.students.all()

        pagination = StudentPagination()
        result = pagination.paginate_queryset(students, request)

        serializer = Studentserializer(result, many=True)

        return pagination.get_paginated_response({
            'success': True,
            'message': "Guruh studentlari",
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




































