from django.urls import path
from .views import *
from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register('users',CreateUserViewSet,basename='create_user'),

urlpatterns = [
    path('import-students/', import_students, name='import_students'),
    path('update-students/',update_students),
    path('login/',login,name='login'),
    path('groups/',TutorApiView.as_view()),
    path('students/<int:id>',StudentGEtApiView.as_view()),
    path('students/<int:id>/', StudentGEtApiView.as_view()),
    path('role/', role_get)
]+ router.urls

























































