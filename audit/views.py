
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import  status
from .serializer import *
from django.db.models import Q
from .models import AuditLog



class AuditLogListView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Faqat admin ko'ra oladi
        if not (user.is_superuser or getattr(user.role, 'name', '').lower() == 'admin'):
            return Response(
                {'success': False, 'message': "Ruxsat yo'q", 'data': None},
                status=status.HTTP_403_FORBIDDEN
            )

        qs = AuditLog.objects.select_related('user', 'user__role')

        # ── Filtrlar ──────────────────────────────────────────
        action     = request.query_params.get('action')
        model_name = request.query_params.get('model_name')
        user_id    = request.query_params.get('user_id')
        method     = request.query_params.get('method')
        search     = request.query_params.get('search')
        date_from  = request.query_params.get('date_from')
        date_to    = request.query_params.get('date_to')

        if action:
            qs = qs.filter(action__iexact=action)
        if model_name:
            qs = qs.filter(model_name__icontains=model_name)
        if user_id:
            qs = qs.filter(user_id=user_id)
        if method:
            qs = qs.filter(method__iexact=method)
        if search:
            qs = qs.filter(
                Q(endpoint__icontains=search) |
                Q(description__icontains=search)
            )
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        # ── Pagination ────────────────────────────────────────
        try:
            page      = max(1, int(request.query_params.get('page', 1)))
            page_size = min(200, max(1, int(request.query_params.get('page_size', 50))))
        except ValueError:
            page, page_size = 1, 50

        total  = qs.count()
        offset = (page - 1) * page_size
        qs     = qs[offset: offset + page_size]

        return Response({
            'success': True,
            'message': "Audit loglar",
            'data': {
                'total'    : total,
                'page'     : page,
                'page_size': page_size,
                'results'  : AuditLogSerializer(qs, many=True).data,
            }
        })