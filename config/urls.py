from django.urls import path, re_path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Dekanat API",
        default_version='v1',
        description="Dekanat tizimi API hujjati",
        contact=openapi.Contact(email="admin@admin.com"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)
urlpatterns = [
    path('api/',include('main.urls')),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0)),
]