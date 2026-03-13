from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
import requests
from .models import *
from .serializers import *
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets
from rest_framework import  status

from .service import HEMISStudentImportService


class ImportStudentsAPIView(APIView):

    def post(self, request):

        service = HEMISStudentImportService(
            base_url="https://student.bsmi.uz/api/your-endpoint",
            headers={
                "Accept": "application/json",
            },
            save_images=False
        )

        result = service.run(start_page=1)

        return Response(
            {
                "message": "Studentlar import qilindi",
                "result": result
            },
            status=status.HTTP_200_OK
        )








