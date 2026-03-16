from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
import requests
from config.settings import HEMIS_TOKEN
from .hemis_update_db import HEMISStudentUpdate
from .models import *
from django.contrib.auth import authenticate
from .serializers import *
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets
from rest_framework import  status
from  .hemis_get_student import HEMISStudentImportService
from rest_framework_simplejwt.tokens import RefreshToken
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_students(request):
    base_url = request.data.get("base_url") or "https://student.bsmi.uz/rest/v1/data/student-list"
    token = request.data.get("token") or HEMIS_TOKEN
    start_page = request.data.get("start_page", 1)
    max_pages = request.data.get("max_pages", 1) #538

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
@permission_classes([IsAuthenticated])
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

class CreateUserviewset(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CreateUserSerializer
    permission_classes = [AllowAny]


class TutorApiView(APIView):
    permission_classes = [AllowAny]

    def get(self, request,id):
        try:
            user = CustomUser.objects.get(id=request.user.id)
        except CustomUser.DoesNotExist:
            return Response({
                'success': False,
                'message': "Foydalanuvchi mavjud emas",
                'data': None
            }, status=status.HTTP_404_NOT_FOUND)

        if user.role.id != 3:
            return Response({
                'success': False,
                'message': "Siz tyutor emassiz",
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)

        groups = Group.objects.filter(user=user)
        serializer = TutorGroupSerializer(groups, many=True)

        return Response({
            'success': True,
            'message': "Tyutor guruhlari",
            'count': groups.count(),
            'data': serializer.data,
            'username': user.username,
        }, status=status.HTTP_200_OK)









