from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
import requests

from config.settings import HEMIS_TOKEN
from .models import *
from .serializers import *
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import viewsets
from rest_framework import  status
from  .hemis_get_student import HEMISStudentImportService

@api_view(['POST'])
def import_students(request):
    base_url = request.data.get("base_url") or "https://student.bsmi.uz/rest/v1/data/student-list"
    token = request.data.get("token") or HEMIS_TOKEN
    start_page = request.data.get("start_page", 1)
    max_pages = request.data.get("max_pages", 538)

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
        "last_page": result["last_page"]
    }, status=status.HTTP_200_OK)



















